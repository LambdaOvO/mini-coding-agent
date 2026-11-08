from pathlib import Path
from openai.types.chat import ChatCompletionFunctionToolParam


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

    # 读文件
    with target.open("r", encoding="utf-8") as file:
        text = file.read(max_chars + 1)

    result = {
        "ok": True,
        "result": {
            "path": target.relative_to(root).as_posix(),
            "content": text[:max_chars],
            "truncated": len(text) > max_chars,
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


FILE_HANDLER = {
    "read_file": read_file,
    "list_files": list_files,
}

