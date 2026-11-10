import difflib
from pathlib import Path
from openai.types.chat import ChatCompletionFunctionToolParam
import hashlib
import os
import shutil
import tempfile



READ_VERSIONS = {}

READ_FILE_TOOL: ChatCompletionFunctionToolParam = {
    "type": "function",
    "function": {
        "name": "read_file",
        "description": "读取工作区内的 UTF-8 文本文件，返回源码及截断说明。",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "相对于工作区的文件路径，例如 demo.py。",
                },
            },
            "required": ["path"],
            "additionalProperties": False,
        },
    },
}

def read_file(
        workspace_root: Path,
        path: str,
        max_chars: int = 4000,
) -> dict[str, object]:
    # 审查参数
    if Path(path).anchor or ":" in path:
        return {"ok": False, "error": "path参数不是工作区内的相对路径"}

    root = workspace_root.resolve()
    target = (root / path).resolve()

    if not target.is_relative_to(root):
        return {"ok": False, "error": "文件路径超出工作区范围"}

    max_file_bytes = 64 * 1024

    # 读文件
    with target.open("rb") as file:
        raw = file.read(max_file_bytes + 1)

    if len(raw) > max_file_bytes:
        return {"ok": False, "error": "当前只支持内容不超过 64 KB的文本文件，该文件内容超出限制"}

    text = raw.decode("utf-8")
    version_id = hashlib.sha256(raw).hexdigest()
    READ_VERSIONS[(root, target)] = version_id

    result = {
        "ok": True,
        "result": {
            "path": target.relative_to(root).as_posix(),
            "content": text[:max_chars],
            "truncated": len(text) > max_chars,
            "version_id": version_id,
        }
    }



    return result


LIST_FILES_TOOL: ChatCompletionFunctionToolParam = {
    "type": "function",
    "function": {
        "name": "list_files",
        "description": "列出指定目录的直接子项。需要发现文件时使用，不读取文件内容。",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": '相对于工作区的目录路径；工作区根目录使用 "."。',
                },
            },
            "required": ["path"],
            "additionalProperties": False,
        },
    },
}

def list_files(
    workspace_root: Path,
    path: str = ".",
    max_entries: int = 50,
) -> dict[str, object]:
    # 审查参数
    if Path(path).anchor or ":" in path:
        return {"ok": False, "error": "path参数不是工作区内的相对路径"}

    root = workspace_root.resolve()
    target = (root / path).resolve()

    if not target.is_relative_to(root):
        return {"ok": False, "error": "文件路径超出工作区范围"}

    children = sorted(target.iterdir())

    entries = []
    for child in children[:max_entries]:
        entries.append({
            "path": child.relative_to(root).as_posix(),
            "type": "directory" if child.is_dir() else "file",
        })

    return {
        "ok": True,
        "result": {
            "path": target.relative_to(root).as_posix(),
            "entries": entries,
            "truncated": len(children) > max_entries,
        },
    }


EDIT_FILE_TOOL: ChatCompletionFunctionToolParam = {
    "type": "function",
    "function": {
        "name": "edit_file",
        "description": (
            "精确替换工作区内文件的一处文本。"
            "必须先读取文件，写入前由本地程序请求用户确认。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "相对于工作区的文件路径。",
                },
                "base_version": {
                    "type": "string",
                    "description": "最近一次 read_file 返回的 version_id，原样传入。",
                },
                "old_text": {
                    "type": "string",
                    "description": "要替换的原文，必须非空且在文件中精确匹配一次。",
                },
                "new_text": {
                    "type": "string",
                    "description": "替换后的文本。",
                },
            },
            "required": ["path", "base_version", "old_text", "new_text"],
            "additionalProperties": False,
        },
    },
}

def edit_file(
    workspace_root: Path,
    path: str,
    base_version: str,
    old_text: str,
    new_text: str,
) -> dict[str, object]:
    # 审查参数
    if Path(path).anchor or ":" in path:
        return {"ok": False, "error": "path参数不是工作区内的相对路径"}

    root = workspace_root.resolve()
    target = (root / path).resolve()

    if not target.is_relative_to(root):
        return {"ok": False, "error": "文件路径超出工作区范围"}


    if READ_VERSIONS.get((root, target)) != base_version:
        return {"ok": False, "error": "base_version 不一致，文件内容存在修改"}

    # 读文件，生成新内容
    max_file_bytes = 64 * 1024

    with target.open("rb") as file:
        raw = file.read(max_file_bytes + 1)

    if len(raw) > max_file_bytes:
        return {"ok": False, "error": "当前只支持内容不超过 64 KB的文本文件，该文件内容超出限制"}

    version_id = hashlib.sha256(raw).hexdigest()
    if version_id != base_version:
        return {"ok": False, "error": "文件存在修改 base_version 与当前文件内容不符"}

    content = raw.decode("utf-8")
    if not old_text or content.count(old_text) != 1:
        return {"ok": False, "error": "old_text 为空或在文件内容中出现次数不为1"}

    new_content = content.replace(old_text, new_text, 1)
    new_raw = new_content.encode("utf-8")

    # 查看diff
    diff = "\n".join(difflib.unified_diff(
        content.splitlines(),
        new_content.splitlines(),
        fromfile=path,
        tofile=path,
        lineterm="",
    ))

    print(diff)

    if input("应用这次修改？[y/N] ").strip().lower() != "y":
        return {"ok": False, "error": "用户拒绝修改"}

    # 修改文件，采用临时文件形式
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
                mode="wb", dir=target.parent, delete=False
        ) as file:
            temp_path = Path(file.name)
            file.write(new_raw)

        # 查看等待用户确认期间，是否发生文件修改
        with target.open("rb") as file:
            current_raw = file.read(max_file_bytes + 1)

        if hashlib.sha256(current_raw).hexdigest() != base_version:
            return {"ok": False, "error": "确认期间文件发生变化，请重新读取"}

        shutil.copymode(target, temp_path)
        os.replace(temp_path, target)

    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)

    READ_VERSIONS.pop((root, target), None)

    return {
        "ok": True,
        "result": {
            "path": path,
            "version_id": hashlib.sha256(new_raw).hexdigest(),
            "diff": diff,
        },
    }



FILE_HANDLER = {
    "read_file": read_file,
    "list_files": list_files,
}

