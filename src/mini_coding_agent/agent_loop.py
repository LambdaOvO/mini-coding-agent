import json
from openai.types.chat import ChatCompletionMessageParam

from mini_coding_agent.model_client import request_model
from mini_coding_agent.tool_registry import execute_tool

def run_agent(prompt, tools, model, base_url, workspace_root, max_model_calls=5):
    messages: list[ChatCompletionMessageParam] = [
        {"role": "user", "content": prompt},
    ]

    for round_num in range(1, max_model_calls + 1):
        print(f"\n第 {round_num} 次请求大模型")
        print(f"messages: {messages}")

        replay = request_model(messages, tools, model, base_url)
        messages.append(replay)

        tool_calls = replay.get("tool_calls")

        if not tool_calls:
            return replay.get("content")

        for tool_call in tool_calls:
            function = tool_call["function"]
            name = function["name"]
            arguments = function["arguments"]

            print(f"工具调用请求 {name}: {arguments}")

            result = execute_tool(name, arguments, workspace_root)

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call["id"],
                "content": json.dumps(result, ensure_ascii=False),
            })

    return "达到模型调用次数上限，本次停止。"




