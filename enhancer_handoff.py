from __future__ import annotations

import base64
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import repair_codex_desktop_history as history_repair


MAX_RECENT_MESSAGES = 8
MAX_MESSAGE_CHARS = 1200


@dataclass
class ThreadRecord:
    thread_id: str
    cwd: str
    rollout_path: str
    title: str
    first_user_message: str
    updated_at: int


def _normalize_thread_id(thread_id: str) -> str:
    return str(thread_id or "").removeprefix("local:").strip()


def _preview_text(value: str | None, limit: int = 160) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


def _safe_slug(value: str, fallback: str) -> str:
    normalized = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in value).strip("-")
    return normalized or fallback


def _extract_text_fragments(value: Any) -> list[str]:
    fragments: list[str] = []
    if isinstance(value, str):
        if value.strip():
            fragments.append(value.strip())
        return fragments
    if isinstance(value, list):
        for item in value:
            fragments.extend(_extract_text_fragments(item))
        return fragments
    if isinstance(value, dict):
        text = value.get("text")
        if isinstance(text, str) and text.strip():
            fragments.append(text.strip())
        if "content" in value:
            fragments.extend(_extract_text_fragments(value.get("content")))
        if "parts" in value:
            fragments.extend(_extract_text_fragments(value.get("parts")))
        if "message" in value and isinstance(value.get("message"), str):
            fragments.extend(_extract_text_fragments(value.get("message")))
        return fragments
    return fragments


def _load_thread_record(codex_home: Path, thread_id: str) -> ThreadRecord:
    db_path = codex_home / "state_5.sqlite"
    if not db_path.exists():
        raise RuntimeError(f"SQLite DB not found: {db_path}")

    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    try:
        row = con.execute(
            """
            select id, cwd, rollout_path, title, first_user_message, updated_at
            from threads
            where id = ?
            """,
            (thread_id,),
        ).fetchone()
    finally:
        con.close()

    if row is None:
        raise RuntimeError("Thread not found in local storage")

    return ThreadRecord(
        thread_id=str(row["id"]),
        cwd=history_repair.clean_path(row["cwd"]) or "",
        rollout_path=history_repair.clean_path(row["rollout_path"]) or "",
        title=str(row["title"] or ""),
        first_user_message=str(row["first_user_message"] or ""),
        updated_at=int(row["updated_at"] or 0),
    )


def _collect_recent_messages(rollout_path: str) -> list[dict[str, str]]:
    path = Path(rollout_path)
    if not rollout_path or not path.exists():
        return []

    recent: list[dict[str, str]] = []
    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not raw_line.strip():
            continue
        try:
            row = json.loads(raw_line)
        except json.JSONDecodeError:
            continue

        if row.get("type") != "response_item":
            continue
        payload = row.get("payload")
        if not isinstance(payload, dict):
            continue
        if payload.get("type") != "message":
            continue

        role = str(payload.get("role") or "").strip().lower()
        if role not in {"user", "assistant"}:
            continue

        fragments = _extract_text_fragments(payload.get("content"))
        text = "\n".join(part for part in fragments if part).strip()
        if not text:
            continue

        recent.append(
            {
                "role": role,
                "text": text[:MAX_MESSAGE_CHARS],
            }
        )

    return recent[-MAX_RECENT_MESSAGES:]


def _handoff_root(codex_home: Path, cwd: str) -> Path:
    if cwd:
        workspace = Path(cwd)
        try:
            if workspace.exists() and workspace.is_dir():
                return workspace / ".ai-strategist" / "handoffs"
        except OSError:
            pass
    return codex_home / "codexmate" / "handoffs"


def _latest_message(recent_messages: list[dict[str, str]], role: str) -> str:
    for message in reversed(recent_messages):
        if message.get("role") == role:
            return str(message.get("text") or "").strip()
    return ""


def _render_handoff(record: ThreadRecord, handoff_path: Path, recent_messages: list[dict[str, str]]) -> str:
    created_at = datetime.now().astimezone().isoformat()
    objective = _preview_text(record.title or record.first_user_message or record.thread_id, 200)
    last_user_request = _preview_text(_latest_message(recent_messages, "user") or record.first_user_message, 240)
    last_assistant_response = _preview_text(_latest_message(recent_messages, "assistant"), 240)
    lines = [
        "# AI Strategist Handoff",
        "",
        f"- Created at: {created_at}",
        f"- Thread ID: {record.thread_id}",
        f"- Workspace: {record.cwd or '(unknown)'}",
        f"- Source rollout: {record.rollout_path or '(missing)'}",
        f"- Title: {objective}",
    ]

    if record.first_user_message.strip():
        lines.extend(
            [
                "",
                "## Original Request",
                "",
                record.first_user_message.strip(),
            ]
        )

    lines.extend(
        [
            "",
            "## Task State",
            "",
            f"- Current objective: {objective}",
            f"- Last user request: {last_user_request or '(not captured)'}",
            f"- Last assistant response: {last_assistant_response or '(not captured)'}",
            f"- Active workspace: {record.cwd or '(unknown)'}",
            "",
            "## Progress Ledger",
            "",
            "- Done: Infer only from this handoff, recent messages, and the current workspace state.",
            "- In progress / next step: Continue from the last user request above.",
            "- Relevant files: Not captured in this stage; inspect only files needed for the next concrete step.",
            "",
            "## Verification",
            "",
            "- Latest verified commands: Not captured in this stage.",
            "- Before finalizing new work, run the smallest relevant local check and report the result.",
            "",
            "## Watchouts",
            "",
            "- Do not restart broad repo analysis unless this handoff is insufficient.",
            "- Do not revert unrelated local changes; treat the workspace as user-owned.",
            "- Prefer fresh local state over assumptions when files, git status, processes, or builds matter.",
            "",
            "## Continue Rules",
            "",
            "1. Continue the same task; do not restart analysis from zero.",
            "2. Read only the files needed for the next concrete step.",
            "3. Prefer the workspace state and this handoff over replaying the full rollout.",
        ]
    )

    if recent_messages:
        lines.extend(["", "## Recent Messages", ""])
        for message in recent_messages:
            role = "User" if message["role"] == "user" else "Assistant"
            lines.append(f"### {role}")
            lines.append("")
            lines.append(message["text"])
            lines.append("")

    lines.extend(
        [
            "## Resume Entry",
            "",
            f"- Handoff file: {handoff_path}",
            f"- Workspace root: {record.cwd or '(unknown)'}",
            "",
        ]
    )
    return "\n".join(lines)


def _build_takeover_prompt(handoff_path: Path) -> str:
    return (
        "继续同一任务，不要从零重新分析。\n"
        f"先读取这个 handoff 文件：{handoff_path}\n"
        "仅在 handoff 不足以支撑下一步时，再补读必要文件或最新本地状态。"
    )


def create_handoff(codex_home: Path, thread_id: str, title_hint: str = "") -> dict[str, object]:
    codex_home = history_repair.normalize_path(codex_home)
    normalized_thread_id = _normalize_thread_id(thread_id)
    if not normalized_thread_id:
        return {"ok": False, "status": "failed", "message": "Missing thread id"}

    record = _load_thread_record(codex_home, normalized_thread_id)
    recent_messages = _collect_recent_messages(record.rollout_path)

    handoff_root = _handoff_root(codex_home, record.cwd)
    handoff_root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    name_seed = title_hint or record.title or record.first_user_message or record.thread_id
    handoff_path = handoff_root / f"{stamp}-{_safe_slug(_preview_text(name_seed, 48), record.thread_id)}-handoff.md"

    handoff_content = _render_handoff(record, handoff_path, recent_messages)
    handoff_path.write_text(handoff_content, encoding="utf-8")

    prompt = _build_takeover_prompt(handoff_path)
    return {
        "ok": True,
        "status": "handoff_ready",
        "message": "Handoff prepared for same-workspace takeover.",
        "session_id": record.thread_id,
        "title": record.title or title_hint or record.thread_id,
        "cwd": record.cwd,
        "workspace_path": record.cwd,
        "handoff_path": str(handoff_path),
        "prompt": prompt,
        "prompt_b64": base64.b64encode(prompt.encode("utf-8")).decode("ascii"),
        "recent_message_count": len(recent_messages),
    }
