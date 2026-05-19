import argparse
import json
import shutil
import sqlite3
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


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
    return bool(thread.get("has_user_event"))


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


def repair_state(state_path: Path, threads: list[dict[str, Any]], current_thread_id: str | None, projectless_mode: str) -> dict[str, Any]:
    state = json.loads(state_path.read_text(encoding="utf-8"))
    thread_ids = [thread["id"] for thread in threads]
    hints: dict[str, str] = {}
    roots: list[str] = []

    for thread in threads:
        cwd = clean_path(thread.get("cwd"))
        if not cwd:
            continue
        hints[thread["id"]] = cwd
        if cwd not in roots:
            roots.append(cwd)

    if projectless_mode == "current-only" and current_thread_id in thread_ids:
        state["projectless-thread-ids"] = [current_thread_id]
    elif projectless_mode == "all":
        state["projectless-thread-ids"] = thread_ids
    else:
        state["projectless-thread-ids"] = []

    state["thread-workspace-root-hints"] = hints
    state["electron-saved-workspace-roots"] = roots
    state["project-order"] = roots
    active = [root for root in state.get("active-workspace-roots", []) if root in roots]
    state["active-workspace-roots"] = active or roots[:1]
    state["pinned-thread-ids"] = [tid for tid in state.get("pinned-thread-ids", []) if tid in thread_ids]

    atom = state.get("electron-persisted-atom-state") or {}
    sections = atom.get("sidebar-collapsed-sections-v1") or {}
    sections.update({"chats": False, "threads": False, "pinned": False})
    atom["sidebar-collapsed-sections-v1"] = sections
    state["electron-persisted-atom-state"] = atom

    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "thread_hints": len(hints),
        "saved_workspace_roots": len(roots),
        "active_workspace_roots": state["active-workspace-roots"],
        "projectless_thread_ids": len(state.get("projectless-thread-ids") or []),
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
    parser.add_argument("--include-archived", action="store_true", help="Also restore archived conversations.")
    parser.add_argument("--allow-missing-cwd", action="store_true", help="Show conversations whose cwd no longer exists.")
    parser.add_argument("--allow-empty-cwd", action="store_true", help="Show conversations whose cwd exists but is empty.")
    parser.add_argument("--allow-missing-session", action="store_true", help="Show conversations whose rollout/session file is missing.")
    parser.add_argument("--unarchive-selected", action="store_true", help="Only with --include-archived: clear archived flags for selected threads.")
    parser.add_argument(
        "--projectless-mode",
        choices=["current-only", "all", "none"],
        default="none",
        help="Which selected threads to place in Desktop's projectless bucket.",
    )
    args = parser.parse_args()

    codex_home = Path(args.codex_home)
    db_path = codex_home / "state_5.sqlite"
    state_path = codex_home / ".codex-global-state.json"
    index_path = codex_home / "session_index.jsonl"

    for path, label in [(db_path, "SQLite DB"), (state_path, "Desktop state file")]:
        if not path.exists():
            raise SystemExit(f"{label} not found: {path}")

    threads = load_threads(db_path)
    selected, skipped = selected_threads(threads, args)
    result = build_result(codex_home, threads, selected, skipped, args.dry_run)

    if args.dry_run:
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

    result.update(repair_state(state_path, selected, args.current_thread_id, args.projectless_mode))
    (backup_dir / "repair-report.json").write_text(json.dumps({"summary": result, "skipped": skipped}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
