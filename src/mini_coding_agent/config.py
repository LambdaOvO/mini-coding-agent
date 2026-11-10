import os
from pathlib import Path


def load_env_file(path: Path) -> None:
    """只在用户显式传 --env-file 时加载，不执行内容、不覆盖已有环境变量。"""
    for number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:]
        name, separator, value = line.partition("=")
        name = name.strip()
        if not separator or not name.isidentifier():
            raise ValueError(f"环境文件第 {number} 行格式错误，应为 NAME=value")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        os.environ.setdefault(name, value)

def load_api_key() -> str:

    api_key = os.getenv("DEEPSEEK_API_KEY")

    if api_key is None:
        raise ValueError("缺少环境变量 DEEPSEEK_API_KEY")

    api_key = api_key.strip()

    if api_key == "":
        raise ValueError("DEEPSEEK_API_KEY 环境变量不能为空")

    return api_key
