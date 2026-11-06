import pytest

from mini_coding_agent.calculator import execute_tool

def test_execute_tool_correct():
    name = "add"
    arguments_json = '{"a":19, "b":23}'
    response = execute_tool(name, arguments_json)
    assert response == {"ok": True, "result": 42}

@pytest.mark.parametrize(
    "name,arguments_json",
    [
        ("xxx", '{"a": 19, "b": 23}'),  # 未知工具
        ("add", "{"),  # JSON 格式错误
        ("add", "[]"),  # 解析结果不是字典
        ("add", '{"a": 19}'),  # 缺少参数
        ("add", '{"a": 19, "b": 23, "c": 1}'),  # 多余参数
        ("add", '{"a": "19", "b": 23}'),  # 字符串
        ("add", '{"a": 1.5, "b": 23}'),  # 浮点数
        ("add", '{"a": true, "b": 23}'),  # 布尔值
    ]
)
def test_execute_tool_rejects_invalid_request(name, arguments_json):
    response = execute_tool(name, arguments_json)

    assert response["ok"] is False
    assert response["error"]