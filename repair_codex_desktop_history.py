import argparse
import json
import os
import re
import shutil
import sqlite3
import sys
import tomllib
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


def normalize_path(value: str | Path) -> Path:
    text = str(value)
    expanded = os.path.expandvars(text)
    expanded = re.sub(
        r"%([^%]+)%",
        lambda match: os.environ.get(match.group(1), match.group(0)),
        expanded,
    )
    return Path(expanded).expanduser()


def clean_path(value: str | None) -> str | None:
    if not value:
        return None
    if value.startswith("\\\\?\\"):
        return value[4:]
    return value


def path_exists(value: str | None) -> bool:
    clean = clean_path(value)
    return bool(clean and Path(clean).exists())


def dir_nonempty(value: str | None) -> bool:
    clean = clean_path(value)
    if not clean:
        return False
    path = Path(clean)
    try:
        return path.exists() and path.is_dir() and any(path.iterdir())
    except OSError:
        return False


def canonical_path_key(value: str | None) -> str | None:
    clean = clean_path(value)
    if not clean:
        return None
    return clean.rstrip("\\/").casefold()


def default_history_root() -> str:
    return str(Path.home() / "Documents" / "Codex")


def safe_history_root(value: str | None) -> str:
    clean = clean_path(value) or default_history_root()
    path = normalize_path(clean)
    if path.exists() and path.is_dir():
        return str(path)
    fallback = Path.home()
    return str(fallback)


def normalized_workspace_path(value: str | None, history_root: str | None) -> tuple[str | None, str]:
    clean = clean_path(value)
    if clean and dir_nonempty(clean):
        return clean, "kept"
    if clean and path_exists(clean):
        return safe_history_root(history_root), "empty-to-history-root"
    return safe_history_root(history_root), "missing-to-history-root"


def append_unique_path(paths: list[str], value: str | None) -> bool:
    clean = clean_path(value)
    key = canonical_path_key(clean)
    if not clean or not key:
        return False
    existing = {canonical_path_key(path) for path in paths}
    if key in existing:
        return False
    paths.append(clean)
    return True


def preview_text(value: str | None, limit: int = 160) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).split())
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        if raw.strip():
            rows.append(json.loads(raw))
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False))
        handle.write("\n")


def read_current_provider(codex_home: Path) -> str | None:
    config_path = codex_home / "config.toml"
    if not config_path.exists():
        return None
    try:
        data = tomllib.loads(config_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    provider = data.get("model_provider")
    return provider if isinstance(provider, str) and provider.strip() else None


def load_threads(db_path: Path) -> list[dict[str, Any]]:
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    try:
        return [
            dict(row)
            for row in con.execute(
                """
                select id, cwd, archived, archived_at, model_provider, updated_at,
                       has_user_event, first_user_message, title, rollout_path
                from threads
                order by updated_at desc
                """
            )
        ]
    finally:
        con.close()


def has_conversation(thread: dict[str, Any]) -> bool:
    if thread.get("has_user_event"):
        return True
    first_user_message = thread.get("first_user_message")
    return isinstance(first_user_message, str) and bool(first_user_message.strip())


def classify_thread(
    thread: dict[str, Any],
    *,
    include_archived: bool,
    allow_missing_cwd: bool,
    allow_empty_cwd: bool,
    allow_missing_session: bool,
) -> str | None:
    if not has_conversation(thread):
        return "no_user_message"
    if thread.get("archived") and not include_archived:
        return "archived"
    if not allow_missing_session and not path_exists(thread.get("rollout_path")):
        return "missing_session_file"
    cwd = clean_path(thread.get("cwd"))
    if not cwd and not allow_missing_cwd:
        return "missing_cwd"
    if cwd and not Path(cwd).exists() and not allow_missing_cwd:
        return "missing_cwd"
    if cwd and Path(cwd).exists() and not allow_empty_cwd and not dir_nonempty(cwd):
        return "empty_cwd"
    return None


def selected_threads(threads: list[dict[str, Any]], args: argparse.Namespace) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    selected: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for thread in threads:
        reason = classify_thread(
            thread,
            include_archived=args.include_archived,
            allow_missing_cwd=args.allow_missing_cwd,
            allow_empty_cwd=args.allow_empty_cwd,
            allow_missing_session=args.allow_missing_session,
        )
        if reason:
            skipped.append(
                {
                    "id": thread.get("id"),
                    "reason": reason,
                    "cwd": clean_path(thread.get("cwd")),
                    "title": preview_text(thread.get("title") or thread.get("first_user_message")),
                }
            )
        else:
            selected.append(thread)
    return selected, skipped


def thread_attributions(threads: list[dict[str, Any]], args: argparse.Namespace) -> list[dict[str, Any]]:
    attributions: list[dict[str, Any]] = []
    for thread in threads:
        reason = classify_thread(
            thread,
            include_archived=args.include_archived,
            allow_missing_cwd=args.allow_missing_cwd,
            allow_empty_cwd=args.allow_empty_cwd,
            allow_missing_session=args.allow_missing_session,
        )
        cwd = clean_path(thread.get("cwd"))
        target_location = "skipped" if reason else "workspace"
        attribution_reason = reason or "cwd_exists_and_session_exists"
        attributions.append(
            {
                "id": thread.get("id"),
                "target_location": target_location,
                "workspace_root": cwd if target_location == "workspace" else None,
                "reason": attribution_reason,
                "provider": thread.get("model_provider") or "<null>",
                "session_path": clean_path(thread.get("rollout_path")),
                "title": preview_text(thread.get("title") or thread.get("first_user_message")),
            }
        )
    return attributions


def make_index_rows(existing_rows: list[dict[str, Any]], threads: list[dict[str, Any]]) -> list[dict[str, Any]]:
    existing_by_id = {row.get("id"): row for row in existing_rows if row.get("id")}
    rows: list[dict[str, Any]] = []
    for thread in threads:
        thread_id = thread["id"]
        existing = dict(existing_by_id.get(thread_id) or {})
        existing["id"] = thread_id
        existing["thread_name"] = existing.get("thread_name") or thread.get("title") or thread.get("first_user_message") or thread_id
        existing["updated_at"] = existing.get("updated_at") or timestamp_from_epoch(thread.get("updated_at"))
        rows.append(existing)
    return rows


def timestamp_from_epoch(value: Any) -> str:
    try:
        return datetime.fromtimestamp(int(value)).astimezone().isoformat()
    except (TypeError, ValueError, OSError):
        return datetime.now().astimezone().isoformat()


def backup_files(codex_home: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_dir = codex_home / "desktop_history_repair_backups" / stamp
    backup_dir.mkdir(parents=True, exist_ok=True)
    for name in [
        "state_5.sqlite",
        "state_5.sqlite-wal",
        "state_5.sqlite-shm",
        ".codex-global-state.json",
        "session_index.jsonl",
    ]:
        source = codex_home / name
        if source.exists():
            shutil.copy2(source, backup_dir / name)
    return backup_dir


def update_rollout_session_meta_cwd(rollout_path: str | None, thread_id: str, target_cwd: str) -> dict[str, Any]:
    clean_rollout_path = clean_path(rollout_path)
    if not clean_rollout_path:
        return {"updated": False, "error": ""}

    path = Path(clean_rollout_path)
    if not path.exists():
        return {"updated": False, "error": ""}

    changed = False
    next_lines: list[str] = []
    try:
        for raw_line in path.read_text(encoding="utf-8").splitlines(keepends=True):
            line_body = raw_line[:-1] if raw_line.endswith("\n") else raw_line
            line_end = "\n" if raw_line.endswith("\n") else ""
            try:
                item = json.loads(line_body)
            except json.JSONDecodeError:
                next_lines.append(raw_line)
                continue

            payload = item.get("payload")
            if (
                item.get("type") == "session_meta"
                and isinstance(payload, dict)
                and payload.get("id") == thread_id
                and payload.get("cwd") != target_cwd
            ):
                payload["cwd"] = target_cwd
                raw_line = json.dumps(item, ensure_ascii=False, separators=(",", ":")) + line_end
                changed = True
            next_lines.append(raw_line)

        if changed:
            path.write_text("".join(next_lines), encoding="utf-8")
        return {"updated": changed, "error": ""}
    except OSError as exc:
        return {"updated": False, "error": str(exc)}


def update_rollout_model_provider(rollout_path: str | None, thread_id: str, target_provider: str) -> dict[str, Any]:
    clean_rollout_path = clean_path(rollout_path)
    if not clean_rollout_path:
        return {"updated": False, "error": "missing_rollout_path"}

    path = Path(clean_rollout_path)
    if not path.exists():
        return {"updated": False, "error": "missing_rollout_file"}

    changed = False
    seen_meta = False
    next_lines: list[str] = []
    try:
        for raw_line in path.read_text(encoding="utf-8").splitlines(keepends=True):
            line_body = raw_line[:-1] if raw_line.endswith("\n") else raw_line
            line_end = "\n" if raw_line.endswith("\n") else ""
            try:
                item = json.loads(line_body)
            except json.JSONDecodeError:
                next_lines.append(raw_line)
                continue

            payload = item.get("payload")
            if item.get("type") == "session_meta" and isinstance(payload, dict) and payload.get("id") == thread_id:
                seen_meta = True
                if payload.get("model_provider") != target_provider:
                    payload["model_provider"] = target_provider
                    raw_line = json.dumps(item, ensure_ascii=False, separators=(",", ":")) + line_end
                    changed = True
            next_lines.append(raw_line)

        if changed:
            path.write_text("".join(next_lines), encoding="utf-8")
            return {"updated": True, "error": ""}
        return {"updated": False, "error": "" if seen_meta else "session_meta_not_found"}
    except OSError as exc:
        return {"updated": False, "error": str(exc)}


def sync_selected_provider(db_path: Path, selected: list[dict[str, Any]], target_provider: str) -> dict[str, Any]:
    thread_ids = [thread["id"] for thread in selected if thread.get("id")]
    if not thread_ids:
        return {"provider_synced": 0, "provider_rollouts_synced": 0, "provider_rollout_errors": []}

    placeholders = ",".join("?" for _ in thread_ids)
    con = sqlite3.connect(db_path)
    try:
        before = con.total_changes
        con.execute(
            f"update threads set model_provider = ? where id in ({placeholders}) and coalesce(model_provider, '') != ?",
            [target_provider, *thread_ids, target_provider],
        )
        con.commit()
        provider_synced = con.total_changes - before
    finally:
        con.close()

    rollout_updates = 0
    rollout_errors: list[dict[str, Any]] = []
    for thread in selected:
        sync_result = update_rollout_model_provider(thread.get("rollout_path"), thread["id"], target_provider)
        if sync_result.get("updated"):
            rollout_updates += 1
        elif sync_result.get("error"):
            rollout_errors.append({"id": thread.get("id"), "error": sync_result.get("error")})

    return {
        "provider_synced": provider_synced,
        "provider_rollouts_synced": rollout_updates,
        "provider_rollout_errors": rollout_errors[:20],
    }


def normalize_selected_workspaces(db_path: Path, selected: list[dict[str, Any]], history_root: str | None) -> dict[str, Any]:
    updates: list[tuple[str, str]] = []
    rollout_updates = 0
    rollout_errors: list[dict[str, Any]] = []
    reasons = Counter()

    for thread in selected:
        thread_id = thread.get("id")
        if not thread_id:
            continue
        target_cwd, reason = normalized_workspace_path(thread.get("cwd"), history_root)
        if not target_cwd:
            continue
        reasons[reason] += 1
        if thread.get("cwd") != target_cwd:
            updates.append((thread_id, target_cwd))
            thread["cwd"] = target_cwd
        rollout_result = update_rollout_session_meta_cwd(thread.get("rollout_path"), thread_id, target_cwd)
        if rollout_result.get("updated"):
            rollout_updates += 1
        elif rollout_result.get("error"):
            rollout_errors.append({"id": thread_id, "error": rollout_result.get("error")})

    if updates:
        con = sqlite3.connect(db_path)
        try:
            try:
                con.executemany("update threads set cwd = ? where id = ?", [(cwd, thread_id) for thread_id, cwd in updates])
            except sqlite3.OperationalError as exc:
                return {
                    "workspace_cwd_synced": 0,
                    "workspace_rollouts_synced": rollout_updates,
                    "workspace_rollout_errors": rollout_errors[:20],
                    "workspace_normalization_reasons": dict(reasons),
                    "workspace_sync_error": str(exc),
                }
            con.commit()
            try:
                con.execute("pragma wal_checkpoint(TRUNCATE)")
            except sqlite3.OperationalError:
                pass
        finally:
            con.close()

    return {
        "workspace_cwd_synced": len(updates),
        "workspace_rollouts_synced": rollout_updates,
        "workspace_rollout_errors": rollout_errors[:20],
        "workspace_normalization_reasons": dict(reasons),
    }


def update_thread_workspace_hints(state_path: Path, thread_id: str, target_cwd: str) -> dict[str, Any]:
    if not state_path.exists():
        return {"updated": False, "error": ""}

    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"updated": False, "error": str(exc)}

    changed = False
    hints = state.get("thread-workspace-root-hints")
    if not isinstance(hints, dict):
        hints = {}
        state["thread-workspace-root-hints"] = hints
    if hints.get(thread_id) != target_cwd:
        hints[thread_id] = target_cwd
        changed = True

    for key in ("electron-saved-workspace-roots", "project-order"):
        values = state.get(key)
        if not isinstance(values, list):
            values = []
            state[key] = values
        if target_cwd not in values:
            values.append(target_cwd)
            changed = True

    active_roots = state.get("active-workspace-roots")
    if not isinstance(active_roots, list):
        active_roots = []
        state["active-workspace-roots"] = active_roots
    if active_roots[:1] != [target_cwd]:
        state["active-workspace-roots"] = [target_cwd, *[value for value in active_roots if value != target_cwd]]
        changed = True

    if not changed:
        return {"updated": False, "error": ""}

    try:
        state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return {"updated": True, "error": ""}
    except OSError as exc:
        return {"updated": False, "error": str(exc)}


def _normalize_thread_id(thread_id: str) -> str:
    return str(thread_id or "").removeprefix("local:").strip()


def _thread_id_variants(thread_id: str) -> list[str]:
    bare = _normalize_thread_id(thread_id)
    if not bare:
        return []
    return list(dict.fromkeys([bare, f"local:{bare}"]))


def _load_state_document(state_path: Path) -> dict[str, Any]:
    if not state_path.exists():
        return {}
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return state if isinstance(state, dict) else {}


def _write_state_document(state_path: Path, state: dict[str, Any]) -> None:
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _thread_timestamp_payload(row: sqlite3.Row) -> dict[str, Any]:
    updated_at = int(row["updated_at"] or 0)
    return {
        "updated_at": updated_at,
        "updated_at_ms": updated_at * 1000 if updated_at else 0,
        "created_at_ms": 0,
    }


def thread_sort_key(codex_home: Path, thread_id: str) -> dict[str, Any]:
    codex_home = normalize_path(codex_home)
    normalized_thread_id = _normalize_thread_id(thread_id)
    db_path = codex_home / "state_5.sqlite"
    if not db_path.exists():
        return {"status": "failed", "session_id": normalized_thread_id, "message": f"SQLite DB not found: {db_path}"}

    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    try:
        row = con.execute(
            """
            select id, updated_at
            from threads
            where id = ?
            """,
            (normalized_thread_id,),
        ).fetchone()
    finally:
        con.close()

    if row is None:
        return {"status": "failed", "session_id": normalized_thread_id, "message": "Thread not found in local storage"}

    return {
        "status": "ok",
        "session_id": normalized_thread_id,
        **_thread_timestamp_payload(row),
    }


def thread_sort_keys(codex_home: Path, thread_ids: list[str]) -> dict[str, Any]:
    codex_home = normalize_path(codex_home)
    normalized_ids = list(dict.fromkeys(_normalize_thread_id(thread_id) for thread_id in thread_ids if _normalize_thread_id(thread_id)))
    if not normalized_ids:
        return {"status": "ok", "sort_keys": []}

    db_path = codex_home / "state_5.sqlite"
    if not db_path.exists():
        return {"status": "failed", "message": f"SQLite DB not found: {db_path}", "sort_keys": []}

    placeholders = ",".join("?" for _ in normalized_ids)
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    try:
        rows = con.execute(
            f"""
            select id, updated_at
            from threads
            where id in ({placeholders})
            """,
            normalized_ids,
        ).fetchall()
    finally:
        con.close()

    order = {thread_id: index for index, thread_id in enumerate(normalized_ids)}
    sorted_rows = sorted(rows, key=lambda row: order.get(str(row["id"]), len(order)))
    return {
        "status": "ok",
        "sort_keys": [
            {
                "session_id": str(row["id"]),
                **_thread_timestamp_payload(row),
            }
            for row in sorted_rows
        ],
    }


def set_thread_projectless_state(codex_home: Path, thread_id: str, enabled: bool) -> dict[str, Any]:
    codex_home = normalize_path(codex_home)
    normalized_thread_id = _normalize_thread_id(thread_id)
    if not normalized_thread_id:
        return {"status": "failed", "session_id": normalized_thread_id, "message": "Missing thread id"}

    state_path = codex_home / ".codex-global-state.json"
    state = _load_state_document(state_path)
    variants = _thread_id_variants(normalized_thread_id)
    variant_set = set(variants)

    values = state.get("projectless-thread-ids")
    projectless_ids = [str(value) for value in values] if isinstance(values, list) else []
    changed = False
    if enabled:
        for variant in variants:
            if variant not in projectless_ids:
                projectless_ids.append(variant)
                changed = True
    else:
        filtered = [value for value in projectless_ids if value not in variant_set]
        if filtered != projectless_ids:
            projectless_ids = filtered
            changed = True

    hints = state.get("thread-workspace-root-hints")
    if not isinstance(hints, dict):
        hints = {}
    for variant in variants:
        if variant in hints:
            del hints[variant]
            changed = True

    if changed or not state_path.exists():
        state["projectless-thread-ids"] = projectless_ids
        state["thread-workspace-root-hints"] = hints
        _write_state_document(state_path, state)

    result = thread_sort_key(codex_home, normalized_thread_id)
    if result.get("status") != "ok":
        return result
    return {
        "status": "moved",
        "session_id": normalized_thread_id,
        "target_kind": "projectless" if enabled else "project",
        **{key: value for key, value in result.items() if key not in {"status", "session_id"}},
    }


def move_thread_workspace(codex_home: Path, thread_id: str, target_cwd: str, *, update_state_roots: bool = True) -> dict[str, Any]:
    codex_home = normalize_path(codex_home)
    normalized_thread_id = _normalize_thread_id(thread_id)
    target = clean_path(target_cwd)
    if not target:
        return {"ok": False, "status": "failed", "session_id": normalized_thread_id, "message": "Missing target workspace path"}

    db_path = codex_home / "state_5.sqlite"
    state_path = codex_home / ".codex-global-state.json"
    if not db_path.exists():
        return {"ok": False, "status": "failed", "session_id": normalized_thread_id, "message": f"SQLite DB not found: {db_path}"}

    backup_dir = backup_files(codex_home)
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    try:
        row = con.execute(
            """
            select id, cwd, rollout_path, updated_at, archived
            from threads
            where id = ?
            """,
            (normalized_thread_id,),
        ).fetchone()
        if row is None:
            return {"ok": False, "status": "failed", "session_id": normalized_thread_id, "message": "Thread not found in local storage"}

        previous_cwd = clean_path(row["cwd"])
        con.execute("update threads set cwd = ? where id = ?", (target, normalized_thread_id))
        con.commit()
        try:
            con.execute("pragma wal_checkpoint(TRUNCATE)")
        except sqlite3.OperationalError:
            pass
    finally:
        con.close()

    rollout_result = update_rollout_session_meta_cwd(row["rollout_path"], normalized_thread_id, target)
    state_result = update_thread_workspace_hints(state_path, normalized_thread_id, target) if update_state_roots else {"updated": False, "error": ""}
    return {
        "ok": True,
        "status": "moved",
        "session_id": normalized_thread_id,
        "message": "Thread workspace updated",
        "backup_dir": str(backup_dir),
        "previous_cwd": previous_cwd,
        "target_cwd": target,
        "rollout_updated": rollout_result["updated"],
        "rollout_error": rollout_result["error"],
        "state_updated": state_result["updated"],
        "state_error": state_result["error"],
        "updated_at": row["updated_at"],
        "archived": row["archived"],
    }


def cleanup_dirty_data(codex_home: Path, *, keep_latest: int = 10) -> dict[str, Any]:
    """
    Best-effort cleanup of tool-generated artifacts only.

    - Prunes old entries under `desktop_history_repair_backups/` and keeps the newest N.
    - Does NOT touch Codex core data outside that folder.
    """
    backups_root = codex_home / "desktop_history_repair_backups"
    if not backups_root.exists():
        return {"ok": True, "backups_root": str(backups_root), "removed": 0, "kept": 0}

    entries: list[Path] = []
    try:
        for child in backups_root.iterdir():
            if child.is_dir():
                entries.append(child)
    except OSError:
        return {"ok": False, "backups_root": str(backups_root), "error": "failed to list backups dir"}

    # Newest first (folder names are timestamps in YYYYMMDD-HHMMSS)
    entries.sort(key=lambda p: p.name, reverse=True)
    kept = entries[: max(0, int(keep_latest))]
    removed = 0
    errors: list[str] = []
    for child in entries[max(0, int(keep_latest)) :]:
        try:
            shutil.rmtree(child)
            removed += 1
        except OSError as exc:
            errors.append(f"{child}: {exc}")

    return {
        "ok": len(errors) == 0,
        "backups_root": str(backups_root),
        "removed": removed,
        "kept": len(kept),
        "errors": errors,
    }


def delete_archived_threads(codex_home: Path) -> dict[str, Any]:
    """
    Destructive: delete archived threads from `state_5.sqlite`, then remove references from
    `.codex-global-state.json` and `session_index.jsonl`.

    Always creates a backup via `backup_files()` first.
    """
    codex_home = codex_home.expanduser()
    db_path = codex_home / "state_5.sqlite"
    state_path = codex_home / ".codex-global-state.json"
    index_path = codex_home / "session_index.jsonl"

    for path, label in [(db_path, "SQLite DB"), (state_path, "Desktop state file")]:
        if not path.exists():
            return {"ok": False, "error": f"{label} not found: {path}"}

    threads = load_threads(db_path)
    archived_ids = [t["id"] for t in threads if t.get("archived")]
    if not archived_ids:
        return {"ok": True, "deleted": 0, "backup_dir": None}

    backup_dir = backup_files(codex_home)

    con = sqlite3.connect(db_path)
    try:
        placeholders = ",".join("?" for _ in archived_ids)
        cur = con.execute(f"delete from threads where id in ({placeholders})", archived_ids)
        con.commit()
        try:
            con.execute("pragma wal_checkpoint(TRUNCATE)")
        except sqlite3.OperationalError:
            pass
        deleted = cur.rowcount
    finally:
        con.close()

    # Remove from session index (best-effort)
    try:
        existing_index_rows = read_jsonl(index_path)
        existing_index_rows = [row for row in existing_index_rows if row.get("id") not in set(archived_ids)]
        write_jsonl(index_path, existing_index_rows)
    except OSError:
        pass

    # Remove references from desktop state file (best-effort)
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
        s = set(archived_ids)
        for key in ["pinned-thread-ids", "projectless-thread-ids"]:
            state[key] = [tid for tid in (state.get(key) or []) if tid not in s]
        hints = state.get("thread-workspace-root-hints") or {}
        if isinstance(hints, dict):
            for tid in list(hints.keys()):
                if tid in s:
                    hints.pop(tid, None)
            state["thread-workspace-root-hints"] = hints
        state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except Exception:
        pass

    return {"ok": True, "deleted": int(deleted), "backup_dir": str(backup_dir)}


def preview_delete_archived_threads(codex_home: Path) -> dict[str, Any]:
    """
    Non-destructive preview for archived-thread deletion.
    """
    codex_home = codex_home.expanduser()
    db_path = codex_home / "state_5.sqlite"
    if not db_path.exists():
        return {"ok": False, "error": f"SQLite DB not found: {db_path}"}
    threads = load_threads(db_path)
    archived = [t for t in threads if t.get("archived")]
    provider_counts = Counter((t.get("model_provider") or "<null>") for t in archived)
    return {
        "ok": True,
        "archived_total": len(archived),
        "provider_counts": dict(sorted(provider_counts.items())),
        "sample": [
            {
                "id": t.get("id"),
                "cwd": clean_path(t.get("cwd")),
                "title": preview_text(t.get("title") or t.get("first_user_message")),
            }
            for t in archived[:10]
        ],
    }
def unarchive_selected_threads(db_path: Path, thread_ids: list[str]) -> int:
    if not thread_ids:
        return 0
    placeholders = ",".join("?" for _ in thread_ids)
    con = sqlite3.connect(db_path)
    try:
        cur = con.execute(
            f"update threads set archived=0, archived_at=NULL where archived != 0 and id in ({placeholders})",
            thread_ids,
        )
        con.commit()
        try:
            con.execute("pragma wal_checkpoint(TRUNCATE)")
        except sqlite3.OperationalError:
            pass
        return cur.rowcount
    finally:
        con.close()


def repair_state(
    state_path: Path,
    threads: list[dict[str, Any]],
    current_thread_id: str | None,
    projectless_mode: str,
    history_root: str | None = None,
) -> dict[str, Any]:
    state = json.loads(state_path.read_text(encoding="utf-8"))
    thread_ids = [thread["id"] for thread in threads]
    hints: dict[str, str] = {}
    roots: list[str] = []
    normalized_to_history_root = 0
    stripped_extended_paths = 0

    for thread in threads:
        original_cwd = thread.get("cwd")
        cwd, reason = normalized_workspace_path(original_cwd, history_root)
        if not cwd:
            continue
        if reason != "kept":
            normalized_to_history_root += 1
        if clean_path(original_cwd) != original_cwd:
            stripped_extended_paths += 1
        hints[thread["id"]] = cwd
        append_unique_path(roots, cwd)

    if projectless_mode == "current-only" and current_thread_id in thread_ids:
        state["projectless-thread-ids"] = [current_thread_id]
    elif projectless_mode == "all":
        state["projectless-thread-ids"] = thread_ids
    else:
        state["projectless-thread-ids"] = []

    saved_roots: list[str] = []
    for root in list(state.get("electron-saved-workspace-roots") or []) + roots:
        normalized, _ = normalized_workspace_path(root, history_root)
        append_unique_path(saved_roots, normalized)

    state["thread-workspace-root-hints"] = hints
    state["electron-saved-workspace-roots"] = saved_roots
    state["project-order"] = list(saved_roots)
    # Threads are selected in updated_at desc order; opening the newest restored
    # workspace makes Desktop surface the chat the user just restored.
    state["active-workspace-roots"] = roots[:1]
    state["pinned-thread-ids"] = [tid for tid in state.get("pinned-thread-ids", []) if tid in thread_ids]

    atom = state.get("electron-persisted-atom-state") or {}
    sections = atom.get("sidebar-collapsed-sections-v1") or {}
    sections.update({"chats": False, "threads": False, "pinned": False})
    atom["sidebar-collapsed-sections-v1"] = sections
    state["electron-persisted-atom-state"] = atom

    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "thread_hints": len(hints),
        "saved_workspace_roots": len(saved_roots),
        "active_workspace_roots": state["active-workspace-roots"],
        "projectless_thread_ids": len(state.get("projectless-thread-ids") or []),
        "workspace_normalized_to_history_root": normalized_to_history_root,
        "workspace_extended_paths_stripped": stripped_extended_paths,
    }


def build_result(codex_home: Path, threads: list[dict[str, Any]], selected: list[dict[str, Any]], skipped: list[dict[str, Any]], dry_run: bool) -> dict[str, Any]:
    provider_counts = Counter(thread.get("model_provider") or "<null>" for thread in threads)
    skip_counts = Counter(item["reason"] for item in skipped)
    return {
        "codex_home": str(codex_home),
        "dry_run": dry_run,
        "threads_total": len(threads),
        "threads_selected": len(selected),
        "threads_skipped": len(skipped),
        "skip_reasons": dict(sorted(skip_counts.items())),
        "providers": dict(sorted(provider_counts.items())),
        "provider_diagnostics": dict(sorted(provider_counts.items())),
        "archived_total": sum(1 for thread in threads if thread.get("archived")),
        "workspace_roots_selected": len({clean_path(thread.get("cwd")) for thread in selected if thread.get("cwd")}),
    }


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

    parser = argparse.ArgumentParser(description="Safely repair Codex Desktop history visibility.")
    parser.add_argument("--codex-home", default=str(Path.home() / ".codex"))
    parser.add_argument("--current-thread-id")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--history-root", default=default_history_root(), help="Existing workspace root used for missing or empty cwd values.")
    parser.add_argument("--include-archived", action="store_true", help="Also restore archived conversations.")
    parser.add_argument("--allow-missing-cwd", action="store_true", help="Show conversations whose cwd no longer exists.")
    parser.add_argument("--allow-empty-cwd", action="store_true", help="Show conversations whose cwd exists but is empty.")
    parser.add_argument("--allow-missing-session", action="store_true", help="Show conversations whose rollout/session file is missing.")
    parser.add_argument("--unarchive-selected", action="store_true", help="Only with --include-archived: clear archived flags for selected threads.")
    parser.add_argument("--sync-provider", action="store_true", help="Align selected thread provider metadata to the current or target provider.")
    parser.add_argument("--target-provider", help="Provider key to write when --sync-provider is enabled. Defaults to config.toml model_provider.")
    parser.add_argument(
        "--projectless-mode",
        choices=["current-only", "all", "none"],
        default="none",
        help="Which selected threads to place in Desktop's projectless bucket.",
    )
    args = parser.parse_args()

    codex_home = normalize_path(args.codex_home)
    db_path = codex_home / "state_5.sqlite"
    if not db_path.exists() and (codex_home / "sqlite" / "state_5.sqlite").exists():
        db_path = codex_home / "sqlite" / "state_5.sqlite"
    state_path = codex_home / ".codex-global-state.json"
    index_path = codex_home / "session_index.jsonl"

    for path, label in [(db_path, "SQLite DB"), (state_path, "Desktop state file")]:
        if not path.exists():
            raise SystemExit(f"{label} not found: {path}")

    threads = load_threads(db_path)
    selected, skipped = selected_threads(threads, args)
    result = build_result(codex_home, threads, selected, skipped, args.dry_run)
    target_provider = args.target_provider or read_current_provider(codex_home)
    result["target_provider"] = target_provider
    result["history_root"] = safe_history_root(args.history_root)

    if args.dry_run:
        result["thread_attributions"] = thread_attributions(threads, args)
        result["selected_sample"] = [
            {"id": thread.get("id"), "cwd": clean_path(thread.get("cwd")), "title": preview_text(thread.get("title"))}
            for thread in selected[:10]
        ]
        result["skipped_sample"] = skipped[:10]
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    backup_dir = backup_files(codex_home)
    existing_index_rows = read_jsonl(index_path)
    write_jsonl(index_path, make_index_rows(existing_index_rows, selected))
    result["backup_dir"] = str(backup_dir)
    result["session_index_rows"] = len(selected)

    if args.include_archived and args.unarchive_selected:
        result["unarchived"] = unarchive_selected_threads(db_path, [thread["id"] for thread in selected])
    else:
        result["unarchived"] = 0

    result.update(normalize_selected_workspaces(db_path, selected, args.history_root))
    result.update(repair_state(state_path, selected, args.current_thread_id, args.projectless_mode, args.history_root))
    if args.sync_provider:
        if not target_provider:
            result["provider_sync_error"] = "target_provider_missing"
        else:
            result.update(sync_selected_provider(db_path, selected, target_provider))
    (backup_dir / "repair-report.json").write_text(
        json.dumps(
            {
                "summary": result,
                "thread_attributions": thread_attributions(threads, args),
                "skipped": skipped,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
