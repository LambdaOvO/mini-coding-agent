import os
from openai import OpenAI
from openai.types.chat import (
    ChatCompletionMessage,
    ChatCompletionAssistantMessageParam,
    ChatCompletionFunctionToolParam,
    ChatCompletionMessageFunctionToolCallParam,
)
from mini_coding_agent.config import load_api_key
from openai.types.chat import  ChatCompletionMessageParam


def generate(prompt: str, model: str, base_url: str) -> str:

    if not prompt.strip():
        raise ValueError("prompt 不能为空")

    message: list[ChatCompletionMessageParam] = [
        {"role": "system", "content": "You are a helpful assistant"},
        {"role": "user", "content": prompt},
    ]

    with OpenAI(
        api_key=load_api_key(),
        base_url=base_url,
    ) as client:
        response = client.chat.completions.create(
            model=model,
            messages=message,
            stream=False,
            extra_body={"thinking": {"type": "disabled"}},
        )

        if not response.choices:
            raise RuntimeError("模型相应中没有候选回复")

        content = response.choices[0].message.content

        if content is None or not content.strip():
            raise RuntimeError("模型没有返回有效的文字回答")

        return content

def serialize_assistant(
        reply: ChatCompletionMessage
) -> ChatCompletionAssistantMessageParam:

    tool_calls: list[ChatCompletionMessageFunctionToolCallParam] = []

    if reply.tool_calls:
        for tool_call in reply.tool_calls:
            if tool_call.type != "function":
                raise RuntimeError("工具调用请求不为函数工具调用")
            tool_calls.append({
                "id": tool_call.id,
                "type": tool_call.type,
                "function": {
                    "name": tool_call.function.name,
                    "arguments": tool_call.function.arguments,
                }
            })



    assistant: ChatCompletionAssistantMessageParam = {
        "role": "assistant",
        "content": reply.content,
    }

    if tool_calls:
        assistant["tool_calls"] = tool_calls

    if reply.refusal:
        assistant["refusal"] = reply.refusal

    return assistant


def request_model(
        message: list[ChatCompletionMessageParam],
        tools: list[ChatCompletionFunctionToolParam],
        model: str,
        base_url: str,
) -> ChatCompletionAssistantMessageParam:

    if not message:
        raise RuntimeError("message为空")

    with OpenAI(
        api_key=load_api_key(),
        base_url=base_url,
    ) as client:
        response = client.chat.completions.create(
            model=model,
            messages=message,
            tools=tools,
            tool_choice="auto",
            stream=False,
            extra_body={"thinking": {"type": "disabled"}},
        )
        if not response or not response.choices:
            raise RuntimeError("模型无效响应或模型响应中没有候选回复")

        if response.choices[0].finish_reason not in ("stop", "tool_calls"):
            raise RuntimeError("模型响应回复的 finish_reason 不为 stop 或 tool_calls")

        replay = response.choices[0].message

        if replay.refusal:
            raise RuntimeError(f"模型拒绝回答: {replay.refusal}")

        if not replay.tool_calls and (not replay.content or not replay.content.strip()):
            raise RuntimeError("模型没有返回有效回复或工具调用")

        return serialize_assistant(replay)



