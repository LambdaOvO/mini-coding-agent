import fnmatch
import os
import shutil
import subprocess
from pathlib import Path
from time import monotonic

from openai.types.chat import ChatCompletionFunctionToolParam
from mini_coding_agent.workspace import (
    IGNORED_DIRECTORIES as _IGNORED_DIRECTORIES,
    is_secret_file as _is_secret_file,
    resolve_path,
)


SEARCH_CODE_TOOL: ChatCompletionFunctionToolParam = {
    "type": "function",
    "function": {
        "name": "search_code",
        "description": (
            "在工作区内递归搜索文本，按字面量、区分大小写匹配，"
            "返回文件相对路径、行号和匹配片段。"
            "不知道代码在哪个文件时先搜索；编辑前仍需 read_file 获取文件版本。"
            "默认跳过依赖目录、常见秘密文件和二进制文件；"
            "只读取不超过 256 KiB 的 UTF-8 文件，单次搜索有扫描量和时间预算。"
            "truncated 为 true 表示搜索结果不完整，可缩小 glob 后重试。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": 256,
                    "description": "要查找的原文，例如函数名 calculate_total；不使用正则表达式。",
                },
                "glob": {
                    "type": "string",
                    "description": "文件路径过滤模式，例如 *.py 或 src/*.py；默认 *。",
                },
                "max_results": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 50,
                    "description": "最多返回的匹配行数，默认 30。",
                },
            },
            "required": ["query"],
            "additionalProperties": False,
        },
    },
}


def _is_workspace_path(path: Path, root: Path) -> bool:
    try:
        resolve_path(root, path.relative_to(root).as_posix())
        return True
    except (OSError, ValueError):
        return False


def _git_visible_files(root: Path) -> set[str] | None:
    """仓库根目录使用 Git 自身的忽略规则；独立目录不受父仓库忽略规则影响。"""
    git = shutil.which("git")
    if not git or not (root / ".git").exists():
        return None
    environment = {
        name: value for name, value in os.environ.items()
        if name.upper() in {
            "SYSTEMROOT", "WINDIR", "PATH", "HOME", "USERPROFILE", "TEMP", "TMP",
        }
    }
    try:
        result = subprocess.run(
            [git, "--no-pager", "--no-optional-locks", "-c", "core.fsmonitor=false",
             "-C", str(root), "ls-files", "--cached", "--others", "--exclude-standard", "-z", "--", "."],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=2, env=environment,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode:
        return None
    return {name.decode("utf-8", errors="replace") for name in result.stdout.split(b"\0") if name}


def search_code(
    workspace_root: Path,
    query: str,
    glob: str = "*",
    max_results: int = 30,
) -> dict[str, object]:
    if not isinstance(query, str) or not query.strip() or len(query) > 256:
        return {"ok": False, "error": "query 必须是 1～256 个字符的非空文本"}
    if not isinstance(glob, str) or not glob.strip():
        return {"ok": False, "error": "glob 必须是非空的文件路径匹配模式"}
    if type(max_results) is not int or not 1 <= max_results <= 50:
        return {"ok": False, "error": "max_results 必须是 1～50 之间的整数"}

    root = workspace_root.resolve()
    if not root.is_dir():
        return {"ok": False, "error": "工作区必须是已经存在的目录"}

    matches = []
    visited_files = 0
    searched_files = 0
    skipped_files = 0
    truncated = False
    walk_errors = []
    deadline = monotonic() + 5
    max_file_bytes = 256 * 1024
    visible_files = _git_visible_files(root)
    visible_directories = (
        {parent.as_posix() for name in visible_files for parent in Path(name).parents}
        if visible_files is not None else None
    )

    for directory, directories, filenames in os.walk(
        root, topdown=True, followlinks=False, onerror=walk_errors.append,
    ):
        if truncated or monotonic() >= deadline:
            truncated = True
            break

        parent = Path(directory)
        # 原地删掉不搜索的目录，os.walk 就不会进入它们。
        directories[:] = [
            name for name in sorted(directories)
            if name.lower() not in _IGNORED_DIRECTORIES
            and (
                visible_directories is None
                or (parent / name).relative_to(root).as_posix() in visible_directories
            )
            and _is_workspace_path(parent / name, root)
        ]

        for name in sorted(filenames):
            if monotonic() >= deadline:
                truncated = True
                break

            candidate = parent / name
            relative_path = candidate.relative_to(root).as_posix()
            if visible_files is not None and relative_path not in visible_files:
                continue
            if _is_secret_file(name) or not fnmatch.fnmatch(relative_path, glob):
                continue
            if not _is_workspace_path(candidate, root):
                skipped_files += 1
                continue
            if visited_files >= 2000:
                truncated = True
                break
            visited_files += 1

            try:
                if not candidate.is_file():
                    continue
                with candidate.open("rb") as file:
                    raw = file.read(max_file_bytes + 1)
                if len(raw) > max_file_bytes or b"\x00" in raw:
                    skipped_files += 1
                    continue
                content = raw.decode("utf-8")
            except (OSError, UnicodeError):
                skipped_files += 1
                continue

            searched_files += 1
            for line_number, line in enumerate(content.splitlines(), start=1):
                position = line.find(query)
                if position == -1:
                    continue

                # 保留匹配位置附近的内容，避免长行撑满模型上下文。
                start = max(0, position - 80)
                preview = line[start:start + 400]
                if start:
                    preview = "…" + preview
                if start + 400 < len(line):
                    preview += "…"
                matches.append({
                    "path": relative_path,
                    "line": line_number,
                    "text": preview,
                })
                if len(matches) > max_results:
                    matches.pop()
                    truncated = True
                    break
            if truncated:
                break

    return {
        "ok": True,
        "result": {
            "query": query,
            "glob": glob,
            "matches": matches,
            "searched_files": searched_files,
            "skipped_files": skipped_files,
            "truncated": truncated or bool(walk_errors),
        },
    }
