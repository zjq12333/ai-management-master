import queue
import types
from pathlib import Path
from unittest import TestCase, mock

from CodexMaintenanceGUI import CodexMaintenanceGUI


class _Value:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value


class ThreadripperAutoSyncTests(TestCase):
    def test_worker_uses_fresh_status_before_auto_sync(self):
        gui = CodexMaintenanceGUI.__new__(CodexMaintenanceGUI)
        gui.output_queue = queue.Queue()
        gui.codex_home_var = _Value(r"C:\Users\test\.codex")
        gui.sync_provider = _Value(False)
        gui.last_threadripper_status = {}
        gui.tool_dir = Path.cwd()
        gui.threadripper_command = lambda: "codex-threadripper"
        gui.subprocess_window_options = lambda: {}
        gui.parse_threadripper_status = CodexMaintenanceGUI.parse_threadripper_status.__get__(gui)
        gui.try_update_summary = lambda text: None

        executed = []

        def fake_run(command, **kwargs):
            executed.append(command)
            if command[-1] == "status":
                return types.SimpleNamespace(
                    returncode=0,
                    stdout="Target provider: cliproxy\nRows needing reconcile: 113\n",
                    stderr="",
                )
            if command[-1] == "sync":
                return types.SimpleNamespace(returncode=0, stdout="synced\n", stderr="")
            raise AssertionError(f"unexpected command: {command}")

        with mock.patch("CodexMaintenanceGUI.subprocess.run", side_effect=fake_run):
            gui.command_worker(
                [["__THREADRIPPER_STATUS__"], ["__AUTO_THREADRIPPER_SYNC__"]],
                "test",
                notify=False,
            )

        self.assertIn(
            ["codex-threadripper", "--codex-home", r"C:\Users\test\.codex", "sync"],
            executed,
        )
