import os

def load_api_key() -> str:

    api_key = os.getenv("DEEPSEEK_API_KEY")

    if api_key is None:
        raise ValueError("缺少环境变量 DEEPSEEK_API_KEY")

    api_key = api_key.strip()

    if api_key == "":
        raise ValueError("DEEPSEEK_API_KEY 环境变量不能为空")

    return api_key