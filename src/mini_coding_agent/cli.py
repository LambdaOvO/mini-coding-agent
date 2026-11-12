"""CLI 只处理用户输入和展示；Agent 实例负责保存对话并调度工具。"""

import argparse
import os
import sys
from pathlib import Path

from mini_coding_agent.agent_loop import Agent
from mini_coding_agent.config import configure_api_key, ensure_api_key, load_env_file
from mini_coding_agent.permissions import display_text


def positive_int(value: str) -> int:
    number = int(value)
    if not 1 <= number <= 500:
        raise argparse.ArgumentTypeError("请输入 1～500 之间的整数")
    return number


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mini-coding-agent",
        description="本地 mini coding agent：搜索、读取、创建、编辑代码，并执行经批准的项目命令。",
        allow_abbrev=False,
    )
    parser.add_argument("task", nargs="?", help="单次任务；省略时进入交互式对话")
    parser.add_argument("--workspace", type=Path, default=Path.cwd(), help="工作区，默认为当前目录")
    parser.add_argument("--allow-edit", action="store_true", help="启用文件创建和编辑，默认每次审批")
    parser.add_argument("--allow-commands", action="store_true", help="启用本地命令，每条命令默认审批")
    parser.add_argument("--yes", action="store_true", help="自动批准已启用的操作，仅用于你信任的项目")
    parser.add_argument("--env-file", type=Path, help="显式加载环境变量文件，不覆盖已有环境变量")
    parser.add_argument("--model", help="模型名称，默认 DEEPSEEK_MODEL 或 deepseek-flash")
    parser.add_argument("--base-url", help="兼容 API 地址，默认 DEEPSEEK_BASE_URL 或 https://api.deepseek.com")
    parser.add_argument("--max-model-calls", type=positive_int, default=30, help="每轮最多请求模型次数，默认 30")
    parser.add_argument("--max-tool-calls", type=positive_int, default=80, help="每轮最多执行工具次数，默认 80")
    parser.add_argument("--pass-env", action="append", default=[], metavar="NAME", help="显式允许项目命令继承一个环境变量，可重复")
    parser.add_argument("--debug", action="store_true", help="显示经过脱敏的工具参数")
    return parser


def main() -> int:
    # Windows 控制台使用 Unicode；管道和日志也统一为 UTF-8，避免系统代码页造成乱码。
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = build_parser()
    args = parser.parse_args()
    try:
        root = args.workspace.expanduser().resolve()
    except (OSError, RuntimeError, ValueError):
        parser.error("工作区路径无效")
    if not root.is_dir():
        parser.error("工作区必须是已经存在的目录")
    if args.task is not None and not args.task.strip():
        parser.error("任务不能为空")
    if args.yes and not (args.allow_edit or args.allow_commands):
        parser.error("--yes 需要配合 --allow-edit 或 --allow-commands")
    try:
        if args.env_file:
            load_env_file(args.env_file.expanduser().resolve())
        ensure_api_key()
    except KeyboardInterrupt:
        print("\n已取消密钥设置。")
        return 130
    except (ValueError, OSError) as exc:
        print(display_text(f"配置错误：{exc}"), file=sys.stderr)
        return 2

    agent = Agent(
        root,
        model=args.model or os.getenv("DEEPSEEK_MODEL", "deepseek-flash"),
        base_url=args.base_url or os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        allow_edit=args.allow_edit, allow_commands=args.allow_commands,
        auto_approve=args.yes, max_model_calls=args.max_model_calls,
        max_tool_calls=args.max_tool_calls, pass_env=tuple(args.pass_env), debug=args.debug,
    )
    print(f"工作区：{root}")
    print(
        "权限：读取/搜索"
        + ("，创建/编辑" if args.allow_edit else "")
        + ("，执行命令" if args.allow_commands else "")
        + ("（自动批准）" if args.yes else "（有副作用的操作逐次确认）")
    )
    if args.allow_commands:
        print("本地命令使用当前账户权限运行；工作区限制不等于操作系统沙箱，请使用可信项目。")

    def run(task):
        result = agent.run(task)
        print(f"\n{result.message}")
        print(f"\n[本轮] 状态={result.status}，模型请求={result.model_calls}，工具调用={result.tool_calls}")
        return result

    if args.task is not None:
        result = run(args.task)
        return {"completed": 0, "denied": 3, "cancelled": 130}.get(result.status, 1)

    print("输入任务开始。命令：/help、/key、/diff、/clear、/exit。Ctrl+C 停止当前轮，Ctrl+D/Ctrl+Z 退出。")
    while True:
        try:
            task = input("\n你> ").strip()
        except EOFError:
            print()
            return 0
        except KeyboardInterrupt:
            print("\n使用 /exit 退出。")
            continue
        if not task:
            continue
        if task in {"/exit", "/quit"}:
            return 0
        if task == "/help":
            print("/key 隐藏输入并更换密钥；/diff 查看修改；/clear 清除上下文（不撤销文件）；/exit 退出。")
        elif task == "/key":
            try:
                configure_api_key()
            except KeyboardInterrupt:
                print("\n已中断密钥设置。")
            except (ValueError, OSError) as exc:
                print(f"密钥设置失败：{exc}")
        elif task.split(maxsplit=1)[0] == "/key":
            print("请只输入 /key，然后在隐藏提示中输入密钥，不要把密钥写在命令后面。")
        elif task == "/clear":
            agent.clear()
            print("已清除会话上下文和读取版本记录，磁盘文件保持当前状态。")
        elif task == "/diff":
            if not agent.changes:
                print("本会话没有由工具完成的文件修改。")
            for change in agent.changes:
                print(display_text(change.get("diff", "")))
        else:
            run(task)
