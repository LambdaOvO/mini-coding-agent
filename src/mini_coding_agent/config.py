import os
import getpass
import sys
import warnings
from pathlib import Path

from mini_coding_agent import credential_store


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


def _read_hidden_key() -> str:
    if not sys.stdin.isatty():
        raise ValueError("当前输入不是交互式终端，无法隐藏输入密钥；请使用环境变量或 --env-file")
    try:
        # getpass 在无法隐藏输入时默认会退回明文输入；这里明确拒绝这种回退。
        with warnings.catch_warnings():
            warnings.simplefilter("error", getpass.GetPassWarning)
            return getpass.getpass("DeepSeek API Key（输入隐藏，留空取消）：").strip()
    except (getpass.GetPassWarning, EOFError) as exc:
        raise ValueError("当前终端无法隐藏密钥输入，请使用 PowerShell、Windows Terminal 或 --env-file") from exc


def configure_api_key() -> str | None:
    """在本地终端设置密钥，绝不把输入当作用户任务或发送给模型。"""
    key = _read_hidden_key()
    if not key:
        print("已取消密钥设置，原配置保持不变。")
        return None
    if any(character.isspace() or ord(character) < 32 for character in key) or len(key.encode("utf-8")) > 2560:
        raise ValueError("密钥不能包含空白或控制字符，且长度不能超过 2560 字节")

    saved = False
    if credential_store.available():
        try:
            answer = input("保存到当前用户的 Windows 凭据管理器，下次自动读取？[y/N] ")
        except EOFError:
            answer = ""
        if answer.strip().lower() == "y":
            try:
                credential_store.save_key(key)
                saved = True
            except OSError as exc:
                print(f"未能保存密钥（{exc}），仍可用于本次会话。")
    os.environ["DEEPSEEK_API_KEY"] = key
    if saved:
        print("已更新当前会话密钥，并保存到 Windows 凭据管理器。")
    else:
        print("已更新当前会话密钥；未改动已保存的配置，退出后本次输入不再保留。")
    return key


def ensure_api_key() -> str:
    """启动时按有效环境变量 -> Windows 保存项 -> 隐藏输入的顺序取得密钥。"""
    try:
        return load_api_key()
    except ValueError:
        pass
    try:
        saved = credential_store.load_saved_key()
    except OSError as exc:
        print(f"未能读取已保存的密钥（{exc}），请在终端重新输入。")
        saved = None
    if saved:
        os.environ["DEEPSEEK_API_KEY"] = saved
        return saved
    print("尚未配置 DeepSeek 密钥，请在程序内输入。")
    key = configure_api_key()
    if key is None:
        raise ValueError("未设置 DeepSeek 密钥，启动已取消")
    return key
