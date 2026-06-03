import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import enhancer_runtime


class EnhancerRuntimeTests(unittest.TestCase):
    def test_wait_before_attach_returns_when_codex_target_is_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            log_file = Path(tmp) / "runtime.log"

            with mock.patch.object(
                enhancer_runtime,
                "enhancer_attach_delay_seconds",
                return_value=5.0,
            ), mock.patch.object(
                enhancer_runtime,
                "codex_page_targets",
                return_value=[{"type": "page", "webSocketDebuggerUrl": "ws://127.0.0.1"}],
            ) as targets, mock.patch.object(
                enhancer_runtime.time,
                "sleep",
                side_effect=AssertionError("ready target should avoid fixed attach delay"),
            ):
                enhancer_runtime.wait_before_attach(str(log_file), 49152)

            targets.assert_called_once_with(49152)
            self.assertIn("Codex target ready", log_file.read_text(encoding="utf-8"))

    def test_wait_before_attach_preserves_fixed_delay_without_debug_port(self):
        with mock.patch.object(
            enhancer_runtime,
            "enhancer_attach_delay_seconds",
            return_value=1.0,
        ), mock.patch.object(
            enhancer_runtime.time,
            "sleep",
        ) as sleep:
            enhancer_runtime.wait_before_attach(None)

        sleep.assert_called_once_with(1.0)

    def test_remote_debugging_port_from_command_line(self):
        self.assertEqual(
            enhancer_runtime.remote_debugging_port_from_command_line(
                'Codex.exe --remote-debugging-port=63312 --remote-allow-origins=http://127.0.0.1:63312'
            ),
            63312,
        )
        self.assertEqual(
            enhancer_runtime.remote_debugging_port_from_command_line(
                'Codex.exe --remote-debugging-port 9229'
            ),
            9229,
        )
        self.assertIsNone(enhancer_runtime.remote_debugging_port_from_command_line("Codex.exe"))
        self.assertIsNone(enhancer_runtime.remote_debugging_port_from_command_line("--remote-debugging-port=70000"))

    def test_existing_session_launch_does_not_override_provider(self):
        with tempfile.TemporaryDirectory() as tmp:
            codex_home = Path(tmp) / ".codex"
            codex_home.mkdir()
            status_file = Path(tmp) / "runtime-status.json"
            log_file = Path(tmp) / "runtime.log"

            with mock.patch.object(
                enhancer_runtime,
                "configure_provider_for_launch",
                side_effect=AssertionError("existing-session launch must not override provider"),
            ), mock.patch.object(
                enhancer_runtime,
                "launch_codex_desktop_with_retry",
                return_value={"ok": True, "method": "product_resolved_exe", "debug_port": 49152},
            ), mock.patch.object(
                enhancer_runtime,
                "existing_codex_debug_port",
                return_value=None,
            ), mock.patch.object(
                enhancer_runtime,
                "wait_before_attach",
            ), mock.patch.object(
                enhancer_runtime,
                "attach_to_codex",
                return_value=([], set()),
            ), mock.patch.object(
                enhancer_runtime.threading,
                "Thread",
            ) as thread_cls, mock.patch.object(
                enhancer_runtime,
                "codex_running_processes",
                return_value=[],
            ), mock.patch.object(
                enhancer_runtime.time,
                "sleep",
            ), mock.patch.object(
                sys,
                "argv",
                [
                    "enhancer_runtime.py",
                    "--codex-home",
                    str(codex_home),
                    "--status-file",
                    str(status_file),
                    "--log-file",
                    str(log_file),
                    "--launch-mode",
                    "existing-session",
                ],
            ):
                exit_code = enhancer_runtime.main()

            status = json.loads(status_file.read_text(encoding="utf-8"))
            self.assertEqual(exit_code, 0, status)
            self.assertTrue(status["ok"])
            self.assertIn("existing-session launch keeps current Codex provider", log_file.read_text(encoding="utf-8"))
            self.assertEqual(thread_cls.call_count, 1)
            self.assertIn("runtime takeover watcher disabled", log_file.read_text(encoding="utf-8"))


    def test_runtime_reuses_existing_cdp_without_desktop_activation(self):
        with tempfile.TemporaryDirectory() as tmp:
            codex_home = Path(tmp) / ".codex"
            codex_home.mkdir()
            status_file = Path(tmp) / "runtime-status.json"
            log_file = Path(tmp) / "runtime.log"

            with mock.patch.object(
                enhancer_runtime,
                "desktop_codex_running_processes",
                return_value=[
                    {
                        "pid": 1234,
                        "command_line": "Codex.exe --remote-debugging-port=63312 --remote-allow-origins=http://127.0.0.1:63312",
                    }
                ],
            ), mock.patch.object(
                enhancer_runtime,
                "cdp_available",
                return_value=True,
            ), mock.patch.object(
                enhancer_runtime,
                "launch_codex_desktop_with_retry",
                side_effect=AssertionError("existing CDP must not relaunch or foreground Codex"),
            ), mock.patch.object(
                enhancer_runtime,
                "wait_before_attach",
            ), mock.patch.object(
                enhancer_runtime,
                "attach_to_codex",
                return_value=([], set()),
            ) as attach, mock.patch.object(
                enhancer_runtime.threading,
                "Thread",
            ), mock.patch.object(
                enhancer_runtime,
                "codex_running_processes",
                return_value=[],
            ), mock.patch.object(
                enhancer_runtime.time,
                "sleep",
            ), mock.patch.object(
                sys,
                "argv",
                [
                    "enhancer_runtime.py",
                    "--codex-home",
                    str(codex_home),
                    "--status-file",
                    str(status_file),
                    "--log-file",
                    str(log_file),
                    "--launch-mode",
                    "existing-session",
                ],
            ):
                exit_code = enhancer_runtime.main()

            status = json.loads(status_file.read_text(encoding="utf-8"))
            self.assertEqual(exit_code, 0, status)
            self.assertEqual(status["launch"]["method"], "existing_cdp")
            self.assertEqual(status["debug_port"], 63312)
            attach.assert_called_once_with(codex_home, 63312)
            self.assertIn("skipping desktop activation", log_file.read_text(encoding="utf-8"))

    def test_runtime_takeover_watcher_requires_explicit_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            codex_home = Path(tmp) / ".codex"
            codex_home.mkdir()
            status_file = Path(tmp) / "runtime-status.json"
            log_file = Path(tmp) / "runtime.log"

            with mock.patch.object(
                enhancer_runtime,
                "launch_codex_desktop_with_retry",
                return_value={"ok": True, "method": "product_resolved_exe", "debug_port": 49152},
            ), mock.patch.object(
                enhancer_runtime,
                "existing_codex_debug_port",
                return_value=None,
            ), mock.patch.object(
                enhancer_runtime,
                "wait_before_attach",
            ), mock.patch.object(
                enhancer_runtime,
                "attach_to_codex",
                return_value=([], set()),
            ), mock.patch.object(
                enhancer_runtime.threading,
                "Thread",
            ) as thread_cls, mock.patch.object(
                enhancer_runtime,
                "codex_running_processes",
                return_value=[],
            ), mock.patch.object(
                enhancer_runtime.time,
                "sleep",
            ), mock.patch.object(
                sys,
                "argv",
                [
                    "enhancer_runtime.py",
                    "--codex-home",
                    str(codex_home),
                    "--status-file",
                    str(status_file),
                    "--log-file",
                    str(log_file),
                    "--launch-mode",
                    "existing-session",
                    "--allow-runtime-takeover",
                ],
            ):
                exit_code = enhancer_runtime.main()

            status = json.loads(status_file.read_text(encoding="utf-8"))
            self.assertEqual(exit_code, 0, status)
            self.assertTrue(status["ok"])
            self.assertEqual(thread_cls.call_count, 2)
            self.assertNotIn("runtime takeover watcher disabled", log_file.read_text(encoding="utf-8"))

    def test_takeover_and_attach_relaunches_without_killing_codex(self):
        with tempfile.TemporaryDirectory() as tmp:
            codex_home = Path(tmp) / ".codex"
            codex_home.mkdir()
            log_file = Path(tmp) / "runtime.log"
            debug_port_ref = {"value": 49152}
            sockets_ref = {"value": []}
            seen_ref = {"value": set()}

            with mock.patch.object(
                enhancer_runtime,
                "launch_codex_desktop_with_retry",
                return_value={"ok": True, "debug_port": 49152},
            ) as launch, mock.patch.object(
                enhancer_runtime,
                "wait_before_attach",
            ), mock.patch.object(
                enhancer_runtime,
                "attach_to_codex",
                return_value=([], set()),
            ):
                ok = enhancer_runtime.takeover_and_attach(
                    codex_home,
                    debug_port_ref,
                    sockets_ref,
                    seen_ref,
                    enhancer_runtime.threading.Lock(),
                    str(log_file),
                )

            self.assertTrue(ok)
            launch.assert_called_once_with(
                ["--remote-debugging-port=49152", "--remote-allow-origins=http://127.0.0.1:49152"],
                attempts=3,
                allow_takeover=True,
            )
            self.assertIn("watcher relaunch requested", log_file.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
