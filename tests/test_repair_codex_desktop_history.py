import argparse
import contextlib
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

import repair_codex_desktop_history as history_repair


class RepairCodexDesktopHistoryTests(unittest.TestCase):
    def test_attribution_keeps_same_provider_threads_in_separate_workspaces(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace_a = root / "workspace-a"
            workspace_b = root / "workspace-b"
            workspace_a.mkdir()
            workspace_b.mkdir()
            (workspace_a / "file.txt").write_text("a", encoding="utf-8")
            (workspace_b / "file.txt").write_text("b", encoding="utf-8")
            rollout_a = root / "a.jsonl"
            rollout_b = root / "b.jsonl"
            rollout_a.write_text("{}", encoding="utf-8")
            rollout_b.write_text("{}", encoding="utf-8")
            threads = [
                {
                    "id": "thread-a",
                    "cwd": str(workspace_a),
                    "rollout_path": str(rollout_a),
                    "model_provider": "openai",
                    "has_user_event": 1,
                    "first_user_message": "a",
                    "archived": 0,
                },
                {
                    "id": "thread-b",
                    "cwd": str(workspace_b),
                    "rollout_path": str(rollout_b),
                    "model_provider": "openai",
                    "has_user_event": 1,
                    "first_user_message": "b",
                    "archived": 0,
                },
            ]

            attributions = history_repair.thread_attributions(threads, argparse.Namespace(
                include_archived=False,
                allow_missing_cwd=False,
                allow_empty_cwd=False,
                allow_missing_session=False,
            ))

        self.assertEqual(
            {item["id"]: item["workspace_root"] for item in attributions},
            {"thread-a": str(workspace_a), "thread-b": str(workspace_b)},
        )
        self.assertTrue(all(item["target_location"] == "workspace" for item in attributions))
        self.assertTrue(all(item["reason"] == "cwd_exists_and_session_exists" for item in attributions))

    def test_attribution_keeps_different_provider_threads_in_same_workspace(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            (workspace / "file.txt").write_text("content", encoding="utf-8")
            rollout_a = root / "a.jsonl"
            rollout_b = root / "b.jsonl"
            rollout_a.write_text("{}", encoding="utf-8")
            rollout_b.write_text("{}", encoding="utf-8")
            threads = [
                {
                    "id": "official-thread",
                    "cwd": str(workspace),
                    "rollout_path": str(rollout_a),
                    "model_provider": "openai",
                    "has_user_event": 1,
                    "first_user_message": "official",
                    "archived": 0,
                },
                {
                    "id": "api-thread",
                    "cwd": str(workspace),
                    "rollout_path": str(rollout_b),
                    "model_provider": "cliproxy",
                    "has_user_event": 1,
                    "first_user_message": "api",
                    "archived": 0,
                },
            ]

            attributions = history_repair.thread_attributions(threads, argparse.Namespace(
                include_archived=False,
                allow_missing_cwd=False,
                allow_empty_cwd=False,
                allow_missing_session=False,
            ))

        self.assertEqual({item["workspace_root"] for item in attributions}, {str(workspace)})
        self.assertEqual({item["provider"] for item in attributions}, {"openai", "cliproxy"})
        self.assertTrue(all(item["target_location"] == "workspace" for item in attributions))

    def test_repair_state_switches_active_workspace_to_latest_restored_thread(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            old_workspace = root / "old-active"
            latest_workspace = root / "latest"
            old_workspace.mkdir()
            latest_workspace.mkdir()
            state_path = root / ".codex-global-state.json"
            state_path.write_text(
                json.dumps(
                    {
                        "active-workspace-roots": [str(old_workspace)],
                        "electron-saved-workspace-roots": [str(old_workspace)],
                        "project-order": [str(old_workspace)],
                    }
                ),
                encoding="utf-8",
            )

            result = history_repair.repair_state(
                state_path,
                [
                    {"id": "latest-thread", "cwd": str(latest_workspace)},
                    {"id": "old-thread", "cwd": str(old_workspace)},
                ],
                None,
                "none",
            )

            state = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(state["active-workspace-roots"], [str(latest_workspace)])
            self.assertEqual(result["active_workspace_roots"], [str(latest_workspace)])

    def test_move_thread_workspace_can_skip_global_root_mutation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            db_path = root / "state_5.sqlite"
            rollout_path = root / "rollout.jsonl"
            state_path = root / ".codex-global-state.json"
            rollout_path.write_text(
                '{"type":"session_meta","payload":{"id":"thread-a","cwd":"D:/old","title":"Thread A"}}\n',
                encoding="utf-8",
            )
            state_path.write_text(
                json.dumps(
                    {
                        "thread-workspace-root-hints": {"thread-a": "D:/old"},
                        "electron-saved-workspace-roots": ["D:/old"],
                        "project-order": ["D:/old"],
                        "active-workspace-roots": ["D:/old"],
                    }
                ),
                encoding="utf-8",
            )
            with contextlib.closing(history_repair.sqlite3.connect(db_path)) as con:
                con.execute(
                    """
                    create table threads (
                      id text primary key,
                      cwd text,
                      rollout_path text,
                      updated_at integer,
                      archived integer
                    )
                    """
                )
                con.execute(
                    "insert into threads (id, cwd, rollout_path, updated_at, archived) values (?, ?, ?, ?, ?)",
                    ("thread-a", "D:/old", str(rollout_path), 100, 0),
                )
                con.commit()

            result = history_repair.move_thread_workspace(root, "local:thread-a", "D:/new", update_state_roots=False)

            self.assertEqual(result["status"], "moved")
            self.assertEqual(result["session_id"], "thread-a")
            self.assertFalse(result["state_updated"])
            state = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(state["active-workspace-roots"], ["D:/old"])
            self.assertEqual(state["thread-workspace-root-hints"], {"thread-a": "D:/old"})

    def test_set_thread_projectless_state_updates_ids_and_clears_hints(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            db_path = root / "state_5.sqlite"
            state_path = root / ".codex-global-state.json"
            state_path.write_text(
                json.dumps(
                    {
                        "projectless-thread-ids": [],
                        "thread-workspace-root-hints": {"thread-a": "D:/old", "local:thread-a": "D:/old"},
                    }
                ),
                encoding="utf-8",
            )
            with contextlib.closing(history_repair.sqlite3.connect(db_path)) as con:
                con.execute("create table threads (id text primary key, updated_at integer)")
                con.execute("insert into threads (id, updated_at) values (?, ?)", ("thread-a", 123))
                con.commit()

            enabled = history_repair.set_thread_projectless_state(root, "local:thread-a", True)
            disabled = history_repair.set_thread_projectless_state(root, "thread-a", False)

            self.assertEqual(enabled["status"], "moved")
            self.assertEqual(enabled["target_kind"], "projectless")
            self.assertEqual(enabled["updated_at"], 123)
            self.assertEqual(disabled["status"], "moved")
            state = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(state["projectless-thread-ids"], [])
            self.assertEqual(state["thread-workspace-root-hints"], {})

    def test_thread_sort_keys_preserves_requested_order(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            db_path = root / "state_5.sqlite"
            with contextlib.closing(history_repair.sqlite3.connect(db_path)) as con:
                con.execute("create table threads (id text primary key, updated_at integer)")
                con.execute("insert into threads (id, updated_at) values (?, ?)", ("thread-a", 100))
                con.execute("insert into threads (id, updated_at) values (?, ?)", ("thread-b", 200))
                con.commit()

            result = history_repair.thread_sort_keys(root, ["local:thread-b", "thread-a"])

            self.assertEqual(result["status"], "ok")
            self.assertEqual(
                [item["session_id"] for item in result["sort_keys"]],
                ["thread-b", "thread-a"],
            )
            self.assertEqual(result["sort_keys"][0]["updated_at_ms"], 200000)

    def test_sync_selected_provider_updates_threads_and_rollout_session_meta(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            db_path = root / "state_5.sqlite"
            rollout_path = root / "rollout.jsonl"
            thread_id = "thread-1"
            with contextlib.closing(sqlite3.connect(db_path)) as con:
                con.execute("create table threads (id text primary key, rollout_path text not null, model_provider text)")
                con.execute(
                    "insert into threads (id, rollout_path, model_provider) values (?, ?, ?)",
                    (thread_id, str(rollout_path), "old-provider"),
                )
                con.commit()

            rollout_path.write_text(
                json.dumps(
                    {
                        "type": "session_meta",
                        "payload": {"id": thread_id, "model_provider": "old-provider", "cwd": str(root)},
                    },
                    ensure_ascii=False,
                )
                + "\n"
                + json.dumps({"type": "event_msg", "message": "keep"}, ensure_ascii=False)
                + "\n",
                encoding="utf-8",
            )

            result = history_repair.sync_selected_provider(
                db_path,
                [{"id": thread_id, "rollout_path": str(rollout_path)}],
                "codexzh",
            )

            self.assertEqual(result["provider_synced"], 1)
            self.assertEqual(result["provider_rollouts_synced"], 1)
            self.assertEqual(result["provider_rollout_errors"], [])
            with contextlib.closing(sqlite3.connect(db_path)) as con:
                provider = con.execute("select model_provider from threads where id = ?", (thread_id,)).fetchone()[0]
            self.assertEqual(provider, "codexzh")
            first_line = json.loads(rollout_path.read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual(first_line["payload"]["model_provider"], "codexzh")


if __name__ == "__main__":
    unittest.main()
