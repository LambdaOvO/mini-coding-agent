"""OpenAI-compatible Chat Completions 适配层；不执行任何本地工具。"""

from openai import APIConnectionError, APIStatusError, OpenAI
from openai.types.chat import (
    ChatCompletionAssistantMessageParam, ChatCompletionFunctionToolParam,
    ChatCompletionMessage, ChatCompletionMessageParam,
)

from mini_coding_agent.config import load_api_key


def serialize_assistant(reply: ChatCompletionMessage) -> ChatCompletionAssistantMessageParam:
    assistant = {"role": "assistant", "content": reply.content}
    if reply.tool_calls:
        calls = []
        seen = set()
        for call in reply.tool_calls:
            if call.type != "function" or not call.id or call.id in seen:
                raise RuntimeError("模型返回了不支持或重复的工具调用")
            seen.add(call.id)
            calls.append({
                "id": call.id, "type": "function",
                "function": {"name": call.function.name, "arguments": call.function.arguments},
            })
        assistant["tool_calls"] = calls
    if reply.refusal:
        assistant["refusal"] = reply.refusal
    return assistant


def request_model(
    message: list[ChatCompletionMessageParam],
    tools: list[ChatCompletionFunctionToolParam],
    model: str, base_url: str,
) -> ChatCompletionAssistantMessageParam:
    if not message:
        raise ValueError("message 不能为空")
    try:
        with OpenAI(
            api_key=load_api_key(), base_url=base_url,
            timeout=90.0, max_retries=1,
        ) as client:
            kwargs = {
                "model": model, "messages": message, "stream": False,
                "extra_body": {"thinking": {"type": "disabled"}},
            }
            if tools:
                kwargs.update(tools=tools, tool_choice="auto")
            response = client.chat.completions.create(**kwargs)
    except APIStatusError as exc:
        raise RuntimeError(f"模型服务返回 HTTP {exc.status_code}，请检查模型、密钥或服务状态") from exc
    except APIConnectionError as exc:
        raise RuntimeError("无法连接模型服务，请检查网络、代理和 base URL") from exc
    if response is None or not response.choices:
        raise RuntimeError("模型没有返回候选回复，请稍后重试")
    choice = response.choices[0]
    if choice.finish_reason not in {"stop", "tool_calls"}:
        raise RuntimeError(f"模型回复未完整结束：{choice.finish_reason}")
    reply = choice.message
    if reply.refusal:
        raise RuntimeError(f"模型拒绝回答：{reply.refusal}")
    if not reply.tool_calls and (not reply.content or not reply.content.strip()):
        raise RuntimeError("模型没有返回文字或工具调用")
    return serialize_assistant(reply)


def generate(prompt: str, model: str, base_url: str) -> str:
    """保留最初单轮问答接口，便于对照学习。"""
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("prompt 不能为空")
    reply = request_model([{"role": "user", "content": prompt}], [], model, base_url)
    content = reply.get("content")
    if not content:
        raise RuntimeError("模型没有返回有效文字")
    return content
