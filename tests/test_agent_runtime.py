import json

from mini_coding_agent.agent_loop import Agent


def call(name, arguments, identifier="call_1"):
    return {
        "id": identifier, "type": "function",
        "function": {"name": name, "arguments": json.dumps(arguments)},
    }


def test_readonly_blocks_hidden_write_and_preserves_multi_turn_history(tmp_path):
    received = []
    replies = iter([
        {"role": "assistant", "content": "", "tool_calls": [
            call("create_file", {"path": "bad.py", "content": "bad"}),
        ]},
        {"role": "assistant", "content": "当前为只读"},
        {"role": "assistant", "content": "我记得上轮"},
    ])

    def request(messages, *_):
        received.append(json.loads(json.dumps(messages)))
        return next(replies)

    agent = Agent(tmp_path, requester=request, emit=lambda _: None)
    assert agent.run("先分析").status == "completed"
    assert not (tmp_path / "bad.py").exists()
    assert not json.loads(received[1][-1]["content"])["ok"]
    agent.run("继续")
    assert [m["content"] for m in received[-1] if m["role"] == "user"] == ["先分析", "继续"]


def test_denial_seals_batch_and_never_executes_later_actions(tmp_path, monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _: "n")
    reply = {"role": "assistant", "content": "", "tool_calls": [
        call("create_file", {"path": "first.py", "content": "one"}, "one"),
        call("create_file", {"path": "second.py", "content": "two"}, "two"),
    ]}
    agent = Agent(tmp_path, allow_edit=True, requester=lambda *_: reply, emit=lambda _: None)
    assert agent.run("创建两个文件").status == "denied"
    assert list(tmp_path.iterdir()) == []
    assert [m["tool_call_id"] for m in agent.messages if m["role"] == "tool"] == ["one", "two"]
    assert json.loads(agent.messages[-1]["content"])["skipped"]


def test_tool_budget_covers_every_call_in_batch(tmp_path):
    reply = {"role": "assistant", "content": "", "tool_calls": [
        call("list_files", {}, "one"), call("list_files", {}, "two"),
    ]}
    agent = Agent(tmp_path, max_tool_calls=1, requester=lambda *_: reply, emit=lambda _: None)
    result = agent.run("查看")
    assert result.status == "limit" and result.tool_calls == 1
    assert len([m for m in agent.messages if m["role"] == "tool"]) == 2


def test_interrupt_seals_tools_and_keeps_session_usable(tmp_path, monkeypatch):
    def interrupt(_):
        raise KeyboardInterrupt

    monkeypatch.setattr("builtins.input", interrupt)
    reply = {"role": "assistant", "content": "", "tool_calls": [
        call("create_file", {"path": "file.py", "content": "one"}, "one"),
        call("list_files", {}, "two"),
    ]}
    agent = Agent(tmp_path, allow_edit=True, requester=lambda *_: reply, emit=lambda _: None)
    assert agent.run("创建文件").status == "cancelled"
    assert not (tmp_path / "file.py").exists()
    assert len([m for m in agent.messages if m["role"] == "tool"]) == 2
    agent.requester = lambda *_: {"role": "assistant", "content": "可以继续"}
    assert agent.run("继续").status == "completed"


def test_history_trimming_removes_whole_turns(tmp_path):
    agent = Agent(
        tmp_path, max_context_chars=6000, emit=lambda _: None,
        requester=lambda *_: {"role": "assistant", "content": "x" * 2600},
    )
    agent.run("第一轮")
    agent.run("第二轮")
    agent.run("第三轮")
    assert agent.messages[0]["role"] == "system"
    assert agent.messages[1]["role"] == "user"
    assert "第一轮" not in [m.get("content") for m in agent.messages]


def test_model_budget_stops_repeated_valid_calls(tmp_path):
    reply = {"role": "assistant", "content": "", "tool_calls": [call("list_files", {})]}
    agent = Agent(tmp_path, max_model_calls=2, requester=lambda *_: reply, emit=lambda _: None)
    result = agent.run("重复查看")
    assert result.status == "limit"
    assert result.model_calls == 2 and result.tool_calls == 2
