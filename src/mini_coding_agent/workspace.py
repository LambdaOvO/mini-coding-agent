"""所有文件工具共用的工作区边界；这里不负责执行模型或命令。"""

from pathlib import Path, PureWindowsPath


MAX_FILE_BYTES = 1024 * 1024
IGNORED_DIRECTORIES = {
    ".git", ".venv", "venv", ".idea", ".ssh", ".aws", ".azure",
    ".codex", ".docker", ".kube", ".gnupg", "node_modules", "__pycache__",
    ".pytest_cache", ".mypy_cache", ".ruff_cache", "build", "dist", "target",
}
SECRET_FILES = {
    ".npmrc", ".pypirc", ".netrc", "credentials", "credentials.json",
    "secrets.json", "secrets.toml", "secrets.yaml", "secrets.yml",
    "id_rsa", "id_ecdsa", "id_ed25519",
}


class WorkspaceError(ValueError):
    pass


def is_secret_file(name: str) -> bool:
    name = name.lower()
    if name in {".env.example", ".env.sample", ".env.template"}:
        return False
    return (
        name == ".env" or name.startswith(".env.")
        or name in SECRET_FILES
        or Path(name).suffix in {".pem", ".key", ".p12", ".pfx", ".kdbx"}
    )


def resolve_path(workspace_root: Path, path: str) -> Path:
    """只接受根目录内的相对路径，拒绝链接、凭据、设备名和 NTFS ADS。"""
    if not isinstance(path, str) or not path.strip():
        raise WorkspaceError("path 必须是非空的工作区相对路径")
    relative = Path(path.replace("\\", "/"))
    if relative.anchor or PureWindowsPath(path).drive or ":" in path:
        raise WorkspaceError("请使用工作区内的相对路径")
    root = workspace_root.resolve()
    current = root
    for part in relative.parts:
        if part == "..":
            raise WorkspaceError("路径不能包含 ..")
        base = part.split(".")[0].upper()
        devices = {"CON", "PRN", "AUX", "NUL"} | {
            f"{prefix}{i}" for prefix in ("COM", "LPT") for i in range(1, 10)
        }
        if part.rstrip(" .") != part or base in devices:
            raise WorkspaceError("不支持 Windows 设备名或以空格、点结尾的路径")
        if part.lower() in IGNORED_DIRECTORIES or is_secret_file(part):
            raise WorkspaceError(f"该路径受保护，不能通过文件工具访问：{part}")
        current = current / part
        if current.is_symlink() or current.is_junction():
            raise WorkspaceError("不访问符号链接或 Windows junction")
    target = current.resolve()
    if not target.is_relative_to(root):
        raise WorkspaceError("路径超出工作区范围")
    return target


def read_text_bytes(target: Path) -> tuple[bytes, str]:
    if not target.is_file():
        raise WorkspaceError("目标不是已经存在的普通文件")
    with target.open("rb") as file:
        raw = file.read(MAX_FILE_BYTES + 1)
    if len(raw) > MAX_FILE_BYTES:
        raise WorkspaceError("当前支持的单文件大小上限为 1 MiB")
    if b"\x00" in raw:
        raise WorkspaceError("不支持读取二进制文件")
    try:
        return raw, raw.decode("utf-8-sig")
    except UnicodeError as exc:
        raise WorkspaceError("文件不是 UTF-8 文本") from exc
