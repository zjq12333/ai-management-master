import argparse
import json
import sqlite3
from pathlib import Path

DOCUMENTS_ROOT = str(Path.home() / "Documents")
DOCUMENTS_ROOT_LOWER = DOCUMENTS_ROOT.lower()


def clean_cwd(cwd: str | None) -> str | None:
    if not cwd:
        return None
    if cwd.startswith("\\\\?\\"):
        return cwd[4:]
    return cwd


def compact_root(cwd: str | None) -> str | None:
    clean = clean_cwd(cwd)
    if not clean:
        return None
    lower = clean.lower()
    if lower.startswith("d:\\"):
        return "D:\\"
    if lower.startswith(DOCUMENTS_ROOT_LOWER):
        return DOCUMENTS_ROOT
    return clean


def load_threads(db_path: Path) -> list[dict]:
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    try:
        return [
            dict(row)
            for row in con.execute(
                """
                select id, cwd, archived, model_provider, updated_at
                from threads
                order by updated_at desc
                """
            )
        ]
    finally:
        con.close()


def unarchive_threads(db_path: Path) -> int:
    con = sqlite3.connect(db_path)
    try:
        cur = con.execute(
            "update threads set archived=0, archived_at=NULL where archived != 0"
        )
        changed = cur.rowcount
        con.commit()
        try:
            con.execute("pragma wal_checkpoint(TRUNCATE)")
        except sqlite3.OperationalError:
            pass
        return changed
    finally:
        con.close()


def repair_state(
    state_path: Path,
    threads: list[dict],
    current_thread_id: str | None,
    projectless_mode: str,
) -> dict:
    state = json.loads(state_path.read_text(encoding="utf-8"))

    thread_ids = [thread["id"] for thread in threads]
    hints: dict[str, str] = {}
    exact_roots: list[str] = []
    broad_roots: list[str] = []

    for thread in threads:
        cwd = clean_cwd(thread.get("cwd"))
        if not cwd:
            continue
        hints[thread["id"]] = cwd
        if cwd not in exact_roots:
            exact_roots.append(cwd)
        broad = compact_root(cwd)
        if broad and broad not in broad_roots:
            broad_roots.append(broad)

    if projectless_mode == "current-only" and current_thread_id in thread_ids:
        state["projectless-thread-ids"] = [current_thread_id]
    elif projectless_mode == "none":
        state["projectless-thread-ids"] = []
    else:
        state["projectless-thread-ids"] = thread_ids

    state["thread-workspace-root-hints"] = hints
    state["electron-saved-workspace-roots"] = exact_roots
    state["project-order"] = exact_roots
    state["active-workspace-roots"] = broad_roots or exact_roots[:1]

    atom = state.get("electron-persisted-atom-state") or {}
    sections = atom.get("sidebar-collapsed-sections-v1") or {}
    sections.update({"chats": False, "threads": False, "pinned": False})
    atom["sidebar-collapsed-sections-v1"] = sections
    state["electron-persisted-atom-state"] = atom

    state_path.write_text(
        json.dumps(state, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )

    return {
        "thread_hints": len(hints),
        "saved_workspace_roots": len(exact_roots),
        "active_workspace_roots": broad_roots or exact_roots[:1],
        "projectless_thread_ids": len(state.get("projectless-thread-ids") or []),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Repair Codex Desktop history visibility and workspace placement."
    )
    parser.add_argument("--codex-home", default=str(Path.home() / ".codex"))
    parser.add_argument("--current-thread-id")
    parser.add_argument(
        "--projectless-mode",
        choices=["current-only", "all", "none"],
        default="current-only",
        help="Which threads to place in the Desktop projectless bucket.",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    codex_home = Path(args.codex_home)
    db_path = codex_home / "state_5.sqlite"
    state_path = codex_home / ".codex-global-state.json"

    if not db_path.exists():
        raise SystemExit(f"SQLite DB not found: {db_path}")
    if not state_path.exists():
        raise SystemExit(f"Desktop state file not found: {state_path}")

    threads = load_threads(db_path)
    provider_counts: dict[str, int] = {}
    archived_count = 0
    for thread in threads:
        provider_counts[thread.get("model_provider") or "<null>"] = (
            provider_counts.get(thread.get("model_provider") or "<null>", 0) + 1
        )
        if thread.get("archived"):
            archived_count += 1

    result = {
        "codex_home": str(codex_home),
        "threads": len(threads),
        "providers": provider_counts,
        "archived_before": archived_count,
        "dry_run": args.dry_run,
    }

    if args.dry_run:
        roots = sorted(
            {clean_cwd(thread.get("cwd")) for thread in threads if thread.get("cwd")}
        )
        result["workspace_roots_that_would_be_written"] = len(roots)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    unarchived = unarchive_threads(db_path)
    state_result = repair_state(
        state_path=state_path,
        threads=threads,
        current_thread_id=args.current_thread_id,
        projectless_mode=args.projectless_mode,
    )
    result["unarchived"] = unarchived
    result.update(state_result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
