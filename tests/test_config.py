import pytest

from mini_coding_agent.config import load_api_key

def test_load_api_key_strips_whitespace(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "  test_api_key ")

    result = load_api_key()

    assert result == "test_api_key"

def test_load_api_key_missing(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    with pytest.raises(ValueError, match="DEEPSEEK_API_KEY"):
        load_api_key()


def test_load_api_key_empty(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "")

    with pytest.raises(ValueError, match="DEEPSEEK_API_KEY"):
        load_api_key()

def test_load_api_key_whitespace(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "    ")

    with pytest.raises(ValueError, match="DEEPSEEK_API_KEY"):
        load_api_key()