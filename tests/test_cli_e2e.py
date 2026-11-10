"""使用内存 HTTP 传输验证真实 SDK -> CLI -> 工具；不调用付费模型。"""

import json
import os
import subprocess
import sys
import io
from contextlib import contextmanager
from contextlib import redirect_stdout, redirect_stderr
from unittest.mock import patch

import httpx2 as httpx

from mini_coding_agent import model_client
from mini_coding_agent.cli import main

from mini_coding_agent.config import load_env_file


def calls(*items):
    return {
        "role": "assistant", "content": None,
        "tool_calls": [
            {
                "id": f"call_{i}_{name}", "type": "function",
                "function": {"name": name, "arguments": json.dumps(arguments)},
            }
            for i, (name, arguments) in enumerate(items)
        ],
    }


@contextmanager
def fake_api(responder):
    requests = []
    errors = []

    def handle(request):
        try:
            assert request.url.path == "/v1/chat/completions"
            body = json.loads(request.content)
            assert body["thinking"] == {"type": "disabled"}
            requests.append(body)
            message = responder(body, len(requests) - 1)
            response = {
                "id": "chat_test", "object": "chat.completion", "created": 0,
                "model": "offline-test",
                "choices": [{
                    "index": 0, "message": message,
                    "finish_reason": "tool_calls" if message.get("tool_calls") else "stop",
                }],
            }
            return httpx.Response(200, json=response)
        except Exception as exc:
            errors.append(repr(exc))
            return httpx.Response(400, json={"error": {"message": "test provider failure"}})

    original = model_client.OpenAI

    def client(*args, **kwargs):
        kwargs["http_client"] = httpx.Client(transport=httpx.MockTransport(handle))
        return original(*args, **kwargs)

    with patch.object(model_client, "OpenAI", client):
        yield "http://offline.test/v1", requests
    assert not errors, errors


def invoke(root, base_url=None, *options, task=None, input_text=""):
    argv = [
        "mini-coding-agent",
        "--workspace", str(root), *options,
    ]
    if base_url:
        argv += ["--base-url", base_url]
    if task is not None:
        argv.append(task)
    stdout, stderr = io.StringIO(), io.StringIO()
    with (
        patch.dict(os.environ, {"DEEPSEEK_API_KEY": "offline-test-key"}),
        patch.object(sys, "argv", argv),
        patch.object(sys, "stdin", io.StringIO(input_text)),
        redirect_stdout(stdout), redirect_stderr(stderr),
    ):
        try:
            code = main()
        except SystemExit as exc:
            code = exc.code
    return subprocess.CompletedProcess(argv, code, stdout.getvalue(), stderr.getvalue())


def tool_results(body):
    return [json.loads(m["content"]) for m in body["messages"] if m["role"] == "tool"]


def test_real_cli_repairs_project_and_runs_existing_tests(tmp_path):
    (tmp_path / "app.py").write_bytes(b"def total(a, b):\r\n    return a + b\r\n")
    (tmp_path / "notes.txt").write_text("user-owned change", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    checks = (
        "import unittest\nfrom app import total\n"
        "class TotalTest(unittest.TestCase):\n"
        "    def test_total(self): self.assertEqual(total(3, 4), 12)\n"
    )
    (tmp_path / "tests/test_app.py").write_text(checks, encoding="utf-8")
    command = {"argv": ["python", "-B", "-m", "unittest", "discover", "-s", "tests", "-q"]}

    def respond(body, step):
        results = tool_results(body)
        if step == 0:
            assert "create_file" in {t["function"]["name"] for t in body["tools"]}
            return calls(
                ("search_code", {"query": "def total", "glob": "*.py"}),
                ("read_file", {"path": "app.py"}),
            )
        if step == 1:
            assert results[0]["result"]["matches"][0]["path"] == "app.py"
            return calls(("run_command", command))
        if step == 2:
            assert results[-1]["result"]["returncode"] == 1
            version = results[1]["result"]["version_id"]
            return calls(("edit_file", {
                "path": "app.py", "base_version": version,
                "old_text": "return a + b", "new_text": "return a * b",
            }))
        if step == 3:
            assert results[-1]["result"]["changed"]
            return calls(("run_command", command))
        assert results[-1]["result"]["returncode"] == 0
        return {"role": "assistant", "content": "已修复总价计算，现有 unittest 检查通过。"}

    with fake_api(respond) as (url, requests):
        process = invoke(
            tmp_path, url, "--allow-edit", "--allow-commands", "--yes",
            task="修复总价计算，先运行现有检查，再做最小修改并重新检查。",
        )
    assert process.returncode == 0, process.stdout + process.stderr
    assert len(requests) == 5
    assert "退出码 1" in process.stdout and "退出码 0" in process.stdout
    assert (tmp_path / "app.py").read_bytes() == b"def total(a, b):\r\n    return a * b\r\n"
    assert (tmp_path / "notes.txt").read_text() == "user-owned change"
    assert (tmp_path / "tests/test_app.py").read_text() == checks


def test_cli_creates_and_runs_new_project(tmp_path):
    main = 'def greet():\n    return "Hello mini agent"\n\nprint(greet())\n'

    def respond(body, step):
        if step == 0:
            return calls(
                ("create_file", {"path": "app/main.py", "content": main}),
                ("create_file", {"path": "README.md", "content": "运行 python app/main.py\n"}),
            )
        if step == 1:
            assert all(r["ok"] for r in tool_results(body))
            return calls(("run_command", {"argv": ["python", "app/main.py"]}))
        result = tool_results(body)[-1]["result"]
        assert result["returncode"] == 0
        assert result["stdout"].strip() == "Hello mini agent"
        return {"role": "assistant", "content": "已创建应用并实际运行成功。"}

    with fake_api(respond) as (url, _):
        process = invoke(
            tmp_path, url, "--allow-edit", "--allow-commands", "--yes",
            task="创建一个可运行的小项目，并执行检查。",
        )
    assert process.returncode == 0, process.stdout + process.stderr
    assert (tmp_path / "app/main.py").read_text() == main
    assert (tmp_path / "README.md").is_file()


def test_interactive_conversation_reuses_history(tmp_path):
    def respond(body, step):
        tasks = [m["content"] for m in body["messages"] if m["role"] == "user"]
        assert tasks == (["先分析"] if step == 0 else ["先分析", "继续"])
        return {"role": "assistant", "content": "已收到这一轮。"}

    with fake_api(respond) as (url, requests):
        process = invoke(tmp_path, url, input_text="先分析\n继续\n/diff\n/clear\n/exit\n")
    assert process.returncode == 0, process.stdout + process.stderr
    assert len(requests) == 2
    assert "已清除会话上下文" in process.stdout


def test_cli_denial_stops_without_creating_files(tmp_path):
    with fake_api(lambda *_: calls(
        ("create_file", {"path": "refused.py", "content": "bad"}),
    )) as (url, requests):
        process = invoke(tmp_path, url, "--allow-edit", task="创建文件", input_text="n\n")
    assert process.returncode == 3
    assert len(requests) == 1 and list(tmp_path.iterdir()) == []


def test_help_and_invalid_workspace_do_not_need_api_key(tmp_path, monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    process = subprocess.run(
        [sys.executable, "-B", "-m", "mini_coding_agent", "--help"],
        capture_output=True, encoding="utf-8", errors="replace", timeout=10,
    )
    assert process.returncode == 0 and "--allow-commands" in process.stdout
    process = invoke(tmp_path / "missing", task="分析")
    assert process.returncode == 2 and "工作区" in process.stderr


def test_explicit_env_file_preserves_existing_values(tmp_path, monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "existing-key")
    monkeypatch.delenv("DEEPSEEK_MODEL", raising=False)
    path = tmp_path / "settings.env"
    path.write_text('DEEPSEEK_API_KEY="new-key"\nDEEPSEEK_MODEL=offline-model\n', encoding="utf-8")
    load_env_file(path)
    assert os.environ["DEEPSEEK_API_KEY"] == "existing-key"
    assert os.environ["DEEPSEEK_MODEL"] == "offline-model"
