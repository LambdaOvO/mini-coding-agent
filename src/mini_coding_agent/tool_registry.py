import json
from pathlib import Path

from mini_coding_agent.calculator import (
    TOOL_HANDLERS as CALCULATOR_HANDLERS,
    execute_tool as execute_calculation,
)

from mini_coding_agent.file_tools import FILE_HANDLER, edit_file
from mini_coding_agent.command_tools import run_check

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

    if name == "edit_file":
        arguments = json.loads(arguments_json)

        return edit_file(
            workspace_root=workspace_root,
            path=arguments["path"],
            base_version=arguments["base_version"],
            old_text=arguments["old_text"],
            new_text=arguments["new_text"],
        )

    if name == "run_check":
        return run_check(workspace_root)

    return {"ok": False, "error": "未知工具"}

