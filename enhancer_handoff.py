from __future__ import annotations

import base64
import json
import re
import sqlite3
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import repair_codex_desktop_history as history_repair


MAX_RECENT_MESSAGES = 8
MAX_MESSAGE_CHARS = 1200
MAX_GIT_STATUS_LINES = 30
MAX_TAKEOVER_FIELD_CHARS = 700
THREAD_ID_RE = re.compile(r"^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$", re.IGNORECASE)
RESUME_META_MARKERS = (
    "continue the same task",
    "do not re-analyze from zero",
    "read this handoff file",
    "embedded handoff",
    "handoff file path",
    "resume entry",
)


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
    return text[: max(0, limit - 3)].rstrip() + "..."


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
            payload = row.get("item")
        if not isinstance(payload, dict):
            continue
        if payload.get("type") not in {"message", None}:
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


def _is_resume_meta_message(text: str) -> bool:
    lowered = str(text or "").lower()
    if any(marker in lowered for marker in RESUME_META_MARKERS):
        return True
    # Chinese resume prompts often include an English "handoff" token alongside
    # repeated instructions to continue the same task or read a file path.
    return "handoff" in lowered and any(
        marker in lowered
        for marker in ("继续", "不要从零", "文件路径", "读取", "内联")
    )


def _latest_non_meta_message(recent_messages: list[dict[str, str]], role: str) -> str:
    for message in reversed(recent_messages):
        if message.get("role") != role:
            continue
        text = str(message.get("text") or "").strip()
        if text and not _is_resume_meta_message(text):
            return text
    return ""


def _first_non_meta_text(*values: str) -> str:
    for value in values:
        text = str(value or "").strip()
        if text and not _is_resume_meta_message(text):
            return text
    return ""


def _handoff_section_value(handoff_content: str, prefix: str) -> str:
    for line in handoff_content.splitlines():
        if line.startswith(prefix):
            value = line.removeprefix(prefix).strip()
            if _is_resume_meta_message(value):
                return ""
            return _preview_text(value, MAX_TAKEOVER_FIELD_CHARS)
    return ""


def _looks_like_thread_id(value: str) -> bool:
    return bool(THREAD_ID_RE.match(str(value or "").strip()))


def _derive_objective_from_evidence(evidence: str) -> str:
    text = str(evidence or "")
    patterns = (
        r"做完了\s+(.+?)\s+的第一版",
        r"completed\s+(.+?)(?:\.|$)",
        r"`[0-9a-f]{7,40}\s+(.+?)`",
    )
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if not match:
            continue
        candidate = match.group(1).strip(" `。.;:")
        if not candidate:
            continue
        words = candidate.split()
        if words and all(part.islower() or part in {"+", "&", "/", "-"} for part in words):
            candidate = " ".join(word.capitalize() if word.isalpha() else word for word in words)
        return _preview_text(candidate, MAX_TAKEOVER_FIELD_CHARS)
    return ""


def _derive_next_action_from_evidence(evidence: str) -> str:
    objective = _derive_objective_from_evidence(evidence)
    if not objective:
        return ""
    return _preview_text(f"Continue {objective}.", MAX_TAKEOVER_FIELD_CHARS)


def _run_git(workspace: Path, args: list[str]) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=workspace,
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    if result.returncode != 0:
        return ""
    return result.stdout.rstrip()


def _collect_local_snapshot(cwd: str) -> dict[str, object]:
    if not cwd:
        return {"workspace_exists": False, "git_available": False, "branch": "", "status": []}

    workspace = Path(cwd)
    try:
        if not workspace.exists() or not workspace.is_dir():
            return {"workspace_exists": False, "git_available": False, "branch": "", "status": []}
    except OSError:
        return {"workspace_exists": False, "git_available": False, "branch": "", "status": []}

    snapshot: dict[str, object] = {
        "workspace_exists": True,
        "git_available": False,
        "branch": "",
        "status": [],
    }
    try:
        inside = _run_git(workspace, ["rev-parse", "--is-inside-work-tree"])
        if inside != "true":
            return snapshot
        branch = _run_git(workspace, ["branch", "--show-current"]) or _run_git(workspace, ["rev-parse", "--short", "HEAD"])
        status = _run_git(workspace, ["status", "--short"])
    except (OSError, subprocess.SubprocessError):
        return snapshot

    snapshot["git_available"] = True
    snapshot["branch"] = branch or "(detached or unknown)"
    snapshot["status"] = status.splitlines()[:MAX_GIT_STATUS_LINES] if status else []
    return snapshot


def _render_handoff(
    record: ThreadRecord,
    handoff_path: Path,
    recent_messages: list[dict[str, str]],
    local_snapshot: dict[str, object],
) -> str:
    created_at = datetime.now().astimezone().isoformat()
    real_user_request = _latest_non_meta_message(recent_messages, "user")
    latest_raw_user_request = _latest_message(recent_messages, "user")
    objective_source = _first_non_meta_text(record.title, record.first_user_message, real_user_request)
    objective = _preview_text(objective_source or record.thread_id, 200)
    last_user_request = _preview_text(real_user_request, 240)
    original_request = _first_non_meta_text(record.first_user_message, real_user_request)
    if (
        latest_raw_user_request
        and _is_resume_meta_message(latest_raw_user_request)
        and original_request
        and last_user_request == _preview_text(original_request, 240)
    ):
        last_user_request = ""
    last_assistant_response = _preview_text(_latest_non_meta_message(recent_messages, "assistant"), 240)
    lines = [
        "# AI Strategist Handoff",
        "",
        f"- Created at: {created_at}",
        f"- Thread ID: {record.thread_id}",
        f"- Workspace: {record.cwd or '(unknown)'}",
        f"- Source rollout: {record.rollout_path or '(missing)'}",
        f"- Title: {objective}",
    ]

    if original_request:
        lines.extend(
            [
                "",
                "## Original Request",
                "",
                original_request,
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
            "## Local Snapshot",
            "",
            f"- Workspace exists: {'yes' if local_snapshot.get('workspace_exists') else 'no'}",
            f"- Git branch: {local_snapshot.get('branch') or '(not a git workspace)'}",
            "- Git status:",
        ]
    )

    status_lines = local_snapshot.get("status")
    if isinstance(status_lines, list) and status_lines:
        lines.extend([f"  - `{line}`" for line in status_lines])
        if len(status_lines) >= MAX_GIT_STATUS_LINES:
            lines.append("  - ... truncated; inspect git status locally for the full list.")
    elif local_snapshot.get("git_available"):
        lines.append("  - clean")
    else:
        lines.append("  - unavailable")

    lines.extend(
        [
            "",
            "## Progress Ledger",
            "",
            f"- Done / current evidence: {last_assistant_response or 'Infer from recent messages and current workspace state.'}",
            f"- Next action cue: {last_user_request or 'Infer from current workspace state.'}",
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
            "4. Communicate with the user in Chinese; task work artifacts may remain in English when appropriate.",
        ]
    )

    if recent_messages:
        lines.extend(["", "## Recent Messages", ""])
        for message in recent_messages:
            if _is_resume_meta_message(message.get("text", "")):
                continue
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



def _build_takeover_prompt(handoff_path: Path, handoff_content: str) -> str:
    objective = _handoff_section_value(handoff_content, "- Current objective:")
    next_action = _handoff_section_value(handoff_content, "- Next action cue:")
    evidence = _handoff_section_value(handoff_content, "- Done / current evidence:")
    workspace = _handoff_section_value(handoff_content, "- Workspace:")
    if _looks_like_thread_id(objective) or not objective:
        objective = _derive_objective_from_evidence(evidence) or objective
    if next_action == "Infer from current workspace state.":
        next_action = _derive_next_action_from_evidence(evidence)
    topic = objective or next_action or "Handoff takeover"
    lines = [
        f"接手任务：{topic}",
        "Continue the same task; do not restart analysis from zero.",
        f"Handoff file: {handoff_path}",
    ]
    if workspace:
        lines.append(f"Workspace: {workspace}")
    if objective:
        lines.append(f"Objective: {objective}")
    if next_action:
        lines.append(f"Next action cue: {next_action}")
    if evidence:
        lines.append(f"Current evidence: {evidence}")
    lines.extend(
        [
            "Read the handoff file only if these fields are insufficient.",
            "After you understand the handoff, propose your next work plan and wait for the user's approval before executing it.",
            "Communicate with the user in Chinese, but you may keep task work artifacts in English when appropriate.",
        ]
    )
    return (
        "\n".join(lines)
    )


def create_handoff(codex_home: Path, thread_id: str, title_hint: str = "") -> dict[str, object]:
    codex_home = history_repair.normalize_path(codex_home)
    normalized_thread_id = _normalize_thread_id(thread_id)
    if not normalized_thread_id:
        return {"ok": False, "status": "failed", "message": "Missing thread id"}

    record = _load_thread_record(codex_home, normalized_thread_id)
    recent_messages = _collect_recent_messages(record.rollout_path)
    local_snapshot = _collect_local_snapshot(record.cwd)

    handoff_root = _handoff_root(codex_home, record.cwd)
    handoff_root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    name_seed = _first_non_meta_text(title_hint, record.title, record.first_user_message) or record.thread_id
    handoff_path = handoff_root / f"{stamp}-{_safe_slug(_preview_text(name_seed, 48), record.thread_id)}-handoff.md"

    handoff_content = _render_handoff(record, handoff_path, recent_messages, local_snapshot)
    handoff_path.write_text(handoff_content, encoding="utf-8")

    prompt = _build_takeover_prompt(handoff_path, handoff_content)
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
