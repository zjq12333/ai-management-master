from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import prelaunch_manager
import repair_codex_desktop_history as history_repair
from prelaunch_manager import (
    ProviderProfile,
    codex_running_processes,
    collect_prelaunch_evidence,
    configure_provider_for_launch,
    enhancer_enabled,
    is_codex_or_cli_running,
    launch_codex_desktop,
    launch_codex_desktop_with_enhancer,
    load_provider_profile_from_config,
    parse_threadripper_status,
    prepare_codex_takeover,
    prepare_codex_desktop_notice_state,
    run_threadripper_status,
    subprocess_window_options,
    terminate_enhancer_runtime_processes,
    threadripper_command,
)


def repo_root() -> Path:
    return Path(__file__).resolve().parent


def normalize_codex_home(codex_home: str) -> Path:
    expanded = os.path.expandvars(codex_home)
    expanded = re.sub(
        r"%([^%]+)%",
        lambda match: os.environ.get(match.group(1), match.group(0)),
        expanded,
    )
    return Path(expanded).expanduser()


def parse_provider_json(raw: str | None) -> dict[str, object] | None:
    if raw is None:
        return None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid --provider-json payload: {exc}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("Invalid --provider-json payload: expected a JSON object.")
    return payload


def prepare_report_dir(kind: str, mode: str | None) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    safe_kind = (kind or "unknown").replace(" ", "_")
    safe_mode = (mode or "unknown").replace(" ", "_")
    reports_root = Path(os.environ.get("AI_STRATEGIST_REPORTS_DIR") or repo_root() / "reports")
    report_dir = reports_root / f"{stamp}-{safe_kind}-{safe_mode}"
    report_dir.mkdir(parents=True, exist_ok=True)
    return report_dir


def write_report_bundle(report_dir: Path, payload: dict[str, object], log_lines: list[str] | None = None) -> None:
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "run.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    lines = log_lines or []
    if not lines:
        lines = [json.dumps(payload, ensure_ascii=False, indent=2)]
    (report_dir / "run.log.txt").write_text(
        "\n".join(line.rstrip("\n") for line in lines) + "\n",
        encoding="utf-8",
    )


def handle_status(codex_home: str) -> dict[str, object]:
    evidence = collect_prelaunch_evidence(normalize_codex_home(codex_home))
    return {"ok": True, "evidence": evidence.to_dict()}


def handle_runtime_status() -> dict[str, object]:
    processes = codex_running_processes()
    desktop_processes = prelaunch_manager.desktop_codex_running_processes()
    product_resolved_exe = prelaunch_manager.resolved_codex_desktop_exe()
    appid = prelaunch_manager.find_codex_desktop_appid()
    last_resort_exe = None if product_resolved_exe else prelaunch_manager.find_codex_desktop_exe()
    return {
        "ok": True,
        "codex_running": bool(desktop_processes),
        "processes": processes,
        "desktop_processes": desktop_processes,
        "desktop_launch": {
            "product_resolved_exe": product_resolved_exe,
            "product_resolved_source": os.environ.get("AI_STRATEGIST_CODEX_DESKTOP_SOURCE") or None,
            "appid": appid,
            "last_resort_exe": last_resort_exe,
            "method": (
                "product_resolved_exe"
                if product_resolved_exe
                else "appid"
                if appid
                else "windowsapps_exe_last_resort"
                if last_resort_exe
                else "none"
            ),
        },
    }


def handle_stop_runtime() -> dict[str, object]:
    result = terminate_enhancer_runtime_processes(current_runtime_pid=os.getpid())
    return {"ok": bool(result.get("ok")), **result}


def ensure_codex_not_running() -> None:
    if is_codex_or_cli_running():
        raise RuntimeError("请先完全退出 Codex Desktop 和 codex CLI 后再继续。")


def run_threadripper_sync_if_needed(codex_home: str, force: bool = False) -> dict[str, object]:
    codex_home_path = normalize_codex_home(codex_home)
    status = run_threadripper_status(codex_home_path) or {}
    command = threadripper_command()
    rows = int(status.get("rows_needing_reconcile") or 0)

    if not command:
        return {
            "ok": True,
            "skipped": True,
            "reason": "threadripper_unavailable",
            "status": status,
        }

    if rows <= 0 and not force:
        return {"ok": True, "skipped": True, "status": status}

    process = subprocess.run(
        [command, "--codex-home", str(codex_home_path), "sync"],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        **subprocess_window_options(),
    )
    if process.returncode != 0:
        return {
            "ok": False,
            "skipped": False,
            "status": status,
            "error": (process.stderr or process.stdout).strip() or f"exit code {process.returncode}",
        }

    sync_status = parse_threadripper_status(process.stdout)
    if not sync_status:
        sync_status = status
    sync_status["raw"] = process.stdout
    return {"ok": True, "skipped": False, "status": sync_status}


def run_threadripper_compatibility_check(codex_home: str) -> dict[str, object]:
    """
    Read provider-bucket compatibility without changing thread ownership.

    AI Strategist's product model restores conversations to their original
    workspace/session location. Provider-bucket data is diagnostic compatibility
    evidence only unless a future explicit repair action asks to mutate it.
    """
    codex_home_path = normalize_codex_home(codex_home)
    command = threadripper_command()
    status = run_threadripper_status(codex_home_path) or {}
    if not command:
        return {
            "ok": True,
            "skipped": True,
            "reason": "threadripper_unavailable",
            "status": status,
        }
    if status.get("error"):
        return {
            "ok": False,
            "skipped": True,
            "reason": "status_failed",
            "error": status.get("error"),
            "status": status,
        }
    return {
        "ok": True,
        "skipped": True,
        "reason": "compatibility_check_only",
        "status": status,
    }


def run_history_repair(
    codex_home: str,
    projectless_mode: str,
    *,
    include_archived: bool = False,
    allow_missing_cwd: bool = False,
    allow_empty_cwd: bool = False,
    allow_missing_session: bool = False,
    unarchive_selected: bool = False,
) -> dict[str, object]:
    args = argparse.Namespace(
        codex_home=codex_home,
        current_thread_id=None,
        dry_run=False,
        include_archived=include_archived,
        allow_missing_cwd=allow_missing_cwd,
        allow_empty_cwd=allow_empty_cwd,
        allow_missing_session=allow_missing_session,
        unarchive_selected=unarchive_selected,
        projectless_mode=projectless_mode,
    )
    codex_home_path = normalize_codex_home(codex_home)
    db_path = codex_home_path / "state_5.sqlite"
    state_path = codex_home_path / ".codex-global-state.json"
    index_path = codex_home_path / "session_index.jsonl"

    for path, label in ((db_path, "SQLite DB"), (state_path, "Desktop state file")):
        if not path.exists():
            raise RuntimeError(f"{label} not found: {path}")

    threads = history_repair.load_threads(db_path)
    selected, skipped = history_repair.selected_threads(threads, args)
    result = history_repair.build_result(codex_home_path, threads, selected, skipped, False)
    result["thread_attributions"] = history_repair.thread_attributions(threads, args)
    backup_dir = history_repair.backup_files(codex_home_path)
    existing_index_rows = history_repair.read_jsonl(index_path)
    history_repair.write_jsonl(index_path, history_repair.make_index_rows(existing_index_rows, selected))
    result["backup_dir"] = str(backup_dir)
    result["session_index_rows"] = len(selected)
    if args.include_archived and args.unarchive_selected:
        result["unarchived"] = history_repair.unarchive_selected_threads(
            db_path, [thread["id"] for thread in selected]
        )
    else:
        result["unarchived"] = 0
    result.update(history_repair.repair_state(state_path, selected, args.current_thread_id, args.projectless_mode))
    return {"ok": True, "summary": result}


def provider_config_payload(config: object) -> dict[str, object]:
    return {
        "config_path": config.config_path,
        "backup_path": config.backup_path,
        "mode": config.mode,
        "target_model_provider": config.target_model_provider,
        "verified_model_provider": config.verified_model_provider,
    }


def current_provider_config_payload(codex_home: str, mode: str) -> dict[str, object]:
    codex_home_path = normalize_codex_home(codex_home)
    config_path = prelaunch_manager.config_path_from_codex_home(codex_home_path)
    raw = config_path.read_text(encoding="utf-8") if config_path.exists() else ""
    current_provider = prelaunch_manager.read_model_provider(raw) or "unknown"
    target_provider = "openai" if mode == "official" else current_provider
    source = "existing_config"
    if mode == "official" and current_provider != "openai":
        source = "transient_official_runtime_override"
    return {
        "config_path": str(config_path),
        "backup_path": None,
        "mode": mode,
        "current_model_provider": current_provider,
        "target_model_provider": target_provider,
        "verified_model_provider": target_provider if source == "existing_config" else current_provider,
        "source": source,
        "mutated": False,
    }


def handle_launch(
    codex_home: str,
    mode: str,
    provider: dict[str, object] | None,
    projectless_mode: str,
    hide_official_quota_notice: bool = False,
    restore_history: bool = False,
    include_archived: bool = False,
    allow_missing_cwd: bool = False,
    allow_empty_cwd: bool = False,
    allow_missing_session: bool = False,
    unarchive_selected: bool = False,
) -> dict[str, object]:
    report_dir = prepare_report_dir("配置并启动", mode)
    payload: dict[str, object] = {
        "ok": False,
        "started_at": datetime.now().astimezone().isoformat(),
        "kind": "配置并启动",
        "mode": mode,
        "codex_home": str(normalize_codex_home(codex_home)),
        "report_dir": str(report_dir),
    }
    log_lines: list[str] = []
    should_restore_history = bool(restore_history) and mode != "official"

    try:
        takeover = {"ok": True, "skipped": True, "reason": "launch_preserves_existing_codex"}
        payload["takeover"] = takeover
        log_lines.append("Launch preserves existing Codex processes; no takeover was attempted.")
        if hide_official_quota_notice:
            notice_state = prepare_codex_desktop_notice_state()
            payload["notice_suppression"] = notice_state
            log_lines.append(
                "Official quota notice suppression: ok={ok} method={method} reason={reason}".format(
                    ok=notice_state.get("ok"),
                    method=notice_state.get("method") or "none",
                    reason=notice_state.get("reason") or "none",
                )
            )

        codex_home_path = normalize_codex_home(codex_home)
        profile = None if provider is None else ProviderProfile(**provider)
        if mode == "api" and profile is None:
            profile = load_provider_profile_from_config(codex_home_path, mode)

        if should_restore_history:
            try:
                repair = run_history_repair(
                    codex_home,
                    projectless_mode,
                    include_archived=include_archived,
                    allow_missing_cwd=allow_missing_cwd,
                    allow_empty_cwd=allow_empty_cwd,
                    allow_missing_session=allow_missing_session,
                    unarchive_selected=unarchive_selected,
                )
            except Exception as exc:
                payload["repair"] = {"ok": False, "error": str(exc)}
                payload["launch"] = {"ok": False, "skipped": True, "reason": "prelaunch_repair_failed"}
                log_lines.append(f"History repair failed: {exc}")
                return payload

            payload["repair"] = repair
            if not bool(repair.get("ok")):
                payload["launch"] = {"ok": False, "skipped": True, "reason": "prelaunch_repair_failed"}
                log_lines.append(f"History repair failed: {repair.get('error') or 'unknown error'}")
                return payload

            repair_summary = repair.get("summary") or {}
            log_lines.append(
                "History restore: threads_selected={selected} backup_dir={backup}".format(
                    selected=repair_summary.get("threads_selected") or 0,
                    backup=repair_summary.get("backup_dir") or "unknown",
                )
            )
        else:
            skip_reason = "launch_history_restore_disabled" if mode != "official" else "official_launch_keeps_original_chat_state"
            payload["repair"] = {
                "ok": True,
                "skipped": True,
                "reason": skip_reason,
            }
            if mode != "official":
                log_lines.append("History restore skipped: launch restore option is disabled.")
            else:
                log_lines.append("History restore skipped: official launch keeps original chat state.")

        if mode == "official":
            provider_config = current_provider_config_payload(codex_home, mode)
        else:
            if profile is None:
                profile = load_provider_profile_from_config(codex_home_path, mode)
            config = configure_provider_for_launch(codex_home_path, mode, profile=profile)
            provider_config = provider_config_payload(config)
        payload["provider_config"] = provider_config
        log_lines.append(
            "Configured provider: mode={mode} target={target} verified={verified}".format(
                mode=provider_config["mode"],
                target=provider_config["target_model_provider"],
                verified=provider_config["verified_model_provider"],
            )
        )

        try:
            compatibility = run_threadripper_compatibility_check(codex_home)
        except Exception as exc:
            compatibility = {"ok": False, "skipped": True, "reason": "status_exception", "error": str(exc)}
        payload["provider_compatibility"] = compatibility
        # Keep the legacy key so existing result cards and old reports remain readable.
        payload["sync"] = compatibility
        compatibility_status = compatibility.get("status") or {}
        log_lines.append(
            "Provider compatibility: target={target} rows={rows} reason={reason}".format(
                target=compatibility_status.get("target_provider") or "unknown",
                rows=compatibility_status.get("rows_needing_reconcile") or 0,
                reason=compatibility.get("reason") or "none",
            )
        )

        launch = launch_codex_desktop()
        payload["launch"] = launch
        payload["ok"] = bool(launch.get("ok"))
        if launch.get("ok"):
            method = launch.get("method") or "unknown"
            log_lines.append(f"Codex Desktop launched ({method}).")
        else:
            payload.setdefault("error", launch.get("error") or "launch failed")
            log_lines.append(f"Codex Desktop launch failed: {launch.get('error') or 'unknown error'}")
        return payload
    except Exception as exc:
        payload["error"] = str(exc)
        payload["launch"] = {"ok": False, "skipped": True, "reason": "prelaunch_exception"}
        log_lines.append(f"Prelaunch failed: {exc}")
        return payload
    finally:
        payload["finished_at"] = datetime.now().astimezone().isoformat()
        payload["status"] = "ok" if bool(payload.get("ok")) else "error"
        write_report_bundle(report_dir, payload, log_lines)


def handle_repair(
    codex_home: str,
    projectless_mode: str,
    *,
    include_archived: bool = False,
    allow_missing_cwd: bool = False,
    allow_empty_cwd: bool = False,
    allow_missing_session: bool = False,
    unarchive_selected: bool = False,
) -> dict[str, object]:
    report_dir = prepare_report_dir("修复恢复", "repair")
    payload: dict[str, object] = {
        "ok": False,
        "started_at": datetime.now().astimezone().isoformat(),
        "kind": "修复恢复",
        "mode": "repair",
        "codex_home": str(normalize_codex_home(codex_home)),
        "report_dir": str(report_dir),
    }
    log_lines: list[str] = []

    try:
        ensure_codex_not_running()
        repair = run_history_repair(
            codex_home,
            projectless_mode,
            include_archived=include_archived,
            allow_missing_cwd=allow_missing_cwd,
            allow_empty_cwd=allow_empty_cwd,
            allow_missing_session=allow_missing_session,
            unarchive_selected=unarchive_selected,
        )
        payload["repair"] = repair
        payload["ok"] = bool(repair.get("ok"))
        summary = repair.get("summary") or {}
        log_lines.append(
            "History restore: threads_selected={selected} backup_dir={backup}".format(
                selected=summary.get("threads_selected") or 0,
                backup=summary.get("backup_dir") or "unknown",
            )
        )
        return payload
    except Exception as exc:
        payload["repair"] = {"ok": False, "error": str(exc)}
        payload["error"] = str(exc)
        log_lines.append(f"History repair failed: {exc}")
        return payload
    finally:
        payload["finished_at"] = datetime.now().astimezone().isoformat()
        payload["status"] = "ok" if bool(payload.get("ok")) else "error"
        write_report_bundle(report_dir, payload, log_lines)


def handle_enhanced_launch(codex_home: str) -> dict[str, object]:
    codex_home_path = normalize_codex_home(codex_home)
    report_dir = prepare_report_dir("启动增强", "existing-session-enhancer")
    payload: dict[str, object] = {
        "ok": False,
        "started_at": datetime.now().astimezone().isoformat(),
        "kind": "启动增强",
        "mode": "existing-session-enhancer",
        "codex_home": str(codex_home_path),
        "report_dir": str(report_dir),
        "stages": {},
    }
    log_lines: list[str] = []

    stage = "locate_codex"
    try:
        payload["stages"]["locate_codex"] = collect_prelaunch_evidence(codex_home_path).to_dict()
        log_lines.append("Stage locate_codex: collected local Codex Desktop evidence.")

        stage = "launch_with_enhancer"
        launch = launch_codex_desktop_with_enhancer(codex_home_path, "existing-session")
        payload["stages"]["launch_with_enhancer"] = launch
        payload["launch"] = launch
        payload["ok"] = bool(launch.get("ok"))
        if payload["ok"]:
            log_lines.append(
                "Stage launch_with_enhancer: ok method={method} runtime_pid={pid}".format(
                    method=launch.get("method") or "unknown",
                    pid=launch.get("runtime_pid") or "unknown",
                )
            )
        else:
            log_lines.append(
                "Stage launch_with_enhancer: failed error={error}".format(
                    error=launch.get("error") or launch.get("reason") or "unknown"
                )
            )
        return payload
    except Exception as exc:
        payload["error"] = str(exc)
        payload["stages"][stage] = {"ok": False, "error": str(exc)}
        log_lines.append(f"Stage {stage}: exception {exc}")
        return payload
    finally:
        payload["finished_at"] = datetime.now().astimezone().isoformat()
        payload["status"] = "ok" if bool(payload.get("ok")) else "error"
        write_report_bundle(report_dir, payload, log_lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["status", "runtime-status", "stop-runtime", "launch", "repair", "enhanced-launch"])
    parser.add_argument("--codex-home", required=False)
    parser.add_argument("--mode", default="official")
    parser.add_argument("--projectless-mode", default="none")
    parser.add_argument("--provider-json")
    parser.add_argument("--hide-official-quota-notice", action="store_true")
    parser.add_argument("--restore-history", action="store_true")
    parser.add_argument("--include-archived", action="store_true")
    parser.add_argument("--allow-missing-cwd", action="store_true")
    parser.add_argument("--allow-empty-cwd", action="store_true")
    parser.add_argument("--allow-missing-session", action="store_true")
    parser.add_argument("--unarchive-selected", action="store_true")
    return parser


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

    parser = build_parser()
    args = parser.parse_args()

    try:
        provider = parse_provider_json(args.provider_json)
        if args.command == "status":
            if not args.codex_home:
                raise RuntimeError("--codex-home is required for status")
            payload = handle_status(args.codex_home)
        elif args.command == "runtime-status":
            payload = handle_runtime_status()
        elif args.command == "stop-runtime":
            payload = handle_stop_runtime()
        elif args.command == "repair":
            if not args.codex_home:
                raise RuntimeError("--codex-home is required for repair")
            payload = handle_repair(
                args.codex_home,
                args.projectless_mode,
                include_archived=args.include_archived,
                allow_missing_cwd=args.allow_missing_cwd,
                allow_empty_cwd=args.allow_empty_cwd,
                allow_missing_session=args.allow_missing_session,
                unarchive_selected=args.unarchive_selected,
            )
        elif args.command == "enhanced-launch":
            if not args.codex_home:
                raise RuntimeError("--codex-home is required for enhanced-launch")
            payload = handle_enhanced_launch(args.codex_home)
        else:
            if not args.codex_home:
                raise RuntimeError("--codex-home is required for launch")
            payload = handle_launch(
                args.codex_home,
                args.mode,
                provider,
                args.projectless_mode,
                args.hide_official_quota_notice,
                args.restore_history,
                include_archived=args.include_archived,
                allow_missing_cwd=args.allow_missing_cwd,
                allow_empty_cwd=args.allow_empty_cwd,
                allow_missing_session=args.allow_missing_session,
                unarchive_selected=args.unarchive_selected,
            )
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 1

    print(json.dumps(payload, ensure_ascii=False))
    return 0 if bool(payload.get("ok")) else 1


if __name__ == "__main__":
    raise SystemExit(main())
