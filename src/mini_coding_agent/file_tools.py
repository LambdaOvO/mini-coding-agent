"""文件读取、精确替换和创建。原始字节哈希是编辑的基准版本。"""

import codecs
import difflib
import hashlib
import os
import shutil
import stat
import tempfile
from collections.abc import Callable
from pathlib import Path

from openai.types.chat import ChatCompletionFunctionToolParam

from mini_coding_agent.permissions import ask_approval, display_text
from mini_coding_agent.workspace import (
    MAX_FILE_BYTES, WorkspaceError, read_text_bytes, resolve_path,
)

READ_VERSIONS: dict[tuple[Path, Path], str] = {}


def _schema(
    name: str, description: str, properties: dict, required: list[str],
) -> ChatCompletionFunctionToolParam:
    return {
        "type": "function",
        "function": {
            "name": name, "description": description,
            "parameters": {
                "type": "object", "properties": properties,
                "required": required, "additionalProperties": False,
            },
        },
    }


READ_FILE_TOOL: ChatCompletionFunctionToolParam = _schema(
    "read_file",
    "读取 UTF-8 文件并取得完整文件的 version_id。大文件用 start_line/end_line 分段读取；行号从 1 开始。",
    {
        "path": {"type": "string", "description": "工作区相对路径"},
        "start_line": {"type": "integer", "minimum": 1},
        "end_line": {"type": "integer", "minimum": 1},
    },
    ["path"],
)
LIST_FILES_TOOL: ChatCompletionFunctionToolParam = _schema(
    "list_files", "列出一个目录的直接子项，目录可以继续逐层展开。",
    {"path": {"type": "string", "description": "相对目录，根目录为 ."}},
    [],
)
EDIT_FILE_TOOL: ChatCompletionFunctionToolParam = _schema(
    "edit_file",
    "精确替换唯一一处原文。必须先 read_file 并原样回传 version_id；展示 Diff 后由程序请求批准。",
    {
        "path": {"type": "string"},
        "base_version": {"type": "string"},
        "old_text": {"type": "string", "minLength": 1},
        "new_text": {"type": "string"},
    },
    ["path", "base_version", "old_text", "new_text"],
)
CREATE_FILE_TOOL: ChatCompletionFunctionToolParam = _schema(
    "create_file",
    "创建新的 UTF-8 文件，可创建缺失的父目录。展示 Diff 并请求批准；绝不覆盖已有文件。",
    {"path": {"type": "string"}, "content": {"type": "string"}},
    ["path", "content"],
)


def _diff(path: str, before: str, after: str) -> str:
    diff = "\n".join(difflib.unified_diff(
        before.splitlines(), after.splitlines(),
        fromfile=path, tofile=path, lineterm="",
    ))
    return diff or "(仅换行格式或末尾换行发生变化)"


def read_file(
    workspace_root: Path, path: str, max_chars: int = 16000,
    start_line: int = 1, end_line: int | None = None,
) -> dict[str, object]:
    if type(start_line) is not int or start_line < 1:
        raise WorkspaceError("start_line 必须是从 1 开始的整数")
    if end_line is not None and (type(end_line) is not int or end_line < start_line):
        raise WorkspaceError("end_line 不能小于 start_line")
    root = workspace_root.resolve()
    target = resolve_path(root, path)
    raw, text = read_text_bytes(target)
    lines = text.splitlines(keepends=True)
    if start_line > max(1, len(lines)):
        raise WorkspaceError(f"起始行超过文件范围，文件共 {len(lines)} 行")
    end = min(end_line if end_line is not None else start_line + 199, len(lines))
    selected = "".join(lines[start_line - 1:end])
    version_id = hashlib.sha256(raw).hexdigest()
    READ_VERSIONS[(root, target)] = version_id
    return {
        "ok": True,
        "result": {
            "path": target.relative_to(root).as_posix(),
            "content": selected[:max_chars],
            "start_line": start_line, "end_line": end, "total_lines": len(lines),
            "truncated": end < len(lines) or len(selected) > max_chars,
            "content_truncated": len(selected) > max_chars,
            "next_line": end + 1 if end < len(lines) else None,
            "version_id": version_id,
        },
    }


def list_files(
    workspace_root: Path, path: str = ".", max_entries: int = 100,
) -> dict[str, object]:
    root = workspace_root.resolve()
    target = resolve_path(root, path)
    if not target.is_dir():
        raise WorkspaceError("目标不是已经存在的目录")
    entries = []
    truncated = False
    for child in sorted(target.iterdir(), key=lambda p: p.name.lower()):
        relative = child.relative_to(root).as_posix()
        try:
            resolve_path(root, relative)
        except (WorkspaceError, OSError):
            continue
        if len(entries) >= max_entries:
            truncated = True
            break
        entries.append({"path": relative, "type": "directory" if child.is_dir() else "file"})
    return {
        "ok": True,
        "result": {
            "path": target.relative_to(root).as_posix(),
            "entries": entries, "truncated": truncated,
        },
    }


def edit_file(
    workspace_root: Path, path: str, base_version: str, old_text: str, new_text: str,
    *, confirm: Callable[[str], bool] | None = None,
) -> dict[str, object]:
    root = workspace_root.resolve()
    target = resolve_path(root, path)
    if READ_VERSIONS.get((root, target)) != base_version:
        raise WorkspaceError("没有对应的读取版本，请先 read_file")
    raw, content = read_text_bytes(target)
    if hashlib.sha256(raw).hexdigest() != base_version:
        raise WorkspaceError("文件已经变化，请重新读取后编辑")
    if "\x00" in new_text:
        raise WorkspaceError("不能将二进制空字符写入文本文件")

    # 模型通常用 LF 编写多行参数，只规范化替换片段，不重写原文件其他行。
    newline = "\r\n" if "\r\n" in content else "\n"
    old_text = old_text.replace("\r\n", "\n").replace("\n", newline)
    new_text = new_text.replace("\r\n", "\n").replace("\n", newline)
    if not old_text or content.count(old_text) != 1:
        raise WorkspaceError("old_text 必须非空并且在当前文件中精确匹配一次")
    new_content = content.replace(old_text, new_text, 1)
    if new_content == content:
        return {"ok": True, "result": {"path": path, "changed": False, "version_id": base_version}}
    new_raw = new_content.encode("utf-8")
    if raw.startswith(codecs.BOM_UTF8):
        new_raw = codecs.BOM_UTF8 + new_raw
    if len(new_raw) > MAX_FILE_BYTES:
        raise WorkspaceError("编辑后文件超过 1 MiB 上限")
    diff = _diff(path, content, new_content)
    print(display_text(diff))
    if not (confirm or ask_approval)(f"应用对 {path} 的修改？"):
        return {"ok": False, "denied": True, "error": "用户拒绝修改"}

    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(mode="wb", dir=target.parent, delete=False) as file:
            temp_path = Path(file.name)
            file.write(new_raw)
        shutil.copymode(target, temp_path)
        current_target = resolve_path(root, path)
        current_raw, _ = read_text_bytes(current_target)
        if current_target != target or hashlib.sha256(current_raw).hexdigest() != base_version:
            raise WorkspaceError("确认期间文件发生变化，拒绝覆盖，请重新读取")
        os.replace(temp_path, target)
    finally:
        if temp_path is not None:
            if temp_path.exists() and os.name == "nt":
                temp_path.chmod(stat.S_IWRITE)
            temp_path.unlink(missing_ok=True)
    READ_VERSIONS.pop((root, target), None)
    return {
        "ok": True,
        "result": {
            "path": target.relative_to(root).as_posix(), "changed": True,
            "version_id": hashlib.sha256(new_raw).hexdigest(), "diff": diff,
        },
    }


def create_file(
    workspace_root: Path, path: str, content: str,
    *, confirm: Callable[[str], bool] | None = None,
) -> dict[str, object]:
    root = workspace_root.resolve()
    target = resolve_path(root, path)
    if target.exists():
        raise WorkspaceError("文件已存在，请先读取并使用 edit_file，不能覆盖")
    raw = content.encode("utf-8")
    if len(raw) > MAX_FILE_BYTES or "\x00" in content:
        raise WorkspaceError("只支持不超过 1 MiB 的 UTF-8 文本文件")
    diff = _diff(path, "", content)
    print(display_text(diff))
    if not (confirm or ask_approval)(f"创建 {path}？"):
        return {"ok": False, "denied": True, "error": "用户拒绝创建"}
    target = resolve_path(root, path)
    target.parent.mkdir(parents=True, exist_ok=True)
    # 排他创建：审批期间即使有人创建了同名文件，也不会被覆盖。
    with target.open("xb") as file:
        file.write(raw)
    return {
        "ok": True,
        "result": {
            "path": target.relative_to(root).as_posix(), "changed": True,
            "version_id": hashlib.sha256(raw).hexdigest(), "diff": diff,
        },
    }


FILE_HANDLER = {"read_file": read_file, "list_files": list_files}
