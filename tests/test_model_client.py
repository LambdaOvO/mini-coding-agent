from unittest.mock import Mock
import pytest
from mini_coding_agent import model_client

def test_generate_rejects_whitespace_prompt(monkeypatch):
    fake_client = Mock()
    monkeypatch.setattr(model_client, "OpenAI", fake_client)

    with pytest.raises(ValueError, match="prompt"):
        model_client.generate(
            prompt="   ",
            model="deepseek",
            base_url="https://example.com"
        )

    fake_client.assert_not_called()

def test_generate_rejects_empty_prompt(monkeypatch):
    fake_client = Mock()
    monkeypatch.setattr(model_client, "OpenAI", fake_client)

    with pytest.raises(ValueError, match="prompt"):
        model_client.generate(
            prompt="",
            model="deepseek",
            base_url="https://example.com"
        )

    fake_client.assert_not_called()