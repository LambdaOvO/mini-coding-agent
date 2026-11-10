import ctypes
import os
import sys
import time
import pytest

from mini_coding_agent.command_tools import run_command


def test_command_exit_output_cwd_and_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "do-not-pass-this-key")
    code = (
        "import os,sys; print(os.getcwd()); print('中文'); "
        "print(os.getenv('DEEPSEEK_API_KEY', 'missing')); "
        "print('diagnostic', file=sys.stderr); sys.exit(7)"
    )
    result = run_command(tmp_path, ["python", "-c", code], confirm=lambda _: True)["result"]
    assert result["returncode"] == 7
    assert "中文" in result["stdout"] and "missing" in result["stdout"]
    assert "do-not-pass-this-key" not in result["stdout"]
    assert str(tmp_path) in result["stdout"]
    assert result["stderr"].strip() == "diagnostic"


def test_denial_never_starts_program(tmp_path):
    marker = tmp_path / "marker"
    result = run_command(
        tmp_path, ["python", "-c", "open('marker','w').write('bad')"],
        confirm=lambda _: False,
    )
    assert result["denied"] and not marker.exists()


def test_output_is_bounded(tmp_path):
    result = run_command(
        tmp_path, ["python", "-c", "print('x' * (3 * 1024 * 1024))"],
        confirm=lambda _: True,
    )["result"]
    assert result["truncated"] and result["output_limited"]
    assert len(result["stdout"]) <= 16000


def _alive(pid):
    if os.name != "nt":
        try:
            os.kill(pid, 0)
            return True
        except ProcessLookupError:
            return False
    from ctypes import wintypes
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel.WaitForSingleObject.restype = wintypes.DWORD
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.OpenProcess(0x100000, False, pid)
    if not handle:
        return False
    try:
        return kernel.WaitForSingleObject(handle, 0) == 258
    finally:
        kernel.CloseHandle(handle)


def test_timeout_reaps_descendants(tmp_path):
    child = "import time; from pathlib import Path; time.sleep(2); Path('escaped').write_text('bad')"
    code = (
        "import subprocess,sys,time; "
        f"p=subprocess.Popen([sys.executable,'-c',{child!r}]); "
        "print(p.pid, flush=True); time.sleep(20)"
    )
    result = run_command(tmp_path, ["python", "-c", code], timeout=1, confirm=lambda _: True)["result"]
    assert result["timed_out"]
    pid = int(result["stdout"].strip())
    for _ in range(30):
        if not _alive(pid):
            break
        time.sleep(0.03)
    assert not _alive(pid), f"命令子进程 {pid} 未回收"
    time.sleep(1.2)
    assert not (tmp_path / "escaped").exists()


def test_keyboard_interrupt_reaps_running_process(tmp_path, monkeypatch):
    from mini_coding_agent import command_tools

    original_popen = command_tools.subprocess.Popen
    original_sleep = time.sleep
    started = []

    def record(*args, **kwargs):
        process = original_popen(*args, **kwargs)
        started.append(process.pid)
        return process

    interrupted = False

    def interrupt_once(seconds):
        nonlocal interrupted
        if not interrupted:
            interrupted = True
            raise KeyboardInterrupt
        original_sleep(seconds)

    monkeypatch.setattr(command_tools.subprocess, "Popen", record)
    monkeypatch.setattr(command_tools.time, "sleep", interrupt_once)
    with pytest.raises(KeyboardInterrupt):
        run_command(
            tmp_path, ["python", "-c", "import time; time.sleep(20)"],
            confirm=lambda _: True,
        )
    assert started and not _alive(started[0])
