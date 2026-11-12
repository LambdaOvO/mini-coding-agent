"""可选的 Windows 凭据保存；密钥不写入项目文件或普通配置文件。"""

import ctypes
import os
from ctypes import wintypes


TARGET_NAME = "mini-coding-agent/deepseek-api-key"
CRED_TYPE_GENERIC = 1
CRED_PERSIST_LOCAL_MACHINE = 2
ERROR_NOT_FOUND = 1168


class CredentialStoreError(OSError):
    pass


class _Credential(ctypes.Structure):
    _fields_ = [
        ("Flags", wintypes.DWORD),
        ("Type", wintypes.DWORD),
        ("TargetName", wintypes.LPWSTR),
        ("Comment", wintypes.LPWSTR),
        ("LastWritten", wintypes.FILETIME),
        ("CredentialBlobSize", wintypes.DWORD),
        ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)),
        ("Persist", wintypes.DWORD),
        ("AttributeCount", wintypes.DWORD),
        ("Attributes", ctypes.c_void_p),
        ("TargetAlias", wintypes.LPWSTR),
        ("UserName", wintypes.LPWSTR),
    ]


def available() -> bool:
    return os.name == "nt"


def _windows_api():
    if not available():
        raise CredentialStoreError("当前平台不支持内置的 Windows 凭据保存")
    api = ctypes.WinDLL("Advapi32.dll", use_last_error=True)
    api.CredReadW.argtypes = [
        wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
        ctypes.POINTER(ctypes.POINTER(_Credential)),
    ]
    api.CredReadW.restype = wintypes.BOOL
    api.CredWriteW.argtypes = [ctypes.POINTER(_Credential), wintypes.DWORD]
    api.CredWriteW.restype = wintypes.BOOL
    api.CredFree.argtypes = [ctypes.c_void_p]
    api.CredFree.restype = None
    return api


def load_saved_key() -> str | None:
    if not available():
        return None
    api = _windows_api()
    pointer = ctypes.POINTER(_Credential)()
    if not api.CredReadW(TARGET_NAME, CRED_TYPE_GENERIC, 0, ctypes.byref(pointer)):
        code = ctypes.get_last_error()
        if code == ERROR_NOT_FOUND:
            return None
        raise CredentialStoreError(f"读取 Windows 凭据失败，错误码 {code}")
    try:
        credential = pointer.contents
        raw = ctypes.string_at(credential.CredentialBlob, credential.CredentialBlobSize)
        return raw.decode("utf-8").strip() or None
    except UnicodeError as exc:
        raise CredentialStoreError("已保存的密钥格式无效，请使用 /key 重新设置") from exc
    finally:
        api.CredFree(pointer)


def save_key(key: str) -> None:
    raw = key.encode("utf-8")
    if not raw or len(raw) > 2560:
        raise ValueError("密钥内容为空或超过 Windows 凭据大小上限")
    api = _windows_api()
    buffer = ctypes.create_string_buffer(raw)
    credential = _Credential()
    credential.Type = CRED_TYPE_GENERIC
    credential.TargetName = TARGET_NAME
    credential.Comment = "Mini Coding Agent DeepSeek API Key"
    credential.CredentialBlobSize = len(raw)
    credential.CredentialBlob = ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte))
    credential.Persist = CRED_PERSIST_LOCAL_MACHINE
    credential.UserName = "DeepSeek"
    if not api.CredWriteW(ctypes.byref(credential), 0):
        code = ctypes.get_last_error()
        raise CredentialStoreError(f"保存 Windows 凭据失败，错误码 {code}")
