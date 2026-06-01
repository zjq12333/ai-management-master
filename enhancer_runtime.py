from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
from pathlib import Path

import requests
import websocket

import enhancer_handoff
import enhancer_runtime_watcher
import repair_codex_desktop_history as history_repair
from prelaunch_manager import (
    cdp_available,
    cleanup_failed_enhanced_launch,
    codex_running_processes,
    desktop_codex_running_processes,
    config_path_from_codex_home,
    configure_provider_for_launch,
    ensure_must_install_local_plugins,
    launch_codex_desktop_with_retry,
    load_enhancer_settings,
    read_model_provider,
)


BRIDGE_BINDING_NAME = "aiStrategistEnhancer"
CDP_MESSAGE_ID = 100
ENHANCER_ATTACH_DELAY_SECONDS = 5.0


def next_message_id() -> int:
    global CDP_MESSAGE_ID
    CDP_MESSAGE_ID += 1
    return CDP_MESSAGE_ID


def write_status_file(status_file: str | None, payload: dict[str, object]) -> None:
    if not status_file:
        return
    Path(status_file).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def append_runtime_log(log_file: str | None, message: str) -> None:
    if not log_file:
        return
    timestamp = time.strftime("%Y-%m-%dT%H:%M:%S")
    Path(log_file).parent.mkdir(parents=True, exist_ok=True)
    with Path(log_file).open("a", encoding="utf-8") as handle:
        handle.write(f"[{timestamp}] {message}\n")


def enhancer_attach_delay_seconds() -> float:
    raw = os.environ.get("AI_STRATEGIST_ENHANCER_ATTACH_DELAY_SECONDS", "").strip()
    if raw:
        try:
            return max(0.0, min(30.0, float(raw)))
        except ValueError:
            pass
    return ENHANCER_ATTACH_DELAY_SECONDS


def wait_before_attach(log_file: str | None) -> None:
    delay = enhancer_attach_delay_seconds()
    if delay <= 0:
        return
    append_runtime_log(log_file, f"waiting {delay:.1f}s before enhancer attach")
    time.sleep(delay)


def list_targets(port: int) -> list[dict[str, object]]:
    session = requests.Session()
    session.trust_env = False
    response = session.get(f"http://127.0.0.1:{port}/json", timeout=3)
    response.raise_for_status()
    return response.json()


def codex_page_targets(port: int) -> list[dict[str, object]]:
    pages = [
        target
        for target in list_targets(port)
        if target.get("type") == "page" and target.get("webSocketDebuggerUrl")
    ]
    filtered = []
    for target in pages:
        title = str(target.get("title", "")).lower()
        url = str(target.get("url", "")).lower()
        if "codex" in title or url.startswith("app://"):
            filtered.append(target)
    return filtered or pages


def wait_for_message_id(ws: websocket.WebSocket, message_id: int) -> dict[str, object]:
    while True:
        message = json.loads(ws.recv())
        if message.get("id") != message_id:
            continue
        if "error" in message:
            raise RuntimeError(str(message["error"]))
        return message


def build_bridge_bootstrap(settings: dict[str, object]) -> str:
    return f"""
(() => {{
  window.__aiStrategistEnhancerSettings = {json.dumps(settings, ensure_ascii=False)};
  window.__aiStrategistEnhancerCallbacks = new Map();
  window.__aiStrategistEnhancerSeq = 0;
  window.__aiStrategistEnhancerResolve = (id, result) => {{
    const callback = window.__aiStrategistEnhancerCallbacks.get(id);
    if (!callback) return;
    window.__aiStrategistEnhancerCallbacks.delete(id);
    callback.resolve(result);
  }};
  window.__aiStrategistEnhancerReject = (id, message) => {{
    const callback = window.__aiStrategistEnhancerCallbacks.get(id);
    if (!callback) return;
    window.__aiStrategistEnhancerCallbacks.delete(id);
    callback.reject(new Error(message || "Enhancer request failed"));
  }};
  window.__aiStrategistEnhancerBridge = (path, payload) => new Promise((resolve, reject) => {{
    const id = String(++window.__aiStrategistEnhancerSeq);
    window.__aiStrategistEnhancerCallbacks.set(id, {{ resolve, reject }});
    window.{BRIDGE_BINDING_NAME}(JSON.stringify({{ id, path, payload }}));
  }});
}})();
"""


def inject_script_for_target(
    target: dict[str, object],
    injection_script: str,
    settings: dict[str, object],
) -> websocket.WebSocket:
    websocket_url = str(target["webSocketDebuggerUrl"])
    ws = websocket.create_connection(websocket_url, timeout=5)
    ws.send(json.dumps({"id": 1, "method": "Runtime.enable", "params": {}}))
    wait_for_message_id(ws, 1)
    ws.send(json.dumps({"id": 2, "method": "Runtime.removeBinding", "params": {"name": BRIDGE_BINDING_NAME}}))
    wait_for_message_id(ws, 2)
    ws.send(json.dumps({"id": 3, "method": "Runtime.addBinding", "params": {"name": BRIDGE_BINDING_NAME}}))
    wait_for_message_id(ws, 3)

    bootstrap = build_bridge_bootstrap(settings)
    for message_id, script in ((4, bootstrap), (5, injection_script)):
        ws.send(json.dumps({"id": message_id, "method": "Page.addScriptToEvaluateOnNewDocument", "params": {"source": script}}))
        wait_for_message_id(ws, message_id)

    for message_id, script in ((6, bootstrap), (7, injection_script)):
        ws.send(
            json.dumps(
                {
                    "id": message_id,
                    "method": "Runtime.evaluate",
                    "params": {
                        "expression": script,
                        "awaitPromise": False,
                        "allowUnsafeEvalBlockedByCSP": True,
                    },
                }
            )
        )
        wait_for_message_id(ws, message_id)

    return ws


def resolve_bridge(ws: websocket.WebSocket, request_id: str, result: dict[str, object]) -> None:
    expression = f"window.__aiStrategistEnhancerResolve({json.dumps(request_id)}, {json.dumps(result, ensure_ascii=False)})"
    ws.send(
        json.dumps(
            {
                "id": next_message_id(),
                "method": "Runtime.evaluate",
                "params": {"expression": expression, "awaitPromise": False, "allowUnsafeEvalBlockedByCSP": True},
            }
        )
    )


def reject_bridge(ws: websocket.WebSocket, request_id: str, message: str) -> None:
    expression = f"window.__aiStrategistEnhancerReject({json.dumps(request_id)}, {json.dumps(message, ensure_ascii=False)})"
    ws.send(
        json.dumps(
            {
                "id": next_message_id(),
                "method": "Runtime.evaluate",
                "params": {"expression": expression, "awaitPromise": False, "allowUnsafeEvalBlockedByCSP": True},
            }
        )
    )


def handle_request(codex_home: Path, path: str, payload: dict[str, object]) -> dict[str, object]:
    if path == "/health":
        return {"ok": True, "status": "ok"}
    if path == "/enhancer-settings":
        return {
            "ok": True,
            "status": "ok",
            "settings": load_enhancer_settings(codex_home).get("enhancer", {}),
        }
    if path == "/move-thread-workspace":
        thread_id = str(payload.get("session_id", "")).removeprefix("local:")
        target_cwd = str(payload.get("target_cwd", "") or "")
        return history_repair.move_thread_workspace(codex_home, thread_id, target_cwd, update_state_roots=False)
    if path == "/thread-projectless":
        thread_id = str(payload.get("session_id", "")).removeprefix("local:")
        enabled = bool(payload.get("enabled"))
        return history_repair.set_thread_projectless_state(codex_home, thread_id, enabled)
    if path == "/thread-sort-key":
        thread_id = str(payload.get("session_id", "")).removeprefix("local:")
        return history_repair.thread_sort_key(codex_home, thread_id)
    if path == "/thread-sort-keys":
        sessions = payload.get("sessions")
        thread_ids = []
        if isinstance(sessions, list):
            for item in sessions:
                if isinstance(item, dict):
                    thread_ids.append(str(item.get("session_id", "")).removeprefix("local:"))
        return history_repair.thread_sort_keys(codex_home, thread_ids)
    if path == "/handoff-to-same-workspace":
        thread_id = str(payload.get("session_id", "")).removeprefix("local:")
        title = str(payload.get("title", "") or "")
        return enhancer_handoff.create_handoff(codex_home, thread_id, title)
    return {"ok": False, "status": "failed", "message": f"Unknown path: {path}"}


def bridge_loop(codex_home: Path, ws: websocket.WebSocket) -> None:
    while True:
        try:
            message = json.loads(ws.recv())
        except websocket.WebSocketTimeoutException:
            continue
        except Exception:
            return

        if message.get("method") != "Runtime.bindingCalled":
            continue

        params = message.get("params", {})
        try:
            request = json.loads(str(params.get("payload", "{}")))
            request_id = str(request.get("id", ""))
            result = handle_request(codex_home, str(request.get("path", "")), dict(request.get("payload", {})))
            resolve_bridge(ws, request_id, result)
        except Exception as exc:
            request_id = ""
            try:
                request_id = str(request.get("id", ""))
            except Exception:
                request_id = ""
            if request_id:
                reject_bridge(ws, request_id, str(exc))


def load_injection_script() -> str:
    script_path = Path(__file__).resolve().with_name("enhancer_renderer_inject.js")
    return script_path.read_text(encoding="utf-8")


def debug_args(debug_port: int) -> list[str]:
    return [
        f"--remote-debugging-port={debug_port}",
        f"--remote-allow-origins=http://127.0.0.1:{debug_port}",
    ]


def attach_to_codex(codex_home: Path, debug_port: int) -> tuple[list[websocket.WebSocket], set[str]]:
    script = load_injection_script()
    settings = load_enhancer_settings(codex_home).get("enhancer", {})
    sockets: list[websocket.WebSocket] = []
    seen: set[str] = set()
    deadline = time.time() + 20

    while time.time() < deadline and not sockets:
        try:
            for target in codex_page_targets(debug_port):
                key = str(target.get("id") or target.get("webSocketDebuggerUrl"))
                if not key or key in seen:
                    continue
                ws = inject_script_for_target(target, script, settings if isinstance(settings, dict) else {})
                seen.add(key)
                threading.Thread(target=bridge_loop, args=(codex_home, ws), daemon=True).start()
                sockets.append(ws)
        except Exception:
            time.sleep(0.5)
            continue

    if not sockets:
        raise RuntimeError("Failed to inject enhancer into Codex pages.")
    return sockets, seen


def close_sockets(sockets: list[websocket.WebSocket]) -> None:
    for ws in sockets:
        try:
            ws.close()
        except Exception:
            continue


def watch_for_new_pages(
    codex_home: Path,
    debug_port_ref: dict[str, int],
    sockets_ref: dict[str, list[websocket.WebSocket]],
    seen_ref: dict[str, set[str]],
    attachment_lock: threading.Lock,
) -> None:
    script = load_injection_script()
    settings = load_enhancer_settings(codex_home).get("enhancer", {})
    while True:
        try:
            debug_port = int(debug_port_ref["value"])
            for target in codex_page_targets(debug_port):
                key = str(target.get("id") or target.get("webSocketDebuggerUrl"))
                if not key:
                    continue
                with attachment_lock:
                    if key in seen_ref["value"]:
                        continue
                ws = inject_script_for_target(target, script, settings if isinstance(settings, dict) else {})
                with attachment_lock:
                    if key in seen_ref["value"]:
                        try:
                            ws.close()
                        except Exception:
                            pass
                        continue
                    seen_ref["value"].add(key)
                    sockets_ref["value"].append(ws)
                threading.Thread(target=bridge_loop, args=(codex_home, ws), daemon=True).start()
        except Exception:
            pass
        time.sleep(1.5)


def replace_attachments(
    sockets_ref: dict[str, list[websocket.WebSocket]],
    seen_ref: dict[str, set[str]],
    attachment_lock: threading.Lock,
    new_sockets: list[websocket.WebSocket],
    new_seen: set[str],
) -> None:
    with attachment_lock:
        previous = list(sockets_ref["value"])
        sockets_ref["value"] = list(new_sockets)
        seen_ref["value"] = set(new_seen)
    close_sockets(previous)


def takeover_and_attach(
    codex_home: Path,
    debug_port_ref: dict[str, int],
    sockets_ref: dict[str, list[websocket.WebSocket]],
    seen_ref: dict[str, set[str]],
    attachment_lock: threading.Lock,
    log_file: str | None = None,
) -> bool:
    current_port = int(debug_port_ref["value"])
    append_runtime_log(log_file, f"watcher relaunch requested on debug port {current_port}")

    launch = launch_codex_desktop_with_retry(debug_args(current_port), attempts=3)
    if not launch.get("ok"):
        append_runtime_log(log_file, f"watcher relaunch failed: {launch}")
        return False

    new_port = int(launch.get("debug_port") or current_port)
    try:
        wait_before_attach(log_file)
        sockets, seen = attach_to_codex(codex_home, new_port)
    except Exception as exc:
        cleanup_failed = cleanup_failed_enhanced_launch(current_runtime_pid=os.getpid(), timeout_seconds=4.0)
        append_runtime_log(
            log_file,
            f"watcher attach failed on debug port {new_port}: {exc}; cleanup={cleanup_failed}",
        )
        return False

    with attachment_lock:
        debug_port_ref["value"] = new_port
    replace_attachments(sockets_ref, seen_ref, attachment_lock, sockets, seen)
    append_runtime_log(log_file, f"watcher takeover attached on debug port {new_port}")
    return True


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

    parser = argparse.ArgumentParser()
    parser.add_argument("--codex-home", required=True)
    parser.add_argument("--debug-port", type=int, default=9229)
    parser.add_argument("--launch-mode", default="official")
    parser.add_argument("--status-file", default="")
    parser.add_argument("--log-file", default="")
    args = parser.parse_args()

    codex_home = history_repair.normalize_path(args.codex_home)
    restore_payload = None
    must_install_plugins_payload = None
    phase = "startup"
    status_ready = False
    try:
        append_runtime_log(
            args.log_file,
            "runtime start "
            + json.dumps(
                {
                    "pid": os.getpid(),
                    "python": sys.executable,
                    "launch_mode": args.launch_mode,
                    "debug_port": args.debug_port,
                    "codex_home": str(codex_home),
                    "resolved_codex_desktop": os.environ.get("AI_STRATEGIST_CODEX_DESKTOP"),
                    "resolved_python_runtime": os.environ.get("AI_STRATEGIST_PYTHON_RUNTIME"),
                },
                ensure_ascii=False,
            ),
        )
        phase = "ensure-must-install-plugins"
        must_install_plugins_payload = ensure_must_install_local_plugins(codex_home)
        if must_install_plugins_payload.get("enabled"):
            append_runtime_log(
                args.log_file,
                "must-install plugins "
                + json.dumps(must_install_plugins_payload, ensure_ascii=False, sort_keys=True),
            )
        if args.launch_mode == "official":
            phase = "official-provider-override"
            config_path = config_path_from_codex_home(codex_home)
            raw = config_path.read_text(encoding="utf-8") if config_path.exists() else ""
            if read_model_provider(raw) != "openai":
                restore_payload = configure_provider_for_launch(codex_home, "official")
        elif args.launch_mode == "existing-session":
            append_runtime_log(args.log_file, "existing-session launch keeps current Codex provider and login state")

        phase = "desktop-launch"
        launch = launch_codex_desktop_with_retry(
            [
                f"--remote-debugging-port={args.debug_port}",
                f"--remote-allow-origins=http://127.0.0.1:{args.debug_port}",
            ],
            attempts=3,
        )
        append_runtime_log(args.log_file, f"launch result: {json.dumps(launch, ensure_ascii=False)}")
        if not launch.get("ok"):
            write_status_file(args.status_file, dict(launch))
            print(json.dumps(launch, ensure_ascii=False))
            return 1

        actual_debug_port = int(launch.get("debug_port") or args.debug_port)
        phase = "attach-delay"
        wait_before_attach(args.log_file)
        phase = "attach-to-codex"
        sockets, seen = attach_to_codex(codex_home, actual_debug_port)
        append_runtime_log(
            args.log_file,
            f"attached enhancer bridge on debug port {actual_debug_port} to {len(sockets)} target(s)",
        )
        debug_port_ref = {"value": actual_debug_port}
        sockets_ref = {"value": list(sockets)}
        seen_ref = {"value": set(seen)}
        attachment_lock = threading.Lock()

        phase = "watchers-start"
        page_watcher = threading.Thread(
            target=watch_for_new_pages,
            args=(codex_home, debug_port_ref, sockets_ref, seen_ref, attachment_lock),
            daemon=True,
        )
        page_watcher.start()
        runtime_watcher = threading.Thread(
            target=enhancer_runtime_watcher.watch_loop,
            kwargs={
                "cdp_listening": lambda: cdp_available(int(debug_port_ref["value"])),
                "codex_pids": lambda: [
                    process["pid"]
                    for process in desktop_codex_running_processes()
                    if isinstance(process.get("pid"), int)
                ],
                "takeover": lambda: takeover_and_attach(
                    codex_home,
                    debug_port_ref,
                    sockets_ref,
                    seen_ref,
                    attachment_lock,
                    args.log_file,
                ),
            },
            daemon=True,
        )
        runtime_watcher.start()
        write_status_file(
            args.status_file,
            {
                "ok": True,
                "method": "enhancer_runtime",
                "launch": launch,
                "debug_port": actual_debug_port,
                "phase": "ready",
                "log_file": args.log_file,
                "must_install_plugins": must_install_plugins_payload,
            },
        )
        status_ready = True
        phase = "running"
        append_runtime_log(args.log_file, f"runtime ready on debug port {actual_debug_port}")

        idle_rounds = 0
        while True:
            time.sleep(2)
            if codex_running_processes():
                idle_rounds = 0
                continue
            idle_rounds += 1
            if idle_rounds >= 8:
                append_runtime_log(args.log_file, "runtime exiting after Codex stayed offline")
                return 0
    except Exception as exc:
        cleanup = None
        if not status_ready:
            cleanup = cleanup_failed_enhanced_launch(current_runtime_pid=os.getpid(), timeout_seconds=4.0)
            append_runtime_log(args.log_file, f"startup failure cleanup result: {cleanup}")
        append_runtime_log(args.log_file, f"runtime failure in phase={phase}: {exc!r}")
        write_status_file(
            args.status_file,
            {
                "ok": False,
                "method": "enhancer_runtime",
                "error": str(exc),
                "phase": phase,
                "cleanup": cleanup,
                "log_file": args.log_file,
            },
        )
        return 1
    finally:
        if restore_payload:
            backup_path = Path(restore_payload.backup_path)
            config_path = Path(restore_payload.config_path)
            if backup_path.exists():
                config_path.write_text(backup_path.read_text(encoding="utf-8"), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
