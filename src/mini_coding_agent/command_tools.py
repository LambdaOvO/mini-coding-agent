"""通用命令执行：先审批，持续收集输出，超时/取消后清理进程树。"""

import json
import os
import shutil
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from pathlib import Path

from openai.types.chat import ChatCompletionFunctionToolParam

from mini_coding_agent.permissions import ask_approval, display_text
from mini_coding_agent.processes import ProcessTree
from mini_coding_agent.workspace import WorkspaceError, resolve_path

RUN_COMMAND_TOOL: ChatCompletionFunctionToolParam = {
    "type": "function",
    "function": {
        "name": "run_command",
        "description": (
            "执行项目已有的测试、构建或其他短命令。argv 是完整参数数组，不是 Shell 命令行。"
            "程序会展示实际命令并请求用户确认。cwd 是工作区内的相对目录。"
            "python 使用 Agent 的解释器；如项目有独立虚拟环境，可传入其解释器路径。"
            "Windows 的 .cmd/.bat/.ps1 需显式指定 cmd.exe 或 powershell.exe 执行。"
            "退出后回收所属后台进程，不支持启动长期服务。returncode=0 只表示命令正常退出。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "argv": {
                    "type": "array", "items": {"type": "string"},
                    "minItems": 1, "maxItems": 64,
                    "description": '例如 ["python", "-m", "pytest", "-q"]',
                },
                "cwd": {"type": "string", "description": "默认工作区根目录 ."},
                "timeout": {"type": "integer", "minimum": 1, "maximum": 120},
            },
            "required": ["argv"],
            "additionalProperties": False,
        },
    },
}


def run_command(
    workspace_root: Path, argv: list[str], cwd: str = ".", timeout: int = 30,
    *, confirm: Callable[[str], bool] | None = None,
    pass_env: tuple[str, ...] = (),
) -> dict[str, object]:
    if not isinstance(argv, list) or not 1 <= len(argv) <= 64:
        raise WorkspaceError("argv 必须是包含 1～64 个参数的数组")
    if any(not isinstance(arg, str) or "\x00" in arg for arg in argv) or not argv[0].strip():
        raise WorkspaceError("命令参数必须是字符串，且可执行程序不能为空")
    if type(timeout) is not int or not 1 <= timeout <= 120:
        raise WorkspaceError("timeout 必须是 1～120 秒")
    root = workspace_root.resolve()
    working_directory = resolve_path(root, cwd)
    if not working_directory.is_dir():
        raise WorkspaceError("命令工作目录不存在")
    argv = list(argv)  # 将审批绑定到这份实际执行的参数。
    if argv[0].lower() in {"python", "python3", "python.exe"}:
        argv[0] = sys.executable
    elif argv[0].lower() in {"pytest", "pytest.exe"}:
        argv = [sys.executable, "-m", "pytest", *argv[1:]]
    elif "/" in argv[0] or "\\" in argv[0]:
        executable = Path(argv[0])
        if not executable.is_absolute():
            argv[0] = str((working_directory / executable).resolve())
    executable = shutil.which(argv[0]) or argv[0]
    if os.name == "nt" and Path(executable).suffix.lower() in {".cmd", ".bat", ".ps1"}:
        raise WorkspaceError("Windows 脚本请显式指定解释器，例如 cmd.exe /d /c npm test")
    print(display_text(f"\n命令：{json.dumps(argv, ensure_ascii=False)}\n目录：{working_directory}\n时限：{timeout} 秒"))
    if not (confirm or ask_approval)("执行上述本地命令？"):
        return {"ok": False, "denied": True, "error": "用户拒绝执行命令"}

    allowed_env = (
        "SYSTEMROOT", "WINDIR", "PATH", "PATHEXT", "TEMP", "TMP",
        "USERPROFILE", "HOMEDRIVE", "HOMEPATH", "HOME", "APPDATA",
        "LOCALAPPDATA", "LANG", "LC_ALL", "VIRTUAL_ENV",
    )
    child_env = {key: os.environ[key] for key in (*allowed_env, *pass_env) if key in os.environ}
    child_env.update(PYTHONUTF8="1", PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1")
    buffers = {"stdout": bytearray(), "stderr": bytearray()}
    output_limit = threading.Event()
    lock = threading.Lock()
    total_bytes = 0

    def collect(pipe, channel):
        nonlocal total_bytes
        try:
            while chunk := pipe.read(4096):
                with lock:
                    total_bytes += len(chunk)
                    available = max(0, 16000 - len(buffers[channel]))
                    buffers[channel].extend(chunk[:available])
                    if total_bytes > 2 * 1024 * 1024:
                        output_limit.set()
        finally:
            pipe.close()

    started = time.monotonic()
    process = None
    readers = []
    timed_out = False
    tree = ProcessTree()
    try:
        process = subprocess.Popen(
            argv, cwd=working_directory, env=child_env, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False,
            start_new_session=os.name != "nt",
            creationflags=(0x4 | subprocess.CREATE_NEW_PROCESS_GROUP) if os.name == "nt" else 0,
        )
        tree.attach(process)
        for channel in ("stdout", "stderr"):
            reader = threading.Thread(
                target=collect, args=(getattr(process, channel), channel), daemon=True,
            )
            reader.start()
            readers.append(reader)
        while process.poll() is None:
            if output_limit.is_set():
                break
            if time.monotonic() - started >= timeout:
                timed_out = True
                break
            time.sleep(0.03)
    finally:
        # 正常退出也关闭 Job/进程组，避免被调用程序留下后台子进程。
        tree.close(process)
        if process is not None:
            if process.poll() is None:
                process.kill()
            process.wait(timeout=5)
            for reader in readers:
                reader.join(timeout=3)
    return {
        "ok": True,
        "result": {
            "argv": argv, "cwd": working_directory.relative_to(root).as_posix(),
            "returncode": process.returncode,
            "stdout": display_text(buffers["stdout"].decode("utf-8", errors="replace")),
            "stderr": display_text(buffers["stderr"].decode("utf-8", errors="replace")),
            "timed_out": timed_out,
            "output_limited": output_limit.is_set(),
            "truncated": total_bytes > sum(len(value) for value in buffers.values()),
            "duration_seconds": round(time.monotonic() - started, 2),
        },
    }


# 保留早期教学示例的导入兼容；正式 CLI 使用 run_command。
CHECK_CODE = (
    "from demo import calculate_total\n"
    "actual = calculate_total(3, 4)\n"
    "print(f'actual={actual}, expected=12', flush=True)\n"
    "assert actual == 12, f'expected 12, got {actual!r}'\n"
)
RUN_CHECK_TOOL: ChatCompletionFunctionToolParam = {
    "type": "function",
    "function": {
        "name": "run_check", "description": "早期 demo.py 练习检查。",
        "parameters": {"type": "object", "properties": {}, "required": [], "additionalProperties": False},
    },
}


def run_check(workspace_root: Path) -> dict[str, object]:
    response = run_command(
        workspace_root, [sys.executable, "-B", "-X", "utf8", "-c", CHECK_CODE],
        timeout=10, confirm=lambda _: True,
    )
    if response.get("ok"):
        result = response["result"]
        result["passed"] = result["returncode"] == 0 and not result["timed_out"]
    return response
