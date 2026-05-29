from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path
from typing import Callable


def windows_system_tool(name: str) -> str:
    system_root = os.environ.get("SystemRoot")
    if system_root:
        candidate = Path(system_root) / "System32" / name
        if candidate.exists():
            return str(candidate)
    return name


def normalized_windows_path(value: str | None) -> str:
    if not value:
        return ""
    return str(value).strip().strip('"').replace("/", "\\").lower()


def is_windowsapps_codex_desktop_path(exe_path: str | None) -> bool:
    normalized = normalized_windows_path(exe_path)
    return (
        "\\windowsapps\\openai.codex_" in normalized
        and "\\app\\codex.exe" in normalized
        and "\\app\\resources\\codex.exe" not in normalized
    )


def known_desktop_codex_exe_paths(
    *,
    resolved_exe: Callable[[], str | None],
    find_windowsapps_exe: Callable[[], str | None],
    query_registry_exe: Callable[[], str | None],
    env_candidates: Callable[[], list[object]],
) -> set[str]:
    candidates: set[str] = set()
    for raw in (resolved_exe(), find_windowsapps_exe(), query_registry_exe()):
        normalized = normalized_windows_path(raw)
        if normalized:
            candidates.add(normalized)

    for candidate in env_candidates():
        try:
            if candidate.exists():
                normalized = normalized_windows_path(str(candidate))
                if normalized:
                    candidates.add(normalized)
        except OSError:
            continue
    return candidates


def codex_process_details(
    *,
    powershell_output: Callable[[str], str],
    fallback_processes: Callable[[], list[dict[str, object]]],
) -> list[dict[str, object]]:
    if os.name == "nt":
        try:
            output = powershell_output(
                "Get-CimInstance Win32_Process -Filter \"Name='Codex.exe' OR Name='codex.exe'\" "
                "| Select-Object Name, ProcessId, ExecutablePath, CommandLine "
                "| ForEach-Object { \"$($_.Name)`t$($_.ProcessId)`t$($_.ExecutablePath)`t$($_.CommandLine)\" }"
            )
        except Exception:
            output = ""

        processes: list[dict[str, object]] = []
        seen: set[tuple[str, int | None]] = set()
        for raw_line in output.splitlines():
            parts = raw_line.split("\t", 3)
            if len(parts) < 2:
                continue
            image = parts[0].strip() or "Codex.exe"
            pid: int | None = None
            try:
                pid = int(parts[1].strip())
            except ValueError:
                pid = None
            dedupe_key = (image.lower(), pid)
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            processes.append(
                {
                    "image": image,
                    "pid": pid,
                    "exe": parts[2].strip() if len(parts) > 2 else "",
                    "command_line": parts[3].strip() if len(parts) > 3 else "",
                }
            )
        if processes:
            return processes

    return fallback_processes()


def desktop_codex_running_processes(
    *,
    process_details: Callable[[], list[dict[str, object]]],
    known_desktop_paths: Callable[[], set[str]],
) -> list[dict[str, object]]:
    desktop_paths = known_desktop_paths()
    processes = process_details()
    if not processes:
        return []

    filtered: list[dict[str, object]] = []
    seen: set[tuple[str, int | None]] = set()
    for process in processes:
        exe_path = normalized_windows_path(str(process.get("exe") or ""))
        command_line = normalized_windows_path(str(process.get("command_line") or ""))
        if not (
            (exe_path and (exe_path in desktop_paths or is_windowsapps_codex_desktop_path(exe_path)))
            or any(candidate and candidate in command_line for candidate in desktop_paths)
            or is_windowsapps_codex_desktop_path(command_line)
        ):
            continue
        key = (str(process.get("image") or "").lower(), process.get("pid") if isinstance(process.get("pid"), int) else None)
        if key in seen:
            continue
        seen.add(key)
        filtered.append(process)
    return filtered


def enhancer_runtime_processes(
    *,
    powershell_output: Callable[[str], str],
    exclude_pid: int | None = None,
) -> list[dict[str, object]]:
    if os.name != "nt":
        return []
    try:
        output = powershell_output(
            "Get-CimInstance Win32_Process -Filter \"Name='pythonw.exe' OR Name='python.exe'\" "
            "| Select-Object ProcessId, ExecutablePath, CommandLine "
            "| ForEach-Object { \"$($_.ProcessId)`t$($_.ExecutablePath)`t$($_.CommandLine)\" }"
        )
    except Exception:
        return []

    processes: list[dict[str, object]] = []
    for raw_line in output.splitlines():
        parts = raw_line.split("\t", 2)
        if len(parts) < 3:
            continue
        try:
            pid = int(parts[0].strip())
        except ValueError:
            continue
        if exclude_pid is not None and pid == exclude_pid:
            continue
        command_line = parts[2].strip()
        if "enhancer_runtime.py" not in normalized_windows_path(command_line):
            continue
        processes.append(
            {
                "pid": pid,
                "exe": parts[1].strip(),
                "command_line": command_line,
            }
        )
    return processes


def terminate_named_processes(
    processes: list[dict[str, object]],
    *,
    relist: Callable[[], list[dict[str, object]]],
    subprocess_window_options: Callable[[], dict[str, object]],
    timeout_seconds: float,
    label: str,
) -> dict[str, object]:
    killed: list[dict[str, object]] = []
    errors: list[str] = []

    for process in processes:
        pid = process.get("pid")
        if not isinstance(pid, int):
            continue
        try:
            result = subprocess.run(
                [windows_system_tool("taskkill.exe"), "/PID", str(pid), "/T", "/F"],
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                **subprocess_window_options(),
            )
        except Exception as exc:
            errors.append(f"{label} PID {pid}: {exc}")
            continue

        if result.returncode == 0:
            killed.append(process)
        else:
            message = (result.stderr or result.stdout).strip() or f"exit code {result.returncode}"
            errors.append(f"{label} PID {pid}: {message}")

    deadline = time.time() + timeout_seconds
    remaining = relist()
    while remaining and time.time() < deadline:
        time.sleep(0.2)
        remaining = relist()

    return {
        "ok": not remaining,
        "killed": killed,
        "remaining": remaining,
        "errors": errors,
    }


def terminate_enhancer_runtime_processes(
    *,
    relist: Callable[[int | None], list[dict[str, object]]],
    subprocess_window_options: Callable[[], dict[str, object]],
    exclude_pid: int | None = None,
    timeout_seconds: float = 4.0,
) -> dict[str, object]:
    processes = relist(exclude_pid)
    return terminate_named_processes(
        processes,
        relist=lambda: relist(exclude_pid),
        subprocess_window_options=subprocess_window_options,
        timeout_seconds=timeout_seconds,
        label="enhancer_runtime",
    )


def terminate_desktop_codex_processes(
    *,
    relist: Callable[[], list[dict[str, object]]],
    subprocess_window_options: Callable[[], dict[str, object]],
    timeout_seconds: float = 5.0,
) -> dict[str, object]:
    processes = [process for process in relist() if process.get("pid") is not None]
    return terminate_named_processes(
        processes,
        relist=relist,
        subprocess_window_options=subprocess_window_options,
        timeout_seconds=timeout_seconds,
        label="Codex.exe",
    )


def cleanup_failed_enhanced_launch(
    *,
    current_runtime_pid: int | None,
    terminate_runtimes: Callable[[int | None, float], dict[str, object]],
    terminate_desktop: Callable[[float], dict[str, object]],
    timeout_seconds: float = 5.0,
) -> dict[str, object]:
    launcher = terminate_runtimes(current_runtime_pid, timeout_seconds)
    desktop = terminate_desktop(timeout_seconds)
    return {
        "ok": bool(launcher.get("ok")) and bool(desktop.get("ok")),
        "launcher": launcher,
        "desktop": desktop,
    }


def launch_codex_desktop_with_retry(
    extra_args: list[str],
    *,
    normalize_remote_debugging_args: Callable[[list[str]], tuple[list[str], int | None]],
    terminate_runtimes: Callable[[int | None, float], dict[str, object]],
    cleanup_failed_launch: Callable[[int | None, float], dict[str, object]],
    prepare_takeover: Callable[[float, float], dict[str, object]],
    launch_once: Callable[[list[str], int | None], dict[str, object]],
    attempts: int = 3,
    retry_cooldown_seconds: float = 1.5,
    current_runtime_pid: int | None = None,
    cdp_not_ready_error_fragment: str = "CDP did not come up",
    allow_takeover: bool = False,
) -> dict[str, object]:
    normalized_args, debug_port = normalize_remote_debugging_args(extra_args)
    max_attempts = max(1, int(attempts))
    previous_attempts: list[dict[str, object]] = []

    for attempt in range(1, max_attempts + 1):
        launcher_cleanup = terminate_runtimes(current_runtime_pid, 4.0)
        if not bool(launcher_cleanup.get("ok")):
            return {
                "ok": False,
                "method": "retry_launcher_cleanup",
                "attempt": attempt,
                "attempts": attempt - 1,
                "args": normalized_args,
                "debug_port": debug_port,
                "error": "Failed to stop stale enhancer runtime processes before launch.",
                "launcher_cleanup": launcher_cleanup,
                "previous_attempts": previous_attempts,
            }

        if attempt > 1:
            if not allow_takeover:
                return {
                    "ok": False,
                    "method": "retry_takeover_not_allowed",
                    "attempt": attempt,
                    "attempts": attempt - 1,
                    "args": normalized_args,
                    "debug_port": debug_port,
                    "error": "Codex Desktop did not become ready; explicit repair is required before takeover.",
                    "previous_attempts": previous_attempts,
                }
            takeover = prepare_takeover(max(5.0, retry_cooldown_seconds + 3.5), retry_cooldown_seconds)
            if not bool(takeover.get("ok")):
                return {
                    "ok": False,
                    "method": "retry_takeover",
                    "attempt": attempt,
                    "attempts": attempt - 1,
                    "args": normalized_args,
                    "debug_port": debug_port,
                    "error": "Retry cleanup failed before relaunching Codex Desktop.",
                    "takeover": takeover,
                    "previous_attempts": previous_attempts,
                }

        payload = launch_once(normalized_args, debug_port)
        payload["attempt"] = attempt
        payload["attempts"] = attempt
        if payload.get("ok"):
            if previous_attempts:
                payload["previous_attempts"] = previous_attempts
                payload["recovered_after_retry"] = True
            return payload

        previous_attempts.append(
            {
                "attempt": attempt,
                "method": payload.get("method"),
                "pid": payload.get("pid"),
                "debug_port": payload.get("debug_port"),
                "error": payload.get("error"),
            }
        )
        cleanup = cleanup_failed_launch(current_runtime_pid, 4.0)
        if cdp_not_ready_error_fragment not in str(payload.get("error") or "") or attempt >= max_attempts:
            payload["cleanup"] = cleanup
            payload["previous_attempts"] = previous_attempts[:-1]
            return payload
        previous_attempts[-1]["cleanup"] = cleanup

    return {
        "ok": False,
        "method": "retry_exhausted",
        "attempts": max_attempts,
        "args": normalized_args,
        "debug_port": debug_port,
        "previous_attempts": previous_attempts,
        "error": "Codex Desktop retry loop exited unexpectedly.",
    }
