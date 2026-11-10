import codecs
import json
import os
import subprocess

import pytest

from mini_coding_agent.file_tools import create_file, edit_file, list_files, read_file
from mini_coding_agent.search_tools import search_code
from mini_coding_agent.tool_registry import execute_tool
from mini_coding_agent.workspace import WorkspaceError, resolve_path


def test_read_page_edit_crlf_bom_and_last_newline(tmp_path):
    path = tmp_path / "code.py"
    before = codecs.BOM_UTF8 + b"def total(a, b):\r\n    return a + b\r\n"
    path.write_bytes(before)
    snapshot = read_file(tmp_path, "code.py", start_line=2, end_line=2)["result"]
    assert snapshot["content"] == "    return a + b\r\n"
    result = edit_file(
        tmp_path, "code.py", snapshot["version_id"],
        "def total(a, b):\n    return a + b",
        "def total(a, b):\n    return a * b",
        confirm=lambda _: True,
    )
    assert result["ok"]
    assert path.read_bytes() == before.replace(b"a + b", b"a * b")


def test_refusal_and_concurrent_editor_are_preserved(tmp_path):
    path = tmp_path / "code.py"
    path.write_text("old", encoding="utf-8")
    version = read_file(tmp_path, "code.py")["result"]["version_id"]
    result = edit_file(tmp_path, "code.py", version, "old", "new", confirm=lambda _: False)
    assert result["denied"] and path.read_text() == "old"

    def external_edit(_):
        path.write_text("user change", encoding="utf-8")
        return True

    with pytest.raises(WorkspaceError, match="确认期间"):
        edit_file(tmp_path, "code.py", version, "old", "new", confirm=external_edit)
    assert path.read_text() == "user change"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["code.py"]


def test_create_parents_and_never_overwrite(tmp_path):
    assert create_file(tmp_path, "app/main.py", "print(1)\n", confirm=lambda _: True)["ok"]
    with pytest.raises(WorkspaceError, match="已存在"):
        create_file(tmp_path, "app/main.py", "wrong", confirm=lambda _: True)
    assert (tmp_path / "app/main.py").read_text() == "print(1)\n"
    result = create_file(tmp_path, "refused.py", "", confirm=lambda _: False)
    assert result["denied"] and not (tmp_path / "refused.py").exists()


@pytest.mark.parametrize("path", [
    "../outside.py", "C:/Windows/test", "C:relative", "/absolute",
    ".git/config", ".venv/config", ".env", ".env.local",
    "dir/.aws/credentials", "file:stream", "NUL.txt", "foo.",
])
def test_workspace_rejects_protected_paths(tmp_path, path):
    with pytest.raises(WorkspaceError):
        resolve_path(tmp_path, path)


def test_search_filter_limit_and_secret_policy(tmp_path):
    (tmp_path / "app").mkdir()
    (tmp_path / "app/a.py").write_text("needle\nneedle\nneedle\n", encoding="utf-8")
    (tmp_path / ".env").write_text("needle", encoding="utf-8")
    (tmp_path / ".env.example").write_text("needle", encoding="utf-8")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules/x.py").write_text("needle", encoding="utf-8")
    result = search_code(tmp_path, "needle", glob="*.py", max_results=2)["result"]
    assert result["truncated"]
    assert [(item["path"], item["line"]) for item in result["matches"]] == [
        ("app/a.py", 1), ("app/a.py", 2),
    ]
    result = search_code(tmp_path, "needle")["result"]
    assert {item["path"] for item in result["matches"]} == {"app/a.py", ".env.example"}
    assert {item["path"] for item in list_files(tmp_path)["result"]["entries"]} == {
        "app", ".env.example",
    }


def test_large_file_is_read_in_pages(tmp_path):
    (tmp_path / "large.py").write_bytes(b"x = 1\n" * 12000)
    page = read_file(tmp_path, "large.py", start_line=11000, end_line=11002)["result"]
    assert page["content"] == "x = 1\n" * 3
    assert page["total_lines"] == 12000
    assert page["next_line"] == 11003


@pytest.mark.parametrize("arguments", ["{", "[]", '{"path": 12}', '{"path": "a", "surprise": 1}'])
def test_tool_errors_are_feedback_instead_of_crashes(tmp_path, arguments):
    assert not execute_tool("read_file", arguments, tmp_path)["ok"]
    assert not execute_tool("unknown", "{}", tmp_path)["ok"]


def test_link_cannot_read_outside(tmp_path):
    outside = tmp_path / "outside"
    root = tmp_path / "root"
    outside.mkdir()
    root.mkdir()
    (outside / "secret.py").write_text("private", encoding="utf-8")
    try:
        (root / "linked").symlink_to(outside, target_is_directory=True)
    except OSError:
        if os.name != "nt":
            raise
        # Windows 普通账户通常可以创建 junction，不需要符号链接特权。
        result = subprocess.run(
            ["cmd.exe", "/d", "/c", "mklink", "/J", str(root / "linked"), str(outside)],
            capture_output=True,
        )
        if result.returncode:
            pytest.skip("当前受限账户既不能创建 symlink，也不能创建 junction")
    response = execute_tool("read_file", json.dumps({"path": "linked/secret.py"}), root)
    assert not response["ok"]
