"""工具目录、JSON 参数校验和实际分发。新增工具不需要改变 Agent Loop。"""

import json
from pathlib import Path

from mini_coding_agent.calculator import execute_tool as execute_calculation
from mini_coding_agent.command_tools import RUN_CHECK_TOOL, RUN_COMMAND_TOOL, run_check, run_command
from mini_coding_agent.file_tools import (
    CREATE_FILE_TOOL, EDIT_FILE_TOOL, LIST_FILES_TOOL, READ_FILE_TOOL,
    create_file, edit_file, list_files, read_file,
)
from mini_coding_agent.search_tools import SEARCH_CODE_TOOL, search_code
from mini_coding_agent.workspace import WorkspaceError


ALL_SCHEMAS = {
    schema["function"]["name"]: schema
    for schema in (
        LIST_FILES_TOOL, SEARCH_CODE_TOOL, READ_FILE_TOOL,
        CREATE_FILE_TOOL, EDIT_FILE_TOOL, RUN_COMMAND_TOOL, RUN_CHECK_TOOL,
    )
}


def get_tools(allow_edit: bool = False, allow_commands: bool = False) -> list[dict]:
    names = ["list_files", "search_code", "read_file"]
    if allow_edit:
        names += ["create_file", "edit_file"]
    if allow_commands:
        names += ["run_command"]
    return [ALL_SCHEMAS[name] for name in names]


def _validate(value, schema: dict, label: str = "参数"):
    kind = schema.get("type")
    if kind == "object":
        if not isinstance(value, dict):
            raise ValueError(f"{label}必须是 JSON 对象")
        properties = schema.get("properties", {})
        missing = set(schema.get("required", [])) - value.keys()
        if missing:
            raise ValueError(f"缺少参数：{', '.join(sorted(missing))}")
        if not schema.get("additionalProperties", True) and value.keys() - properties.keys():
            raise ValueError("包含工具不支持的参数")
        for key, item in value.items():
            if key in properties:
                _validate(item, properties[key], key)
    elif kind == "array":
        if not isinstance(value, list):
            raise ValueError(f"{label}必须是数组")
        if not schema.get("minItems", 0) <= len(value) <= schema.get("maxItems", 10000):
            raise ValueError(f"{label}的元素数量超出限制")
        for item in value:
            _validate(item, schema["items"], label)
    elif kind == "string":
        if not isinstance(value, str):
            raise ValueError(f"{label}必须是字符串")
        if not schema.get("minLength", 0) <= len(value) <= schema.get("maxLength", 2_000_000):
            raise ValueError(f"{label}的长度超出限制")
    elif kind == "integer":
        if type(value) is not int:
            raise ValueError(f"{label}必须是整数")
        if not schema.get("minimum", -10**12) <= value <= schema.get("maximum", 10**12):
            raise ValueError(f"{label}超出允许范围")


def execute_tool(
    name: str, arguments_json: str, workspace_root: Path,
    *, confirm=None, pass_env: tuple[str, ...] = (),
) -> dict[str, object]:
    if name in {"add", "multiply"}:
        return execute_calculation(name, arguments_json)
    if name not in ALL_SCHEMAS:
        return {"ok": False, "error": f"未知工具：{name}"}
    try:
        if not isinstance(arguments_json, str) or len(arguments_json) > 2_000_000:
            raise ValueError("工具参数必须是大小受限的 JSON 字符串")
        arguments = json.loads(arguments_json)
        _validate(arguments, ALL_SCHEMAS[name]["function"]["parameters"])
        handlers = {
            "list_files": lambda **kw: list_files(workspace_root, **kw),
            "read_file": lambda **kw: read_file(workspace_root, **kw),
            "search_code": lambda **kw: search_code(workspace_root, **kw),
            "create_file": lambda **kw: create_file(workspace_root, confirm=confirm, **kw),
            "edit_file": lambda **kw: edit_file(workspace_root, confirm=confirm, **kw),
            "run_command": lambda **kw: run_command(
                workspace_root, confirm=confirm, pass_env=pass_env, **kw,
            ),
            "run_check": lambda **kw: run_check(workspace_root),
        }
        return handlers[name](**arguments)
    except (ValueError, TypeError, OSError) as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
