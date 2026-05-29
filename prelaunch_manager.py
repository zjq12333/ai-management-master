from __future__ import annotations

import json
import os
import re
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import uuid
import ctypes
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

import codex_desktop_app_paths as desktop_app_paths
import codex_desktop_launcher as desktop_launcher


@dataclass
class ProviderProfile:
    key: str
    name: str
    base_url: str
    wire_api: str
    env_key: str
    requires_openai_auth: bool = False
    experimental_bearer_token: str = ""


@dataclass
class ProviderConfigResult:
    config_path: str
    backup_path: str
    mode: str
    target_model_provider: str
    verified_model_provider: str


@dataclass
class PrelaunchEvidence:
    config_path: str
    config_model_provider: str | None
    hybrid_provider_configured: bool
    hybrid_provider_key: str | None
    auth_mode: str | None
    threadripper_available: bool
    threadripper_target_provider: str | None
    rows_needing_reconcile: int | None
    provider_distribution: dict[str, int]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


CODEX_DESKTOP_PACKAGE_FAMILY = "OpenAI.Codex_2p2nqsd0c76g0"
CODEX_DESKTOP_NOTICE_STATE_FILE = "ai-strategist-prelaunch-notice-state.json"
CDP_NOT_READY_ERROR_FRAGMENT = "CDP did not come up"
CDP_WAIT_TIMEOUT_SECONDS = 25.0
ENHANCER_READY_STABLE_SECONDS = 3.0


def windows_system_tool(name: str) -> str:
    system_root = os.environ.get("SystemRoot")
    if system_root:
        candidate = Path(system_root) / "System32" / name
        if candidate.exists():
            return str(candidate)
    return name


def codex_desktop_user_data_dir() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return (
            Path(local_app_data)
            / "Packages"
            / CODEX_DESKTOP_PACKAGE_FAMILY
            / "LocalCache"
            / "Roaming"
            / "Codex"
        )
    return (
        Path.home()
        / "AppData"
        / "Local"
        / "Packages"
        / CODEX_DESKTOP_PACKAGE_FAMILY
        / "LocalCache"
        / "Roaming"
        / "Codex"
    )


def prepare_codex_desktop_notice_state() -> dict[str, object]:
    """
    Best-effort prelaunch preparation for Codex Desktop quota/usage nudges.

    This intentionally does not patch Codex Desktop application code and does
    not inspect current quota. It records an explicit local prelaunch state
    marker before every launch attempt so the launcher has a fixed place to add
    future Codex local-state keys when the desktop client exposes stable keys.
    Failure must not block launching Codex.
    """
    if is_codex_or_cli_running():
        return {
            "ok": False,
            "skipped": True,
            "reason": "codex_running",
            "error": "Codex Desktop or codex CLI is running.",
        }

    user_data_dir = codex_desktop_user_data_dir()
    leveldb_dir = user_data_dir / "Local Storage" / "leveldb"
    marker_path = user_data_dir / CODEX_DESKTOP_NOTICE_STATE_FILE
    payload: dict[str, object] = {
        "prepared_at": datetime.now().astimezone().isoformat(),
        "managed_by": "AI Strategist",
        "policy": "prelaunch_quota_notice_suppression",
        "quota_detection_used": False,
        "codex_desktop_user_data_dir": str(user_data_dir),
        "leveldb_dir": str(leveldb_dir),
        "known_codex_notice_keys": {
            "statsig_feature": "workspace_owner_usage_nudge",
            "free_go_gate_param": "enable_free_go_usage_settings",
            "pricing_page_gate_param": "show_logged_in_pricing_page",
        },
    }

    try:
        user_data_dir.mkdir(parents=True, exist_ok=True)
        marker_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return {
            "ok": True,
            "skipped": False,
            "method": "marker",
            "marker_path": str(marker_path),
            "leveldb_present": leveldb_dir.exists(),
        }
    except Exception as exc:
        return {
            "ok": False,
            "skipped": True,
            "reason": "write_failed",
            "error": str(exc),
            "marker_path": str(marker_path),
        }

def auth_json_path_from_codex_home(codex_home: Path) -> Path:
    return codex_home.expanduser() / "auth.json"


def read_auth_mode(codex_home: Path) -> str | None:
    """
    Returns the persisted auth mode from auth.json if available.

    Expected values include (not exhaustive): "apikey", "chatgpt".
    """
    path = auth_json_path_from_codex_home(codex_home)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    mode = data.get("auth_mode")
    if isinstance(mode, str) and mode.strip():
        return mode.strip()
    return None


def config_path_from_codex_home(codex_home: Path) -> Path:
    return codex_home.expanduser() / "config.toml"


def settings_path_from_codex_home(codex_home: Path) -> Path:
    return codex_home.expanduser() / "codexmate" / "settings.json"


def load_enhancer_settings(codex_home: Path) -> dict[str, object]:
    path = settings_path_from_codex_home(codex_home)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def chat_info_move_enabled(codex_home: Path) -> bool:
    enhancer = load_enhancer_settings(codex_home).get("enhancer")
    return bool(isinstance(enhancer, dict) and enhancer.get("chatInfoMoveEnabled"))


def one_click_handoff_enabled(codex_home: Path) -> bool:
    enhancer = load_enhancer_settings(codex_home).get("enhancer")
    return bool(isinstance(enhancer, dict) and enhancer.get("oneClickHandoffEnabled"))


def hide_official_quota_notice_enabled(codex_home: Path) -> bool:
    enhancer = load_enhancer_settings(codex_home).get("enhancer")
    return bool(isinstance(enhancer, dict) and enhancer.get("hideOfficialQuotaNoticeEnabled"))


def must_install_plugins_enabled(codex_home: Path) -> bool:
    enhancer = load_enhancer_settings(codex_home).get("enhancer")
    return bool(isinstance(enhancer, dict) and enhancer.get("mustInstallPluginsEnabled"))


def bundled_plugin_cache_root(codex_home: Path, plugin_name: str) -> Path:
    return codex_home / "plugins" / "cache" / "openai-bundled" / plugin_name


def bundled_plugin_cache_path(codex_home: Path, plugin_name: str) -> Path:
    root = bundled_plugin_cache_root(codex_home, plugin_name)
    latest = root / "latest"
    if latest.exists():
        return latest
    versions = [
        path
        for path in root.iterdir()
        if path.is_dir() and (path / ".codex-plugin" / "plugin.json").exists()
    ] if root.exists() else []
    versions.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    return versions[0] if versions else latest


def chrome_plugin_cache_path(codex_home: Path) -> Path:
    return bundled_plugin_cache_path(codex_home, "chrome")


def chrome_plugin_locally_ready(codex_home: Path) -> bool:
    scripts = chrome_plugin_cache_path(codex_home) / "scripts"
    check_extension = scripts / "check-extension-installed.js"
    check_native_host = scripts / "check-native-host-manifest.js"
    if not check_extension.exists() or not check_native_host.exists():
        return False
    for script in (check_extension, check_native_host):
        result = subprocess.run(
            ["node", str(script)],
            cwd=str(scripts),
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            return False
    return True


def bundled_plugin_locally_ready(codex_home: Path, plugin_name: str) -> bool:
    plugin_path = bundled_plugin_cache_path(codex_home, plugin_name)
    return (plugin_path / ".codex-plugin" / "plugin.json").exists()


def ensure_plugin_enabled_in_config(config_path: Path, plugin_id: str) -> bool:
    text = config_path.read_text(encoding="utf-8") if config_path.exists() else ""
    header = f'[plugins."{plugin_id}"]'
    if header in text:
        next_text = re.sub(
            rf'(\[plugins\."{re.escape(plugin_id)}"\]\s*)enabled\s*=\s*false',
            rf'\1enabled = true',
            text,
            count=1,
        )
        if next_text != text:
            config_path.write_text(next_text, encoding="utf-8")
            return True
        header_match = re.search(
            rf'(\[plugins\."{re.escape(plugin_id)}"\]\s*)',
            text,
            flags=re.MULTILINE,
        )
        if not header_match:
            return False
        section_start = header_match.end()
        next_section = re.search(r"\n\[", text[section_start:])
        section_end = section_start + next_section.start() if next_section else len(text)
        section = text[section_start:section_end]
        if re.search(r"(?m)^\s*enabled\s*=", section):
            return False
        next_text = f"{text[:section_start]}enabled = true\n{text[section_start:]}"
        config_path.write_text(next_text, encoding="utf-8")
        return True
    separator = "" if text.endswith("\n") or not text else "\n"
    config_path.write_text(f'{text}{separator}\n{header}\nenabled = true\n', encoding="utf-8")
    return True


def ensure_must_install_local_plugins(codex_home: Path) -> dict[str, object]:
    if not must_install_plugins_enabled(codex_home):
        return {"enabled": False, "changed": False, "plugins": []}
    config_path = config_path_from_codex_home(codex_home)
    raw = config_path.read_text(encoding="utf-8") if config_path.exists() else ""
    plugins_to_enable: list[str] = []
    readiness_errors: list[str] = []
    if bundled_plugin_locally_ready(codex_home, "browser"):
        plugins_to_enable.append("browser@openai-bundled")
    else:
        readiness_errors.append("browser_plugin_not_locally_ready")
    if chrome_plugin_locally_ready(codex_home):
        plugins_to_enable.append("chrome@openai-bundled")

    if not plugins_to_enable:
        return {"enabled": True, "changed": False, "plugins": [], "errors": readiness_errors}

    changed_plugins = [
        plugin_id
        for plugin_id in plugins_to_enable
        if ensure_plugin_enabled_in_config(config_path, plugin_id)
    ]
    changed = bool(changed_plugins)
    backup_path = ""
    if changed:
        backup = config_path.with_name(
            f"config.toml.backup_ai_manager_must_install_{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        )
        backup.write_text(raw, encoding="utf-8")
        backup_path = str(backup)
    return {
        "enabled": True,
        "changed": changed,
        "plugins": changed_plugins,
        "available_plugins": plugins_to_enable,
        "errors": readiness_errors,
        "backup_path": backup_path,
    }


def enhancer_enabled(codex_home: Path) -> bool:
    return (
        chat_info_move_enabled(codex_home)
        or one_click_handoff_enabled(codex_home)
        or hide_official_quota_notice_enabled(codex_home)
        or must_install_plugins_enabled(codex_home)
    )


def read_model_provider(raw: str) -> str | None:
    match = re.search(r'(?m)^model_provider\s*=\s*"([^"]+)"\s*$', raw)
    if match:
        return match.group(1).strip()
    return None


def upsert_model_provider(raw: str, provider: str) -> str:
    line = f'model_provider = "{provider}"'
    if re.search(r'(?m)^model_provider\s*=\s*".*?"\s*$', raw):
        return re.sub(r'(?m)^model_provider\s*=\s*".*?"\s*$', line, raw, count=1)

    anchor = re.search(r'(?m)^model_reasoning_effort\s*=\s*".*?"\s*$', raw)
    if anchor:
        index = anchor.end()
        return raw[:index] + "\n" + line + raw[index:]
    return line + "\n" + raw


def upsert_provider_block(raw: str, profile: ProviderProfile) -> str:
    block_lines = [f"[model_providers.{profile.key}]"]
    block_lines.append(f'name = "{profile.name}"')
    block_lines.append(f'base_url = "{profile.base_url}"')
    block_lines.append(f'wire_api = "{profile.wire_api}"')
    if profile.requires_openai_auth:
        block_lines.append("requires_openai_auth = true")
        token = profile.experimental_bearer_token.strip()
        if token:
            block_lines.append(f'experimental_bearer_token = "{token}"')
    else:
        if profile.env_key.strip():
            block_lines.append(f'env_key = "{profile.env_key.strip()}"')
        block_lines.append("supports_websockets = false")
    block = "\n".join(block_lines) + "\n"

    pattern = re.compile(rf"(?ms)^\[model_providers\.{re.escape(profile.key)}\]\n.*?(?=^\[|\Z)")
    if pattern.search(raw):
        return pattern.sub(block, raw, count=1)
    if not raw.endswith("\n"):
        raw += "\n"
    return raw + "\n" + block


def _read_toml_string(block: str, key: str) -> str:
    match = re.search(rf'(?m)^{re.escape(key)}\s*=\s*"([^"]*)"\s*$', block)
    return match.group(1).strip() if match else ""


def _read_toml_bool(block: str, key: str) -> bool:
    match = re.search(rf"(?m)^{re.escape(key)}\s*=\s*(true|false)\s*$", block, re.IGNORECASE)
    return bool(match and match.group(1).lower() == "true")


def parse_provider_profiles(raw: str) -> dict[str, ProviderProfile]:
    profiles: dict[str, ProviderProfile] = {}
    for match in re.finditer(r"(?ms)^\[model_providers\.([^\]]+)\]\n(.*?)(?=^\[|\Z)", raw):
        key = match.group(1).strip()
        block = match.group(2)
        profiles[key] = ProviderProfile(
            key=key,
            name=_read_toml_string(block, "name") or key,
            base_url=_read_toml_string(block, "base_url"),
            wire_api=_read_toml_string(block, "wire_api") or "responses",
            env_key=_read_toml_string(block, "env_key"),
            requires_openai_auth=_read_toml_bool(block, "requires_openai_auth"),
            experimental_bearer_token=_read_toml_string(block, "experimental_bearer_token"),
        )
    return profiles


def load_provider_profile_from_config(codex_home: Path, mode: str) -> ProviderProfile:
    config_path = config_path_from_codex_home(codex_home)
    if not config_path.exists():
        raise RuntimeError(f"Config file not found: {config_path}")

    raw = config_path.read_text(encoding="utf-8")
    current_provider = read_model_provider(raw)
    profiles = parse_provider_profiles(raw)
    if not profiles:
        raise RuntimeError("No model provider profiles found in config.toml.")

    candidate_keys: list[str] = []
    if current_provider and current_provider.lower() != "openai":
        candidate_keys.append(current_provider)
    candidate_keys.extend(["lac", "cliproxy"])
    candidate_keys.extend(key for key in profiles if key.lower() != "openai")

    seen: set[str] = set()
    candidates = [key for key in candidate_keys if not (key in seen or seen.add(key))]
    if mode == "hybrid":
        for key in candidates:
            profile = profiles.get(key)
            if profile and profile.requires_openai_auth and profile.experimental_bearer_token.strip():
                return profile
        raise RuntimeError(
            "No hybrid-capable provider found in config.toml. Expected requires_openai_auth=true and experimental_bearer_token."
        )

    for key in candidates:
        profile = profiles.get(key)
        if profile:
            return profile

    raise RuntimeError("No non-official provider found in config.toml for API launch mode.")


def configure_provider_for_launch(
    codex_home: Path,
    mode: str,
    profile: ProviderProfile | None = None,
) -> ProviderConfigResult:
    config_path = config_path_from_codex_home(codex_home)
    if not config_path.exists():
        raise RuntimeError(f"Config file not found: {config_path}")

    raw = config_path.read_text(encoding="utf-8")
    backup = config_path.with_name(
        f"config.toml.backup_ai_manager_{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    )
    backup.write_text(raw, encoding="utf-8")

    if mode == "official":
        target = "openai"
        updated = upsert_model_provider(raw, target)
    elif mode in ("api", "hybrid"):
        if profile is None:
            raise RuntimeError("Provider profile is required for API launch mode.")
        if mode == "hybrid":
            if not profile.requires_openai_auth:
                raise RuntimeError("Hybrid mode requires requires_openai_auth=true.")
            if not profile.experimental_bearer_token.strip():
                raise RuntimeError("Hybrid mode requires experimental_bearer_token.")
        target = profile.key
        updated = upsert_model_provider(raw, target)
        updated = upsert_provider_block(updated, profile)
    else:
        raise RuntimeError(f"Unsupported launch mode: {mode}")

    config_path.write_text(updated, encoding="utf-8")
    verified_raw = config_path.read_text(encoding="utf-8")
    verified_provider = read_model_provider(verified_raw)
    if verified_provider != target:
        raise RuntimeError(
            f"Config verification failed: expected model_provider={target}, got {verified_provider!r}"
        )

    return ProviderConfigResult(
        config_path=str(config_path),
        backup_path=str(backup),
        mode=mode,
        target_model_provider=target,
        verified_model_provider=verified_provider,
    )


def threadripper_command() -> str | None:
    resolved = os.environ.get("AI_STRATEGIST_THREADRIPPER")
    if resolved and Path(resolved).exists():
        return resolved
    return None


def subprocess_window_options() -> dict[str, object]:
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = 0
    return {
        "startupinfo": startupinfo,
        "creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0),
    }


def gui_launch_options() -> dict[str, object]:
    """
    GUI apps like Codex Desktop should not inherit hidden-console flags.
    """
    return {}


def has_proxy_environment(env: dict[str, str] | None = None) -> bool:
    source = env or os.environ
    return any(
        source.get(name)
        for name in ("HTTPS_PROXY", "HTTP_PROXY", "ALL_PROXY", "https_proxy", "http_proxy", "all_proxy")
    )


def local_proxy_url() -> str | None:
    for port in (7897, 7890, 10809, 10808, 1080):
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                return f"http://127.0.0.1:{port}"
        except OSError:
            continue
    return None


def codex_process_environment() -> dict[str, str]:
    env = os.environ.copy()
    if has_proxy_environment(env):
        return env
    proxy = local_proxy_url()
    if proxy:
        env.setdefault("HTTP_PROXY", proxy)
        env.setdefault("HTTPS_PROXY", proxy)
        env.setdefault("ALL_PROXY", proxy)
    return env


def python_runtime_supports_enhancer_modules(python_executable: Path) -> bool:
    try:
        result = subprocess.run(
            [
                str(python_executable),
                "-c",
                "import requests, websocket",
            ],
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=8,
            **subprocess_window_options(),
        )
    except Exception:
        return False
    return result.returncode == 0


def resolved_python_runtime_executable() -> str:
    configured = os.environ.get("AI_STRATEGIST_PYTHON_RUNTIME") or os.environ.get("AI_STRATEGIST_PYTHON")
    runtime_path = Path(configured) if configured else Path(sys.executable)
    if configured and not runtime_path.exists():
        runtime_path = Path(sys.executable)
    if configured and runtime_path.exists() and not python_runtime_supports_enhancer_modules(runtime_path):
        runtime_path = Path(sys.executable)
    if os.name == "nt":
        pythonw = runtime_path.with_name("pythonw.exe")
        if pythonw.exists():
            return str(pythonw)
    return str(runtime_path)


def enhancer_runtime_launch_options() -> dict[str, object]:
    options: dict[str, object] = {
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "close_fds": True,
    }
    if os.name == "nt":
        options["creationflags"] = (
            getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            | getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
            | getattr(subprocess, "CREATE_NO_WINDOW", 0)
        )
    return options


def enhancer_ready_stable_seconds() -> float:
    raw = os.environ.get("AI_STRATEGIST_ENHANCER_READY_STABLE_SECONDS", "").strip()
    if raw:
        try:
            return max(0.0, min(5.0, float(raw)))
        except ValueError:
            pass
    return ENHANCER_READY_STABLE_SECONDS


def _can_bind_loopback_port(port: int) -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            if os.name == "nt" and hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
                probe.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            probe.bind(("127.0.0.1", port))
            return True
    except OSError:
        return False


def _find_available_loopback_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        if os.name == "nt" and hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def select_windows_loopback_port(requested_port: int) -> int:
    if os.name != "nt" or _can_bind_loopback_port(requested_port):
        return requested_port
    return _find_available_loopback_port()


def parse_remote_debugging_port(arguments: list[str]) -> int | None:
    for argument in arguments:
        if argument.startswith("--remote-debugging-port="):
            try:
                return int(argument.split("=", 1)[1].strip())
            except ValueError:
                return None
    return None


def normalize_remote_debugging_args(arguments: list[str]) -> tuple[list[str], int | None]:
    requested_port = parse_remote_debugging_port(arguments)
    if requested_port is None:
        return list(arguments), None

    selected_port = select_windows_loopback_port(requested_port)
    if selected_port == requested_port:
        return list(arguments), selected_port

    rewritten: list[str] = []
    requested_origin = f"http://127.0.0.1:{requested_port}"
    selected_origin = f"http://127.0.0.1:{selected_port}"
    for argument in arguments:
        if argument.startswith("--remote-debugging-port="):
            rewritten.append(f"--remote-debugging-port={selected_port}")
        elif argument.startswith("--remote-allow-origins="):
            rewritten.append(argument.replace(requested_origin, selected_origin))
        else:
            rewritten.append(argument)
    return rewritten, selected_port


def parse_threadripper_status(text: str) -> dict[str, object]:
    parsed: dict[str, object] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("Target provider:"):
            parsed["target_provider"] = line.split(":", 1)[1].strip()
        elif line.startswith("Rows needing reconcile:"):
            match = re.search(r"(\d+)$", line)
            if match:
                parsed["rows_needing_reconcile"] = int(match.group(1))
    return parsed


def run_threadripper_status(codex_home: Path) -> dict[str, object] | None:
    command = threadripper_command()
    if not command:
        return None
    process = subprocess.run(
        [command, "--codex-home", str(codex_home), "status"],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        **subprocess_window_options(),
    )
    if process.returncode != 0:
        return {
            "target_provider": None,
            "rows_needing_reconcile": None,
            "error": (process.stderr or process.stdout).strip() or f"exit code {process.returncode}",
        }
    parsed = parse_threadripper_status(process.stdout)
    parsed["raw"] = process.stdout
    return parsed


def get_threads_provider_distribution(codex_home: Path) -> dict[str, int]:
    db_path = codex_home.expanduser() / "state_5.sqlite"
    if not db_path.exists():
        return {}
    con = sqlite3.connect(db_path)
    try:
        rows = con.execute(
            """
            select coalesce(model_provider, '<null>') as provider, count(*) as total
            from threads
            group by coalesce(model_provider, '<null>')
            order by total desc, provider asc
            """
        ).fetchall()
    finally:
        con.close()
    return {str(provider): int(total) for provider, total in rows}


def collect_prelaunch_evidence(codex_home: Path) -> PrelaunchEvidence:
    codex_home = codex_home.expanduser()
    config_path = config_path_from_codex_home(codex_home)
    raw = config_path.read_text(encoding="utf-8") if config_path.exists() else ""
    status = run_threadripper_status(codex_home)
    try:
        hybrid_provider_key = load_provider_profile_from_config(codex_home, "hybrid").key
    except Exception:
        hybrid_provider_key = None
    return PrelaunchEvidence(
        config_path=str(config_path),
        config_model_provider=read_model_provider(raw),
        hybrid_provider_configured=hybrid_provider_key is not None,
        hybrid_provider_key=hybrid_provider_key,
        auth_mode=read_auth_mode(codex_home),
        threadripper_available=threadripper_command() is not None,
        threadripper_target_provider=(status or {}).get("target_provider"),  # type: ignore[arg-type]
        rows_needing_reconcile=(status or {}).get("rows_needing_reconcile"),  # type: ignore[arg-type]
        provider_distribution=get_threads_provider_distribution(codex_home),
    )


def evidence_as_json(codex_home: Path) -> str:
    return json.dumps(collect_prelaunch_evidence(codex_home).to_dict(), ensure_ascii=False)


def _powershell_output(command: str) -> str:
    process = subprocess.run(
        [windows_system_tool("WindowsPowerShell\\v1.0\\powershell.exe"), "-NoProfile", "-Command", command],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        **subprocess_window_options(),
    )
    if process.returncode != 0:
        raise RuntimeError((process.stderr or process.stdout).strip() or f"exit code {process.returncode}")
    return (process.stdout or "").strip()


def find_codex_desktop_appid() -> str | None:
    return desktop_app_paths.find_codex_desktop_appid(powershell_output=_powershell_output)


def resolved_codex_desktop_exe() -> str | None:
    return desktop_app_paths.resolved_codex_desktop_exe(os.environ)


def codex_desktop_env_path_candidates() -> list[Path]:
    return desktop_app_paths.codex_desktop_env_path_candidates(os.environ)


def query_reg_default_value(key_path: str) -> str | None:
    if os.name != "nt":
        return None
    try:
        output = subprocess.run(
            [windows_system_tool("reg.exe"), "query", key_path, "/ve"],
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            **subprocess_window_options(),
        )
    except Exception:
        return None
    if output.returncode != 0:
        return None
    for raw_line in (output.stdout or "").splitlines():
        line = raw_line.strip()
        if "REG_SZ" in line or "REG_EXPAND_SZ" in line:
            parts = re.split(r"\s{2,}", line, maxsplit=2)
            if len(parts) >= 3 and parts[2].strip():
                return parts[2].strip()
    return None


def find_codex_in_uninstall_entries(root: str) -> str | None:
    if os.name != "nt":
        return None
    script = (
        f"Get-ChildItem 'Registry::{root}' -ErrorAction SilentlyContinue | ForEach-Object {{ "
        "$item = Get-ItemProperty $_.PSPath -ErrorAction SilentlyContinue; "
        "if ($item.DisplayName -like '*Codex*' -and $item.InstallLocation) { Write-Output $item.InstallLocation } "
        "}}"
    )
    try:
        output = _powershell_output(script)
    except Exception:
        return None
    for raw_line in output.splitlines():
        location = raw_line.strip()
        if not location:
            continue
        candidate = Path(location) / "Codex.exe"
        if candidate.exists():
            return str(candidate)
    return None


def query_codex_desktop_from_registry() -> str | None:
    return desktop_app_paths.query_codex_desktop_from_registry(
        query_default_value=query_reg_default_value,
        find_uninstall_entry=find_codex_in_uninstall_entries,
    )


def find_windowsapps_codex_desktop_exe() -> str | None:
    return desktop_app_paths.find_windowsapps_codex_desktop_exe()


def find_codex_desktop_exe() -> str | None:
    return desktop_app_paths.find_codex_desktop_exe(
        find_windowsapps=find_windowsapps_codex_desktop_exe,
        env_candidates=codex_desktop_env_path_candidates,
        query_registry=query_codex_desktop_from_registry,
        which=shutil.which,
    )


def packaged_app_user_model_id_for_exe(exe: Path) -> str | None:
    return desktop_app_paths.packaged_app_user_model_id_for_exe(exe)


class _GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", ctypes.c_uint32),
        ("Data2", ctypes.c_uint16),
        ("Data3", ctypes.c_uint16),
        ("Data4", ctypes.c_ubyte * 8),
    ]

    def __init__(self, value: str):
        parsed = uuid.UUID(value)
        data4 = bytes([parsed.clock_seq_hi_variant, parsed.clock_seq_low]) + parsed.node.to_bytes(6, "big")
        super().__init__(parsed.time_low, parsed.time_mid, parsed.time_hi_version, (ctypes.c_ubyte * 8)(*data4))


def _raise_for_hresult(hr: int, operation: str) -> None:
    if hr < 0:
        raise OSError(f"{operation} failed with HRESULT 0x{hr & 0xFFFFFFFF:08X}")


def activate_packaged_app(app_user_model_id: str, arguments: str) -> int:
    if os.name != "nt":
        raise RuntimeError("Packaged app activation is only supported on Windows")

    ole32 = ctypes.OleDLL("ole32")
    ole32.CoInitializeEx.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
    ole32.CoInitializeEx.restype = ctypes.c_long
    ole32.CoUninitialize.argtypes = []
    ole32.CoUninitialize.restype = None
    ole32.CoCreateInstance.argtypes = [
        ctypes.POINTER(_GUID),
        ctypes.c_void_p,
        ctypes.c_ulong,
        ctypes.POINTER(_GUID),
        ctypes.POINTER(ctypes.c_void_p),
    ]
    ole32.CoCreateInstance.restype = ctypes.c_long

    coinit_hr = ole32.CoInitializeEx(None, 2)
    should_uninitialize = coinit_hr >= 0
    if coinit_hr < 0 and coinit_hr != -2147417850:  # RPC_E_CHANGED_MODE
        _raise_for_hresult(coinit_hr, "CoInitializeEx")

    activation_manager = ctypes.c_void_p()
    try:
        clsid = _GUID("45BA127D-10A8-46EA-8AB7-56EA9078943C")
        iid = _GUID("2e941141-7f97-4756-ba1d-9decde894a3d")
        _raise_for_hresult(
            ole32.CoCreateInstance(ctypes.byref(clsid), None, 1, ctypes.byref(iid), ctypes.byref(activation_manager)),
            "CoCreateInstance(ApplicationActivationManager)",
        )

        activate_application_type = ctypes.WINFUNCTYPE(
            ctypes.c_long,
            ctypes.c_void_p,
            ctypes.c_wchar_p,
            ctypes.c_wchar_p,
            ctypes.c_ulong,
            ctypes.POINTER(ctypes.c_ulong),
        )

        vtable = ctypes.cast(activation_manager, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
        activate_application = activate_application_type(vtable[3])

        process_id = ctypes.c_ulong()
        _raise_for_hresult(
            activate_application(activation_manager, app_user_model_id, arguments, 0, ctypes.byref(process_id)),
            "ActivateApplication",
        )
        return int(process_id.value)
    finally:
        if activation_manager.value:
            release = ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(
                ctypes.cast(activation_manager, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents[2]
            )
            release(activation_manager)
        if should_uninitialize:
            ole32.CoUninitialize()


def cdp_available(debug_port: int) -> bool:
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(f"http://127.0.0.1:{debug_port}/json/version", timeout=1.0) as response:
            return response.status == 200
    except (OSError, urllib.error.URLError, ValueError):
        return False


def wait_for_cdp(debug_port: int, timeout_seconds: float = CDP_WAIT_TIMEOUT_SECONDS) -> bool:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if cdp_available(debug_port):
            return True
        time.sleep(0.25)
    return False


def focus_codex_window(pid: int | None = None, timeout_seconds: float = 10.0) -> dict[str, object]:
    if os.name != "nt":
        return {"ok": False, "skipped": True, "reason": "non_windows"}

    deadline = time.time() + timeout_seconds
    last_error: str | None = None

    while time.time() < deadline:
        target_pid = pid
        if target_pid is None:
            known_pids = [process.get("pid") for process in codex_running_processes()]
            numeric_pids = [candidate for candidate in known_pids if isinstance(candidate, int)]
            if numeric_pids:
                target_pid = max(numeric_pids)

        if target_pid is None:
            time.sleep(0.25)
            continue

        try:
            output = _powershell_output(
                "$shell = New-Object -ComObject WScript.Shell; "
                f"if ($shell.AppActivate({target_pid})) {{ 'activated' }} else {{ 'missing' }}"
            )
            if output.strip().lower() == "activated":
                return {
                    "ok": True,
                    "skipped": False,
                    "method": "wscript_appactivate",
                    "pid": target_pid,
                }
        except Exception as exc:
            last_error = str(exc)

        time.sleep(0.35)

    return {
        "ok": False,
        "skipped": True,
        "reason": "window_not_activated",
        "pid": pid,
        "error": last_error,
    }


def wait_for_new_codex_pid(existing_pids: set[int], timeout_seconds: float = 10.0) -> int | None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        for process in codex_running_processes():
            pid = process.get("pid")
            if isinstance(pid, int) and pid not in existing_pids:
                return pid
            time.sleep(0.25)
    return None


def _normalized_windows_path(value: str | None) -> str:
    return desktop_launcher.normalized_windows_path(value)


def _is_windowsapps_codex_desktop_path(exe_path: str | None) -> bool:
    return desktop_launcher.is_windowsapps_codex_desktop_path(exe_path)


def _known_desktop_codex_exe_paths() -> set[str]:
    return desktop_launcher.known_desktop_codex_exe_paths(
        resolved_exe=resolved_codex_desktop_exe,
        find_windowsapps_exe=find_windowsapps_codex_desktop_exe,
        query_registry_exe=query_codex_desktop_from_registry,
        env_candidates=codex_desktop_env_path_candidates,
    )


def codex_process_details() -> list[dict[str, object]]:
    return desktop_launcher.codex_process_details(
        powershell_output=_powershell_output,
        fallback_processes=codex_running_processes,
    )


def enhancer_runtime_processes(exclude_pid: int | None = None) -> list[dict[str, object]]:
    return desktop_launcher.enhancer_runtime_processes(
        powershell_output=_powershell_output,
        exclude_pid=exclude_pid,
    )


def desktop_codex_running_processes() -> list[dict[str, object]]:
    return desktop_launcher.desktop_codex_running_processes(
        process_details=codex_process_details,
        known_desktop_paths=_known_desktop_codex_exe_paths,
    )


def launch_codex_desktop() -> dict[str, object]:
    """
    Launch Codex Desktop reliably.

    Primary: product-resolved executable path injected by the Tauri runtime
    resolver. Fallback: Start menu AppID via `shell:AppsFolder\\<AppID>`.
    """
    takeover = prepare_codex_takeover()
    if not bool(takeover.get("ok")):
        return {
            "ok": False,
            "method": "takeover_failed",
            "takeover": takeover,
            "error": "Unable to terminate an existing Codex Desktop instance before launch.",
        }

    existing_pids = {
        pid
        for pid in (process.get("pid") for process in codex_running_processes())
        if isinstance(pid, int)
    }
    env = codex_process_environment()
    exe = resolved_codex_desktop_exe()
    if exe:
        process = subprocess.Popen([exe], cwd=str(Path(exe).parent), env=env, **gui_launch_options())
        return {
            "ok": True,
            "method": "product_resolved_exe",
            "exe": exe,
            "source": os.environ.get("AI_STRATEGIST_CODEX_DESKTOP_SOURCE") or "managedLocal",
            "takeover": takeover,
            "foreground": focus_codex_window(process.pid),
        }

    appid = find_codex_desktop_appid()
    if appid:
        target = f"shell:AppsFolder\\{appid}"
        subprocess.Popen(
            ["powershell", "-NoProfile", "-Command", f"Start-Process '{target}'"],
            env=env,
            **subprocess_window_options(),
        )
        pid = wait_for_new_codex_pid(existing_pids)
        return {
            "ok": True,
            "method": "appid",
            "appid": appid,
            "takeover": takeover,
            "foreground": focus_codex_window(pid),
        }

    exe = find_codex_desktop_exe()
    if exe:
        process = subprocess.Popen([exe], cwd=str(Path(exe).parent), env=env, **gui_launch_options())
        return {
            "ok": True,
            "method": "windowsapps_exe_last_resort",
            "exe": exe,
            "warning": "Launched through WindowsApps last-resort discovery; product-managed resolver did not provide Codex Desktop.",
            "takeover": takeover,
            "foreground": focus_codex_window(process.pid),
        }

    return {
        "ok": False,
        "method": "none",
        "error": "Unable to locate Codex Desktop executable or StartApps AppID.",
    }


def _launch_codex_desktop_with_args_once(normalized_args: list[str], debug_port: int | None) -> dict[str, object]:
    env = codex_process_environment()
    proxy_keys = ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY")
    exe = resolved_codex_desktop_exe()
    payload_source = os.environ.get("AI_STRATEGIST_CODEX_DESKTOP_SOURCE") or "managedLocal"
    if exe:
        exe_path = Path(exe)
        app_user_model_id = packaged_app_user_model_id_for_exe(exe_path)
        if app_user_model_id:
            previous = {key: os.environ.get(key) for key in proxy_keys}
            os.environ.update({key: env[key] for key in proxy_keys if key in env})
            try:
                pid = activate_packaged_app(app_user_model_id, subprocess.list2cmdline(normalized_args))
            finally:
                for key, value in previous.items():
                    if value is None:
                        os.environ.pop(key, None)
                    else:
                        os.environ[key] = value
            if debug_port is not None and not wait_for_cdp(debug_port):
                terminate_desktop_codex_processes(timeout_seconds=3.0)
                return {
                    "ok": False,
                    "method": "product_resolved_packaged_activation",
                    "exe": exe,
                    "appid": app_user_model_id,
                    "source": payload_source,
                    "args": normalized_args,
                    "debug_port": debug_port,
                    "pid": pid,
                    "error": f"Codex Desktop launched but {CDP_NOT_READY_ERROR_FRAGMENT} on port {debug_port}.",
                }
            return {
                "ok": True,
                "method": "product_resolved_packaged_activation",
                "exe": exe,
                "appid": app_user_model_id,
                "source": payload_source,
                "args": normalized_args,
                "debug_port": debug_port,
                "pid": pid,
                "foreground": focus_codex_window(pid),
            }

        process = subprocess.Popen([exe, *normalized_args], cwd=str(exe_path.parent), env=env, **gui_launch_options())
        if debug_port is not None and not wait_for_cdp(debug_port):
            terminate_desktop_codex_processes(timeout_seconds=3.0)
            return {
                "ok": False,
                "method": "product_resolved_exe",
                "exe": exe,
                "source": payload_source,
                "args": normalized_args,
                "debug_port": debug_port,
                "pid": process.pid,
                "error": f"Codex Desktop launched but {CDP_NOT_READY_ERROR_FRAGMENT} on port {debug_port}.",
            }
        return {
            "ok": True,
            "method": "product_resolved_exe",
            "exe": exe,
            "source": payload_source,
            "args": normalized_args,
            "debug_port": debug_port,
            "pid": process.pid,
            "foreground": focus_codex_window(process.pid),
        }

    exe = find_codex_desktop_exe()
    if exe:
        exe_path = Path(exe)
        app_user_model_id = packaged_app_user_model_id_for_exe(exe_path)
        if app_user_model_id:
            previous = {key: os.environ.get(key) for key in proxy_keys}
            os.environ.update({key: env[key] for key in proxy_keys if key in env})
            try:
                pid = activate_packaged_app(app_user_model_id, subprocess.list2cmdline(normalized_args))
            finally:
                for key, value in previous.items():
                    if value is None:
                        os.environ.pop(key, None)
                    else:
                        os.environ[key] = value
            if debug_port is not None and not wait_for_cdp(debug_port):
                terminate_desktop_codex_processes(timeout_seconds=3.0)
                return {
                    "ok": False,
                    "method": "windowsapps_packaged_activation",
                    "exe": exe,
                    "appid": app_user_model_id,
                    "args": normalized_args,
                    "debug_port": debug_port,
                    "pid": pid,
                    "error": f"Codex Desktop launched but {CDP_NOT_READY_ERROR_FRAGMENT} on port {debug_port}.",
                }
            return {
                "ok": True,
                "method": "windowsapps_packaged_activation",
                "exe": exe,
                "appid": app_user_model_id,
                "args": normalized_args,
                "debug_port": debug_port,
                "pid": pid,
                "foreground": focus_codex_window(pid),
            }

        process = subprocess.Popen([exe, *normalized_args], cwd=str(exe_path.parent), env=env, **gui_launch_options())
        if debug_port is not None and not wait_for_cdp(debug_port):
            terminate_desktop_codex_processes(timeout_seconds=3.0)
            return {
                "ok": False,
                "method": "windowsapps_exe_last_resort",
                "exe": exe,
                "args": normalized_args,
                "debug_port": debug_port,
                "pid": process.pid,
                "error": f"Codex Desktop launched but {CDP_NOT_READY_ERROR_FRAGMENT} on port {debug_port}.",
            }
        return {
            "ok": True,
            "method": "windowsapps_exe_last_resort",
            "exe": exe,
            "args": normalized_args,
            "debug_port": debug_port,
            "pid": process.pid,
            "warning": "Enhanced launch fell back to direct Codex executable discovery.",
            "foreground": focus_codex_window(process.pid),
        }

    return {
        "ok": False,
        "method": "none",
        "error": "Unable to locate a direct Codex Desktop executable for enhancer launch.",
    }


def launch_codex_desktop_with_args(extra_args: list[str]) -> dict[str, object]:
    normalized_args, debug_port = normalize_remote_debugging_args(extra_args)
    return _launch_codex_desktop_with_args_once(normalized_args, debug_port)


def launch_codex_desktop_with_retry(
    extra_args: list[str],
    *,
    attempts: int = 3,
    retry_cooldown_seconds: float = 1.5,
) -> dict[str, object]:
    return desktop_launcher.launch_codex_desktop_with_retry(
        extra_args,
        normalize_remote_debugging_args=normalize_remote_debugging_args,
        terminate_runtimes=lambda exclude_pid, timeout_seconds: terminate_enhancer_runtime_processes(
            exclude_pid=exclude_pid,
            timeout_seconds=timeout_seconds,
        ),
        cleanup_failed_launch=lambda current_runtime_pid, timeout_seconds: cleanup_failed_enhanced_launch(
            current_runtime_pid=current_runtime_pid,
            timeout_seconds=timeout_seconds,
        ),
        prepare_takeover=lambda timeout_seconds, cooldown_seconds: prepare_codex_takeover(
            timeout_seconds=timeout_seconds,
            cooldown_seconds=cooldown_seconds,
        ),
        launch_once=_launch_codex_desktop_with_args_once,
        attempts=attempts,
        retry_cooldown_seconds=retry_cooldown_seconds,
        current_runtime_pid=os.getpid() if os.name == "nt" else None,
        cdp_not_ready_error_fragment=CDP_NOT_READY_ERROR_FRAGMENT,
    )


def launch_codex_desktop_with_enhancer(codex_home: Path, launch_mode: str = "official") -> dict[str, object]:
    runtime_script = Path(__file__).resolve().with_name("enhancer_runtime.py")
    status_path = Path(tempfile.gettempdir()) / f"ai-strategist-enhancer-{datetime.now().strftime('%Y%m%d-%H%M%S-%f')}.json"
    log_path = Path(tempfile.gettempdir()) / f"ai-strategist-enhancer-{datetime.now().strftime('%Y%m%d-%H%M%S-%f')}.log"
    runtime_python = resolved_python_runtime_executable()
    process = subprocess.Popen(
        [
            runtime_python,
            str(runtime_script),
            "--codex-home",
            str(codex_home.expanduser()),
            "--launch-mode",
            launch_mode,
            "--status-file",
            str(status_path),
            "--log-file",
            str(log_path),
        ],
        cwd=str(runtime_script.parent),
        **enhancer_runtime_launch_options(),
    )
    deadline = time.time() + 30.0
    try:
        while time.time() < deadline:
            if status_path.exists():
                try:
                    payload = json.loads(status_path.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    time.sleep(0.2)
                    continue
                payload.setdefault("method", "enhancer_runtime")
                payload.setdefault("pid", process.pid)
                payload.setdefault("script", str(runtime_script))
                payload.setdefault("launch_mode", launch_mode)
                payload.setdefault("runtime_python", runtime_python)
                payload.setdefault("log_file", str(log_path))
                if payload.get("ok"):
                    debug_port = payload.get("debug_port")
                    stable_deadline = time.time() + enhancer_ready_stable_seconds()
                    while time.time() < stable_deadline:
                        exit_code = process.poll()
                        if exit_code is not None:
                            return {
                                "ok": False,
                                "method": "enhancer_runtime",
                                "pid": process.pid,
                                "script": str(runtime_script),
                                "launch_mode": launch_mode,
                                "runtime_python": runtime_python,
                                "log_file": str(log_path),
                                "error": f"Enhancer runtime exited shortly after reporting ready status (exit code {exit_code}).",
                            }
                        if isinstance(debug_port, int) and not cdp_available(debug_port):
                            return {
                                "ok": False,
                                "method": "enhancer_runtime",
                                "pid": process.pid,
                                "script": str(runtime_script),
                                "launch_mode": launch_mode,
                                "runtime_python": runtime_python,
                                "log_file": str(log_path),
                                "debug_port": debug_port,
                                "error": f"Enhancer runtime reported ready, but CDP disappeared on port {debug_port}.",
                            }
                        time.sleep(0.2)
                return payload

            exit_code = process.poll()
            if exit_code is not None:
                return {
                    "ok": False,
                    "method": "enhancer_runtime",
                    "pid": process.pid,
                    "script": str(runtime_script),
                    "launch_mode": launch_mode,
                    "runtime_python": runtime_python,
                    "log_file": str(log_path),
                    "error": f"Enhancer runtime exited before reporting ready status (exit code {exit_code}).",
                }
            time.sleep(0.2)

        return {
            "ok": False,
            "method": "enhancer_runtime",
            "pid": process.pid,
            "script": str(runtime_script),
            "launch_mode": launch_mode,
            "runtime_python": runtime_python,
            "log_file": str(log_path),
            "error": "Enhancer runtime did not report ready status before timeout.",
        }
    finally:
        try:
            status_path.unlink(missing_ok=True)
        except OSError:
            pass


def is_codex_or_cli_running() -> bool:
    return bool(codex_running_processes())


def codex_running_processes() -> list[dict[str, object]]:
    processes: list[dict[str, object]] = []
    seen: set[tuple[str, int | None]] = set()
    if shutil.which("powershell"):
        try:
            process = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    "Get-CimInstance Win32_Process -Filter \"Name='Codex.exe' OR Name='codex.exe'\" "
                    "| Select-Object Name,ProcessId,ExecutablePath "
                    "| ConvertTo-Csv -NoTypeInformation",
                ],
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                **subprocess_window_options(),
            )
        except Exception:
            process = None
        if process and process.returncode == 0:
            for raw_line in (process.stdout or "").splitlines():
                line = raw_line.strip()
                if not line:
                    continue
                columns = [part.strip().strip('"') for part in line.split('","')]
                if not columns or columns[0] == "Name":
                    continue
                pid = None
                if len(columns) > 1:
                    try:
                        pid = int(columns[1])
                    except ValueError:
                        pid = None
                dedupe_key = (columns[0].lower(), pid)
                if dedupe_key in seen:
                    continue
                seen.add(dedupe_key)
                processes.append(
                    {
                        "image": columns[0],
                        "pid": pid,
                        "exe": columns[2] if len(columns) > 2 else "",
                    }
                )
            return processes

    if not shutil.which("tasklist"):
        return []

    for image_name in ("Codex.exe", "codex.exe"):
        try:
            process = subprocess.run(
                ["tasklist", "/FI", f"IMAGENAME eq {image_name}", "/FO", "CSV", "/NH"],
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                **subprocess_window_options(),
            )
        except Exception:
            continue
        if process.returncode != 0:
            continue
        for raw_line in (process.stdout or "").splitlines():
            line = raw_line.strip()
            if not line or "INFO:" in line:
                continue
            columns = [part.strip().strip('"') for part in line.split('","')]
            if not columns or columns[0].lower() != image_name.lower():
                continue
            pid = None
            if len(columns) > 1:
                try:
                    pid = int(columns[1])
                except ValueError:
                    pid = None
            dedupe_key = (columns[0].lower(), pid)
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            processes.append({"image": columns[0], "pid": pid})
    return processes


def is_runtime_helper_process(process: dict[str, object]) -> bool:
    image = str(process.get("image") or "")
    exe = str(process.get("exe") or "").replace("/", "\\").lower()
    return image.lower() == "codex.exe" and (
        "\\app\\resources\\codex.exe" in exe
        or exe.endswith("\\resources\\codex.exe")
        or exe.endswith("\\codex\\codex.exe")
    )


def terminate_codex_processes(timeout_seconds: float = 5.0) -> dict[str, object]:
    processes = [
        process
        for process in codex_running_processes()
        if process.get("pid") is not None and is_runtime_helper_process(process)
    ]
    killed: list[dict[str, object]] = []
    errors: list[str] = []

    for process in processes:
        pid = process.get("pid")
        if pid is None:
            continue
        try:
            result = subprocess.run(
                ["taskkill", "/PID", str(pid), "/F"],
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                **subprocess_window_options(),
            )
        except Exception as exc:
            errors.append(f"{process.get('image')} PID {pid}: {exc}")
            continue

        if result.returncode == 0:
            killed.append(process)
        else:
            message = (result.stderr or result.stdout).strip() or f"exit code {result.returncode}"
            errors.append(f"{process.get('image')} PID {pid}: {message}")

    deadline = time.time() + timeout_seconds
    remaining = [process for process in codex_running_processes() if is_runtime_helper_process(process)]
    while remaining and time.time() < deadline:
        time.sleep(0.2)
        remaining = [process for process in codex_running_processes() if is_runtime_helper_process(process)]

    return {
        "ok": not remaining,
        "killed": killed,
        "remaining": remaining,
        "errors": errors,
    }


def terminate_enhancer_runtime_processes(
    exclude_pid: int | None = None,
    timeout_seconds: float = 4.0,
) -> dict[str, object]:
    return desktop_launcher.terminate_enhancer_runtime_processes(
        relist=enhancer_runtime_processes,
        subprocess_window_options=subprocess_window_options,
        exclude_pid=exclude_pid,
        timeout_seconds=timeout_seconds,
    )


def terminate_desktop_codex_processes(timeout_seconds: float = 5.0) -> dict[str, object]:
    return desktop_launcher.terminate_desktop_codex_processes(
        relist=desktop_codex_running_processes,
        subprocess_window_options=subprocess_window_options,
        timeout_seconds=timeout_seconds,
    )


def cleanup_failed_enhanced_launch(
    *,
    current_runtime_pid: int | None = None,
    timeout_seconds: float = 5.0,
) -> dict[str, object]:
    return desktop_launcher.cleanup_failed_enhanced_launch(
        current_runtime_pid=current_runtime_pid,
        terminate_runtimes=lambda exclude_pid, timeout: terminate_enhancer_runtime_processes(
            exclude_pid=exclude_pid,
            timeout_seconds=timeout,
        ),
        terminate_desktop=lambda timeout: terminate_desktop_codex_processes(timeout_seconds=timeout),
        timeout_seconds=timeout_seconds,
    )


def prepare_codex_takeover(timeout_seconds: float = 5.0, cooldown_seconds: float = 1.5) -> dict[str, object]:
    processes = desktop_codex_running_processes()
    if not processes:
        return {
            "ok": True,
            "skipped": True,
            "reason": "no_running_codex",
            "killed": [],
            "remaining": [],
            "errors": [],
        }

    result = terminate_desktop_codex_processes(timeout_seconds=timeout_seconds)
    if not bool(result.get("ok")):
        return {
            "ok": False,
            "skipped": False,
            "reason": "terminate_failed",
            **result,
        }

    time.sleep(max(0.0, cooldown_seconds))
    return {
        "ok": True,
        "skipped": False,
        "reason": "terminated_existing_codex",
        **result,
    }
