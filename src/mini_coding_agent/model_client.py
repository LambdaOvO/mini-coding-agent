import os
from openai import OpenAI
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
