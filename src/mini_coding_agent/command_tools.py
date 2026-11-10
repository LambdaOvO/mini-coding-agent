import os
import subprocess
import sys
from pathlib import Path

from openai.types.chat import ChatCompletionFunctionToolParam

CHECK_CODE = (
    "from demo import calculate_total\n"
    "actual = calculate_total(3, 4)\n"
    "print(f'actual={actual}, expected=12', flush=True)\n"
    "assert actual == 12, f'expected 12, got {actual!r}'\n"
)

RUN_CHECK_TOOL: ChatCompletionFunctionToolParam = {
    "type": "function",
    "function": {
        "name": "run_check",
        "description": (
            "针对calculate_total()函数，"
            "固定检查 calculate_total(3, 4) == 12，返回检查结果、退出码和输出"
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False,
        },
    },
}

def run_check(workspace_root: Path) -> dict[str, object]:
    # 子进程工作目录
    root = workspace_root.resolve()

    # 子进程简易环境变量
    child_env = {}
    for key in ("SYSTEMROOT", "WINDIR", "TEMP", "TMP"):
        if key in os.environ:
            child_env[key] = os.environ[key]

    # 通过子进程运行目标代码
    try:
        completed = subprocess.run(
            [sys.executable, "-B", "-X", "utf8", "-c", CHECK_CODE],
            cwd=root,
            env=child_env,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
            check=False,
            shell=False,
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "检查超时，超过 10 秒"}

    return {
        "ok": True,
        "result": {
            "passed": completed.returncode == 0,
            "returncode": completed.returncode,
            "stdout": completed.stdout[:4000],
            "stderr": completed.stderr[:4000],
            "truncated": (
                    len(completed.stdout) > 4000
                    or len(completed.stderr) > 4000
            ),
        },
    }