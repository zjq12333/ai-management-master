import json
import sqlite3
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import enhancer_handoff


class EnhancerHandoffTests(unittest.TestCase):
    def test_create_handoff_writes_workspace_local_file_and_prompt(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            codex_home = root / ".codex"
            codex_home.mkdir(parents=True, exist_ok=True)
            workspace = root / "workspace"
            workspace.mkdir()
            rollout = codex_home / "rollout.jsonl"
            rollout.write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "type": "response_item",
                                "payload": {
                                    "type": "message",
                                    "role": "user",
                                    "content": [{"type": "input_text", "text": "先检查 handoff 逻辑"}],
                                },
                            },
                            ensure_ascii=False,
                        ),
                        json.dumps(
                            {
                                "type": "response_item",
                                "payload": {
                                    "type": "message",
                                    "role": "assistant",
                                    "content": [{"type": "output_text", "text": "我会先看当前状态"}],
                                },
                            },
                            ensure_ascii=False,
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            db_path = codex_home / "state_5.sqlite"
            con = sqlite3.connect(db_path)
            con.execute(
                """
                create table threads (
                    id text primary key,
                    cwd text,
                    rollout_path text,
                    title text,
                    first_user_message text,
                    updated_at integer
                )
                """
            )
            con.execute(
                """
                insert into threads (id, cwd, rollout_path, title, first_user_message, updated_at)
                values (?, ?, ?, ?, ?, ?)
                """,
                (
                    "thread-1",
                    str(workspace),
                    str(rollout),
                    "测试移交",
                    "先检查 handoff 逻辑",
                    1,
                ),
            )
            con.commit()
            con.close()

            result = enhancer_handoff.create_handoff(codex_home, "thread-1", "测试移交")
            self.assertTrue(result["ok"])
            self.assertEqual(result["status"], "handoff_ready")
            handoff_path = Path(result["handoff_path"])
            self.assertTrue(handoff_path.exists())
            self.assertEqual(handoff_path.parent, workspace / ".ai-strategist" / "handoffs")
            content = handoff_path.read_text(encoding="utf-8")
            self.assertIn("测试移交", content)
            self.assertIn("## Task State", content)
            self.assertIn("- Current objective: 测试移交", content)
            self.assertIn("- Last user request: 先检查 handoff 逻辑", content)
            self.assertIn("- Last assistant response: 我会先看当前状态", content)
            self.assertIn("## Local Snapshot", content)
            self.assertIn("## Progress Ledger", content)
            self.assertIn("- Done / current evidence: 我会先看当前状态", content)
            self.assertIn("- Next action cue: 先检查 handoff 逻辑", content)
            self.assertIn("## Verification", content)
            self.assertIn("## Watchouts", content)
            self.assertIn("Communicate with the user in Chinese", content)
            self.assertIn("先检查 handoff 逻辑", content)
            self.assertIn("我会先看当前状态", content)
            self.assertIn(str(handoff_path), result["prompt"])
            self.assertTrue(result["prompt"].startswith("接手任务：测试移交"))
            self.assertIn("wait for the user's approval before executing it", result["prompt"])
            self.assertNotIn("Start by executing the Next action cue", result["prompt"])
            self.assertIn("Objective:", result["prompt"])
            self.assertIn("Next action cue:", result["prompt"])
            self.assertIn(
                "Communicate with the user in Chinese, but you may keep task work artifacts in English when appropriate.",
                result["prompt"],
            )
            self.assertNotIn("## Handoff Summary", result["prompt"])
            self.assertLessEqual(len(result["prompt"]), 1800)

    def test_create_handoff_falls_back_to_codex_home_when_workspace_missing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            codex_home = root / ".codex"
            codex_home.mkdir(parents=True, exist_ok=True)
            db_path = codex_home / "state_5.sqlite"
            con = sqlite3.connect(db_path)
            con.execute(
                """
                create table threads (
                    id text primary key,
                    cwd text,
                    rollout_path text,
                    title text,
                    first_user_message text,
                    updated_at integer
                )
                """
            )
            con.execute(
                """
                insert into threads (id, cwd, rollout_path, title, first_user_message, updated_at)
                values (?, ?, ?, ?, ?, ?)
                """,
                ("thread-2", "", "", "无工作目录", "直接回退", 1),
            )
            con.commit()
            con.close()

            result = enhancer_handoff.create_handoff(codex_home, "thread-2")

            handoff_path = Path(result["handoff_path"])
            self.assertTrue(handoff_path.exists())
            self.assertEqual(handoff_path.parent, codex_home / "codexmate" / "handoffs")

    def test_create_handoff_includes_git_snapshot_when_workspace_is_git_repo(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            codex_home = root / ".codex"
            codex_home.mkdir(parents=True, exist_ok=True)
            workspace = root / "workspace"
            workspace.mkdir()
            subprocess.run(["git", "init", "-b", "handoff-test"], cwd=workspace, check=True, capture_output=True)
            (workspace / "tracked.txt").write_text("before\n", encoding="utf-8")
            subprocess.run(["git", "add", "tracked.txt"], cwd=workspace, check=True, capture_output=True)
            subprocess.run(
                ["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-m", "seed"],
                cwd=workspace,
                check=True,
                capture_output=True,
            )
            (workspace / "tracked.txt").write_text("after\n", encoding="utf-8")
            (workspace / "new.txt").write_text("new\n", encoding="utf-8")

            db_path = codex_home / "state_5.sqlite"
            con = sqlite3.connect(db_path)
            con.execute(
                """
                create table threads (
                    id text primary key,
                    cwd text,
                    rollout_path text,
                    title text,
                    first_user_message text,
                    updated_at integer
                )
                """
            )
            con.execute(
                """
                insert into threads (id, cwd, rollout_path, title, first_user_message, updated_at)
                values (?, ?, ?, ?, ?, ?)
                """,
                ("thread-3", str(workspace), "", "Git 快照", "继续当前改动", 1),
            )
            con.commit()
            con.close()

            result = enhancer_handoff.create_handoff(codex_home, "thread-3")

            content = Path(result["handoff_path"]).read_text(encoding="utf-8")
            self.assertIn("## Local Snapshot", content)
            self.assertIn("- Git branch: handoff-test", content)
            self.assertIn(" M tracked.txt", content)
            self.assertIn("?? new.txt", content)

    def test_create_handoff_gracefully_degrades_when_git_is_missing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            codex_home = root / ".codex"
            codex_home.mkdir(parents=True, exist_ok=True)
            workspace = root / "workspace"
            workspace.mkdir()

            db_path = codex_home / "state_5.sqlite"
            con = sqlite3.connect(db_path)
            con.execute(
                """
                create table threads (
                    id text primary key,
                    cwd text,
                    rollout_path text,
                    title text,
                    first_user_message text,
                    updated_at integer
                )
                """
            )
            con.execute(
                """
                insert into threads (id, cwd, rollout_path, title, first_user_message, updated_at)
                values (?, ?, ?, ?, ?, ?)
                """,
                ("thread-no-git", str(workspace), "", "No Git", "继续当前改动", 1),
            )
            con.commit()
            con.close()

            with mock.patch("enhancer_handoff.shutil.which", return_value=None):
                result = enhancer_handoff.create_handoff(codex_home, "thread-no-git")

            content = Path(result["handoff_path"]).read_text(encoding="utf-8")
            self.assertIn("## Local Snapshot", content)
            self.assertIn("- Git branch: (not a git workspace)", content)
            self.assertIn("  - unavailable", content)

    def test_create_handoff_filters_resume_meta_messages(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            codex_home = root / ".codex"
            codex_home.mkdir(parents=True, exist_ok=True)
            workspace = root / "workspace"
            workspace.mkdir()
            previous_handoff = workspace / ".ai-strategist" / "handoffs" / "previous-handoff.md"
            previous_handoff.parent.mkdir(parents=True, exist_ok=True)
            previous_handoff.write_text("# Previous\n\nKeep going.\n", encoding="utf-8")
            resume_meta = (
                "Continue the same task, do not re-analyze from zero. "
                f"Read this handoff file first: {previous_handoff}. "
                "Embedded Handoff # AI Strategist Handoff"
            )
            rollout = codex_home / "rollout.jsonl"
            rollout.write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "type": "response_item",
                                "item": {
                                    "role": "user",
                                    "content": [{"type": "input_text", "text": "Build the transfer feature."}],
                                },
                            }
                        ),
                        json.dumps(
                            {
                                "type": "response_item",
                                "item": {
                                    "role": "assistant",
                                    "content": [{"type": "output_text", "text": "Implemented phase one."}],
                                },
                            }
                        ),
                        json.dumps(
                            {
                                "type": "response_item",
                                "item": {
                                    "role": "user",
                                    "content": [{"type": "input_text", "text": resume_meta}],
                                },
                            }
                        ),
                    ]
                ),
                encoding="utf-8",
            )

            db_path = codex_home / "state_5.sqlite"
            con = sqlite3.connect(db_path)
            con.execute(
                """
                create table threads (
                    id text primary key,
                    cwd text,
                    rollout_path text,
                    title text,
                    first_user_message text,
                    updated_at integer
                )
                """
            )
            con.execute(
                "insert into threads values (?, ?, ?, ?, ?, ?)",
                ("thread-4", str(workspace), str(rollout), resume_meta, resume_meta, 1),
            )
            con.commit()
            con.close()

            result = enhancer_handoff.create_handoff(codex_home, "thread-4")

            content = Path(result["handoff_path"]).read_text(encoding="utf-8")
            prompt = result["prompt"]
            self.assertIn("- Title: Build the transfer feature.", content)
            self.assertIn("## Original Request\n\nBuild the transfer feature.", content)
            self.assertIn("- Next action cue: Infer from current workspace state.", content)
            self.assertNotIn("Embedded Handoff", content)
            self.assertNotIn("Read this handoff file first", prompt)
            self.assertIn("Objective: Build the transfer feature.", prompt)
            self.assertNotIn("## Handoff Summary", prompt)
            self.assertLessEqual(len(prompt), 1800)

    def test_takeover_prompt_derives_objective_from_evidence_when_title_is_thread_id(self):
        thread_id = "019e6ec7-3add-7d73-aa56-8bb639a5649a"
        handoff_content = "\n".join(
            [
                "# AI Strategist Handoff",
                "",
                f"- Title: {thread_id}",
                "",
                "## Task State",
                "",
                f"- Current objective: {thread_id}",
                "- Last user request: (not captured)",
                "- Last assistant response: 已把这个版本固定成 Git 提交： `e8b1f82 Add request ledger token savings meter` 这次做完了 Request Ledger + Token Savings Meter 的第一版。",
                "",
                "## Progress Ledger",
                "",
                "- Done / current evidence: 已把这个版本固定成 Git 提交： `e8b1f82 Add request ledger token savings meter` 这次做完了 Request Ledger + Token Savings Meter 的第一版。",
                "- Next action cue: Infer from current workspace state.",
            ]
        )

        prompt = enhancer_handoff._build_takeover_prompt(Path(r"D:\AIHub\.ai-strategist\handoffs\handoff.md"), handoff_content)

        self.assertTrue(prompt.startswith("接手任务：Request Ledger + Token Savings Meter"))
        self.assertIn("Objective: Request Ledger + Token Savings Meter", prompt)
        self.assertNotIn(f"Objective: {thread_id}", prompt)
        self.assertIn("Next action cue: Continue Request Ledger + Token Savings Meter.", prompt)
        self.assertNotIn("Next action cue: Infer from current workspace state.", prompt)
        self.assertIn("wait for the user's approval before executing it", prompt)
        self.assertIn(
            "Communicate with the user in Chinese, but you may keep task work artifacts in English when appropriate.",
            prompt,
        )
        self.assertIn("Current evidence:", prompt)
        self.assertLessEqual(len(prompt), 1800)


if __name__ == "__main__":
    unittest.main()
