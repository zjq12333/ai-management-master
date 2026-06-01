import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import enhancer_runtime


class EnhancerRuntimeTests(unittest.TestCase):
    def test_existing_session_launch_does_not_override_provider(self):
        with tempfile.TemporaryDirectory() as tmp:
            codex_home = Path(tmp) / ".codex"
            codex_home.mkdir()
            status_file = Path(tmp) / "runtime-status.json"
            log_file = Path(tmp) / "runtime.log"

            with mock.patch.object(
                enhancer_runtime,
                "ensure_must_install_local_plugins",
                return_value={"enabled": False, "changed": False, "plugins": [], "available_plugins": [], "errors": []},
            ), mock.patch.object(
                enhancer_runtime,
                "configure_provider_for_launch",
                side_effect=AssertionError("existing-session launch must not override provider"),
            ), mock.patch.object(
                enhancer_runtime,
                "launch_codex_desktop_with_retry",
                return_value={"ok": True, "method": "product_resolved_exe", "debug_port": 49152},
            ), mock.patch.object(
                enhancer_runtime,
                "wait_before_attach",
            ), mock.patch.object(
                enhancer_runtime,
                "attach_to_codex",
                return_value=([], set()),
            ), mock.patch.object(
                enhancer_runtime.threading.Thread,
                "start",
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
            self.assertTrue(status["ok"])
            self.assertIn("existing-session launch keeps current Codex provider", log_file.read_text(encoding="utf-8"))

    def test_runtime_enables_must_install_plugins_before_launch(self):
        with tempfile.TemporaryDirectory() as tmp:
            codex_home = Path(tmp) / ".codex"
            codex_home.mkdir()
            status_file = Path(tmp) / "runtime-status.json"
            log_file = Path(tmp) / "runtime.log"
            plugin_payload = {
                "enabled": True,
                "changed": True,
                "plugins": ["browser@openai-bundled"],
                "available_plugins": ["browser@openai-bundled"],
                "errors": [],
            }
            with mock.patch.object(
                enhancer_runtime,
                "ensure_must_install_local_plugins",
                return_value=plugin_payload,
            ) as ensure_plugins, mock.patch.object(
                enhancer_runtime,
                "launch_codex_desktop_with_retry",
                return_value={"ok": True, "method": "product_resolved_exe", "debug_port": 49152},
            ), mock.patch.object(
                enhancer_runtime,
                "wait_before_attach",
            ), mock.patch.object(
                enhancer_runtime,
                "attach_to_codex",
                return_value=([], set()),
            ), mock.patch.object(
                enhancer_runtime.threading.Thread,
                "start",
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
                    "hybrid",
                ],
            ):
                exit_code = enhancer_runtime.main()

            status = json.loads(status_file.read_text(encoding="utf-8"))
            ensure_plugins.assert_called_once_with(codex_home)
            self.assertEqual(exit_code, 0, status)
            self.assertTrue(status["ok"])
            self.assertEqual(status["must_install_plugins"], plugin_payload)
            self.assertIn("must-install plugins", log_file.read_text(encoding="utf-8"))

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
            launch.assert_called_once()
            self.assertIn("watcher relaunch requested", log_file.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
