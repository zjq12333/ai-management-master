import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

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
            self.assertIn("## Progress Ledger", content)
            self.assertIn("## Verification", content)
            self.assertIn("## Watchouts", content)
            self.assertIn("先检查 handoff 逻辑", content)
            self.assertIn("我会先看当前状态", content)
            self.assertIn(str(handoff_path), result["prompt"])

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


if __name__ == "__main__":
    unittest.main()
