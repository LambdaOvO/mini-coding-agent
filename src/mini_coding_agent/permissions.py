"""审批是程序行为，不能由模型在参数中声称已经批准。"""

import os
import re


def display_text(text: str) -> str:
    # 去掉终端控制序列，并避免已知的环境凭据进入日志或模型上下文。
    text = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", text)
    text = "".join(c for c in text if c in "\n\r\t" or ord(c) >= 32)
    for name, value in os.environ.items():
        if len(value) >= 6 and any(word in name.upper() for word in ("KEY", "TOKEN", "SECRET", "PASSWORD")):
            text = text.replace(value, "[REDACTED]")
    return text


def ask_approval(action: str) -> bool:
    try:
        return input(f"{display_text(action)} [y/N] ").strip().lower() == "y"
    except EOFError:
        return False
