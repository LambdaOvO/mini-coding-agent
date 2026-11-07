from openai import OpenAI
from openai.types.chat import (
    ChatCompletionFunctionToolParam,
    ChatCompletionMessageParam,
)
import json
from pathlib import Path

from mini_coding_agent.config import load_api_key
from mini_coding_agent.calculator import execute_tool


def save_message(
        path: Path,
        message: list[ChatCompletionMessageParam],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    message_json = json.dumps(message, ensure_ascii=False, indent=2)
    path.write_text(message_json, encoding="utf-8")


def load_messages(path: Path) -> list[ChatCompletionMessageParam]:
    messages_json = path.read_text(encoding="utf-8")
    messages = json.loads(messages_json)

    if type(messages) is not list:
        raise RuntimeError("保存的messages数据解析失败，顶层无法解析为列表")
    for message in messages:
        if type(message) is not dict:
            raise RuntimeError(f"保存的messages数据解析失败，数据 {message} 无法解析为字典")

    return messages


ADD_TOOL: ChatCompletionFunctionToolParam = {
    "type": "function",
    "function":{
        "name": "add",
        "description": "计算两个整数之和。",
        "parameters": {
            "type": "object",
            "properties": {
                "a": {"type": "integer", "description": "第一个整数"},
                "b": {"type": "integer", "description": "第二个整数"},
            },
            "required": ["a", "b"],
            "additionalProperties": False,
        },

    }
    
}


def main() -> None:
    message: list[ChatCompletionMessageParam] = [
        {"role": "user", "content": "请调用 add 工具计算 19 + 23。"},
    ]
    with OpenAI(
        api_key=load_api_key(),
        base_url="https://api.deepseek.com",
    ) as client:

        # 大模型第一次调用
        response = client.chat.completions.create(
            model="deepseek-flash",
            messages=message,
            tools=[ADD_TOOL],
            tool_choice={
                "type": "function",
                "function": {"name": "add"},
            },
            stream=False,
            extra_body={"thinking": {"type": "disabled"}},
        )

        if not response.choices:
            raise RuntimeError("模型响应中没有候选回复")

        if response.choices[0].finish_reason != "tool_calls":
            raise RuntimeError("未收到完整结束的工具调用响应")

        reply = response.choices[0].message

        if not reply.tool_calls:
            raise RuntimeError("本次实验没有收到工具调用请求")

        if len(reply.tool_calls) != 1:
            raise RuntimeError("多个工具调用不符合要求")

        print("模型返回的工具调用响应:\n", reply.model_dump_json(indent=2))

        tool_call = reply.tool_calls[0]

        if tool_call.type != "function":
            raise RuntimeError("不是函数工具调用不符合要求")

        message.append({
            "role": "assistant",
            "content": reply.content,
            "tool_calls": [
                {
                    "id": tool_call.id,
                    "type": "function",
                    "function": {
                        "name": tool_call.function.name,
                        "arguments": tool_call.function.arguments,
                    },
                }
            ],
        })

        # 本地工具调用(函数调用)
        result = execute_tool(
            tool_call.function.name,
            tool_call.function.arguments,
        )
        print("本地工具执行结果:", result)

        message.append({
            "role": "tool",
            "tool_call_id": tool_call.id,
            "content": json.dumps(result, ensure_ascii=False),
        })

        print(json.dumps(message, ensure_ascii=False, indent=2))

        # messages持久化

        project_path = Path(__file__).resolve().parents[2]

        snapshot_path = (
            project_path
            / "experiments-data"
            / "m0_tool_messages.json"
        )

        save_message(snapshot_path, message)
        restored_messages = load_messages(snapshot_path)

        assert restored_messages == message

        print("消息保存与恢复一致")
        print("消息保存位置:", snapshot_path)

        message = restored_messages

        # 大模型第二次调用
        final_response = client.chat.completions.create(
            model="deepseek-flash",
            messages=message,
            tools=[ADD_TOOL],
            tool_choice="none",
            stream=False,
            extra_body={"thinking": {"type": "disabled"}},
        )

        if not final_response.choices:
            raise RuntimeError("第二次模型调用没有响应数据")

        answer = final_response.choices[0].message.content

        if answer is None or not answer.strip():
            raise RuntimeError("模型没有返回有效回答")

        print("模型回答:", answer)



if __name__ == "__main__":
    main()

