import json

def add(a: int, b: int) -> int:
    return a + b


def execute_tool(name: str, arguments_json: str) -> dict[str, object]:
    if name != "add":
        return {"ok": False, "error": f"未知工具 {name}"}

    try:
        arguments = json.loads(arguments_json)
    except json.JSONDecodeError:
        return {"ok": False, "error": f"arguments_json:{arguments_json}，json 解析失败"}

    if type(arguments) is not dict:
        return {"ok": False, "error": f"arguments_json:{arguments_json} 参数类型错误，无法解析为dict"}

    if set(arguments) != {"a", "b"}:
        return {"ok": False, "error": "参数必须只能包含 a 和 b"}

    if type(arguments["a"]) is not int or type(arguments["b"]) is not int:
        return {"ok": False, "error": f"arguments_json:{arguments_json} 中a或b参数不是整数类型"}

    result = add(arguments["a"], arguments["b"])

    return {"ok": True, "result": result}

