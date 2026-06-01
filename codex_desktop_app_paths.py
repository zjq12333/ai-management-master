from __future__ import annotations

import os
import re
import shutil
from pathlib import Path
from typing import Callable


def resolved_codex_desktop_exe(env: dict[str, str] | None = None) -> str | None:
    source = env or os.environ
    resolved = source.get("AI_STRATEGIST_CODEX_DESKTOP")
    if resolved and Path(resolved).exists():
        return resolved
    return None


def is_windowsapps_codex_path(value: str | os.PathLike[str] | None) -> bool:
    if not value:
        return False
    normalized = str(value).replace("/", "\\").lower()
    return "\\windowsapps\\openai.codex_" in normalized and normalized.endswith("\\app\\codex.exe")


def codex_desktop_env_path_candidates(env: dict[str, str] | None = None) -> list[Path]:
    source = env or os.environ
    env_candidates = [
        ("LOCALAPPDATA", "Programs/Codex/Codex.exe"),
        ("LOCALAPPDATA", "Codex/Codex.exe"),
        ("LOCALAPPDATA", "Programs/OpenAI Codex/Codex.exe"),
        ("LOCALAPPDATA", "Programs/OpenAI/Codex/Codex.exe"),
        ("PROGRAMFILES", "Codex/Codex.exe"),
        ("PROGRAMFILES", "OpenAI Codex/Codex.exe"),
        ("PROGRAMFILES", "OpenAI/Codex/Codex.exe"),
        ("PROGRAMFILES(X86)", "Codex/Codex.exe"),
        ("PROGRAMFILES(X86)", "OpenAI Codex/Codex.exe"),
        ("PROGRAMFILES(X86)", "OpenAI/Codex/Codex.exe"),
    ]
    paths: list[Path] = []
    for env_key, suffix in env_candidates:
        prefix = source.get(env_key)
        if prefix:
            paths.append(Path(prefix) / Path(suffix))
    return paths


def find_codex_desktop_appid(
    *,
    powershell_output: Callable[[str], str],
) -> str | None:
    try:
        out = powershell_output(
            "Get-StartApps | Where-Object AppID -Match 'OpenAI.Codex' | Select-Object -First 1 -ExpandProperty AppID"
        )
    except Exception:
        out = ""
    return out or None


def find_windowsapps_codex_desktop_exe(
    package_root: Path | None = None,
) -> str | None:
    root = package_root or Path(r"C:\Program Files\WindowsApps")
    if not root.exists():
        return None
    try:
        candidates = sorted(root.glob("OpenAI.Codex_*"), reverse=True)
    except OSError:
        return None
    for candidate in candidates:
        exe = candidate / "app" / "Codex.exe"
        try:
            if exe.exists():
                return str(exe)
        except OSError:
            return None
    return None


def find_codex_desktop_exe(
    *,
    find_windowsapps: Callable[[], str | None],
    env_candidates: Callable[[], list[Path]],
    query_registry: Callable[[], str | None],
    which: Callable[[str], str | None] | None = None,
) -> str | None:
    windowsapps_exe = find_windowsapps()
    if windowsapps_exe:
        return windowsapps_exe

    for candidate in env_candidates():
        try:
            if candidate.exists():
                return str(candidate)
        except OSError:
            continue

    registry_value = query_registry()
    if registry_value:
        return registry_value

    resolver = which or shutil.which
    for name in ("Codex.exe", "codex.exe"):
        path_value = resolver(name)
        if path_value and "windowsapps" not in path_value.lower():
            return path_value
    return None


def packaged_app_user_model_id_for_exe(exe: Path) -> str | None:
    package_dir = exe.parent.parent if exe.parent.name.lower() == "app" else exe.parent
    name = package_dir.name
    if not name.startswith("OpenAI.Codex_") or "__" not in name:
        return None
    identity_name = name.split("_", 1)[0]
    publisher_id = name.rsplit("__", 1)[1]
    if not publisher_id:
        return None
    return f"{identity_name}_{publisher_id}!App"


def query_reg_default_value(
    key_path: str,
    *,
    reg_query: Callable[[str], str | None],
) -> str | None:
    return reg_query(key_path)


def query_codex_desktop_from_registry(
    *,
    query_default_value: Callable[[str], str | None],
    find_uninstall_entry: Callable[[str], str | None],
) -> str | None:
    for reg_path in (
        r"HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\Codex.exe",
        r"HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\Codex.exe",
    ):
        value = query_default_value(reg_path)
        if value and Path(value).exists():
            return value

    for uninstall_root in (
        r"HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
        r"HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
    ):
        value = find_uninstall_entry(uninstall_root)
        if value:
            return value
    return None


_VERSION_RE = re.compile(r"OpenAI\.Codex_([0-9.]+)_")


def version_tuple(path: Path) -> tuple[int, ...]:
    match = _VERSION_RE.search(path.name)
    if not match:
        return ()
    return tuple(int(part) for part in match.group(1).split(".") if part.isdigit())
