import json
from pathlib import Path

from mini_coding_agent.calculator import (
    TOOL_HANDLERS as CALCULATOR_HANDLERS,
    execute_tool as execute_calculation,
)

from mini_coding_agent.file_tools import FILE_HANDLER

def execute_tool(
        name: str,
        arguments_json: str,
        workspace_root: Path,
) -> dict[str, object]:

    if name in CALCULATOR_HANDLERS:
        return execute_calculation(name, arguments_json)

    if name in FILE_HANDLER:
        arguments = json.loads(arguments_json)
        handler = FILE_HANDLER[name]
        return handler(workspace_root, arguments["path"])

    return {"ok": False, "error": "未知工具"}

