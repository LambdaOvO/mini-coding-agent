import ctypes
import io
import os
import sys
import warnings

import pytest

from mini_coding_agent import config, credential_store


@pytest.fixture(autouse=True)
def isolate_key(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "")
    monkeypatch.delenv("DEEPSEEK_API_KEY")


def test_environment_key_does_not_read_store_or_prompt(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "  environment-key  ")

    def unexpected():
        pytest.fail("已有环境密钥时不应读取凭据或要求输入")

    monkeypatch.setattr(credential_store, "load_saved_key", unexpected)
    monkeypatch.setattr(config, "_read_hidden_key", unexpected)
    assert config.ensure_api_key() == "environment-key"


def test_saved_key_is_loaded_into_current_process(monkeypatch, capsys):
    key = "saved-test-secret"
    monkeypatch.setattr(credential_store, "load_saved_key", lambda: key)
    assert config.ensure_api_key() == key
    assert config.load_api_key() == key
    assert key not in capsys.readouterr().out


def test_setup_then_next_start_restores_saved_key(monkeypatch, capsys):
    key = "new-test-secret"
    saved = []
    monkeypatch.setattr(config, "_read_hidden_key", lambda: key)
    monkeypatch.setattr(credential_store, "available", lambda: True)
    monkeypatch.setattr(credential_store, "save_key", saved.append)
    monkeypatch.setattr(credential_store, "load_saved_key", lambda: saved[-1] if saved else None)
    monkeypatch.setattr("builtins.input", lambda _: "y")
    assert config.ensure_api_key() == key
    assert saved == [key]
    os.environ.pop("DEEPSEEK_API_KEY")
    monkeypatch.setattr(config, "_read_hidden_key", lambda: pytest.fail("应直接恢复保存项"))
    assert config.ensure_api_key() == key
    assert key not in capsys.readouterr().out


def test_session_only_does_not_save(monkeypatch, capsys):
    key = "session-only-secret"
    monkeypatch.setattr(config, "_read_hidden_key", lambda: key)
    monkeypatch.setattr(credential_store, "available", lambda: True)
    monkeypatch.setattr(credential_store, "save_key", lambda _: pytest.fail("用户未同意保存"))
    monkeypatch.setattr("builtins.input", lambda _: "n")
    assert config.configure_api_key() == key
    assert os.environ["DEEPSEEK_API_KEY"] == key
    assert key not in capsys.readouterr().out


def test_save_failure_keeps_key_usable_this_session(monkeypatch, capsys):
    key = "temporary-test-secret"
    monkeypatch.setattr(config, "_read_hidden_key", lambda: key)
    monkeypatch.setattr(credential_store, "available", lambda: True)
    monkeypatch.setattr("builtins.input", lambda _: "y")

    def fail(_):
        raise credential_store.CredentialStoreError("保存权限不足")

    monkeypatch.setattr(credential_store, "save_key", fail)
    assert config.configure_api_key() == key
    assert config.load_api_key() == key
    output = capsys.readouterr().out
    assert "未能保存" in output and key not in output


def test_empty_or_interrupted_input_preserves_original_key(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "original-test-key")
    monkeypatch.setattr(config, "_read_hidden_key", lambda: "")
    assert config.configure_api_key() is None
    assert config.load_api_key() == "original-test-key"

    def interrupt():
        raise KeyboardInterrupt

    monkeypatch.setattr(config, "_read_hidden_key", interrupt)
    with pytest.raises(KeyboardInterrupt):
        config.configure_api_key()
    assert config.load_api_key() == "original-test-key"


def test_noninteractive_input_never_reads_plaintext(monkeypatch):
    monkeypatch.setattr(sys, "stdin", io.StringIO("must-not-read-this\n"))
    monkeypatch.setattr(config.getpass, "getpass", lambda _: pytest.fail("不能退回明文输入"))
    with pytest.raises(ValueError, match="交互式终端"):
        config._read_hidden_key()


def test_getpass_warning_is_an_error_before_fallback(monkeypatch):
    class Terminal(io.StringIO):
        def isatty(self):
            return True

    monkeypatch.setattr(sys, "stdin", Terminal())

    def cannot_hide(_):
        warnings.warn("would echo", config.getpass.GetPassWarning)
        pytest.fail("不应该执行明文回退")

    monkeypatch.setattr(config.getpass, "getpass", cannot_hide)
    with pytest.raises(ValueError, match="无法隐藏"):
        config._read_hidden_key()
    assert "DEEPSEEK_API_KEY" not in os.environ


@pytest.mark.skipif(os.name != "nt", reason="Windows 凭据结构")
def test_native_credential_blob_roundtrip_without_touching_user_store(monkeypatch):
    saved = {}
    allocations = []
    freed = []

    class FakeAPI:
        def CredWriteW(self, pointer, flags):
            record = pointer._obj
            assert record.Type == credential_store.CRED_TYPE_GENERIC
            assert record.Persist == credential_store.CRED_PERSIST_LOCAL_MACHINE
            saved[record.TargetName] = ctypes.string_at(record.CredentialBlob, record.CredentialBlobSize)
            return True

        def CredReadW(self, target, kind, flags, destination):
            if target not in saved:
                ctypes.set_last_error(credential_store.ERROR_NOT_FOUND)
                return False
            raw = saved[target]
            buffer = ctypes.create_string_buffer(raw)
            record = credential_store._Credential()
            record.CredentialBlobSize = len(raw)
            record.CredentialBlob = ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte))
            allocations.append((record, buffer))
            output = ctypes.cast(
                destination, ctypes.POINTER(ctypes.POINTER(credential_store._Credential)),
            )
            output[0] = ctypes.pointer(record)
            return True

        def CredFree(self, pointer):
            freed.append(True)

    monkeypatch.setattr(credential_store, "_windows_api", lambda: FakeAPI())
    assert credential_store.load_saved_key() is None
    credential_store.save_key("native-blob-test-secret")
    assert credential_store.load_saved_key() == "native-blob-test-secret"
    assert freed == [True]
