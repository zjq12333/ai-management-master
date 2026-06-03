import io
import tempfile
import threading
import json
import unittest
import re
from pathlib import Path
from unittest import mock
import os

import codex_desktop_launcher
import prelaunch_bridge
import prelaunch_manager


class PrelaunchBridgeTests(unittest.TestCase):
    def setUp(self):
        self.reports_dir = tempfile.TemporaryDirectory()
        self.reports_guard = mock.patch.dict(
            "os.environ",
            {"AI_STRATEGIST_REPORTS_DIR": self.reports_dir.name},
            clear=False,
        )
        self.reports_guard.start()
        self.running_guard = mock.patch.object(prelaunch_bridge, "ensure_codex_not_running")
        self.running_guard.start()
        self.takeover_guard = mock.patch.object(
            prelaunch_bridge,
            "prepare_codex_takeover",
            return_value={"ok": True, "skipped": True, "reason": "no_running_codex", "killed": [], "remaining": [], "errors": []},
        )
        self.takeover_guard.start()

    def tearDown(self):
        self.running_guard.stop()
        self.takeover_guard.stop()
        self.reports_guard.stop()
        self.reports_dir.cleanup()

    def test_runtime_status_includes_desktop_launch_diagnostics(self):
        with mock.patch.object(
            prelaunch_bridge,
            "codex_running_processes",
            return_value=[],
        ), mock.patch.object(
            prelaunch_manager,
            "desktop_codex_running_processes",
            return_value=[],
        ), mock.patch.object(
            prelaunch_manager,
            "resolved_codex_desktop_exe",
            return_value=r"C:\Program Files\Codex\Codex.exe",
        ), mock.patch.object(
            prelaunch_manager,
            "find_codex_desktop_appid",
            return_value="OpenAI.Codex_abc!App",
        ), mock.patch.dict(
            "os.environ",
            {"AI_STRATEGIST_CODEX_DESKTOP_SOURCE": "installedLocal"},
            clear=False,
        ):
            payload = prelaunch_bridge.handle_runtime_status()

        self.assertTrue(payload["ok"])
        self.assertFalse(payload["codex_running"])
        self.assertEqual(payload["desktop_launch"]["method"], "product_resolved_exe")
        self.assertEqual(payload["desktop_launch"]["product_resolved_source"], "installedLocal")
        self.assertEqual(payload["desktop_launch"]["appid"], "OpenAI.Codex_abc!App")

    def test_normalize_codex_home_expands_windows_environment_variable(self):
        with mock.patch.dict("os.environ", {"AI_STRATEGIST_TEST_HOME": "C:/Users/test"}, clear=False):
            self.assertEqual(
                prelaunch_bridge.normalize_codex_home("%AI_STRATEGIST_TEST_HOME%/.codex"),
                Path("C:/Users/test/.codex"),
            )

    def test_threadripper_command_prefers_product_resolved_environment_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            helper = Path(temp_dir) / "codex-threadripper.exe"
            helper.write_text("", encoding="utf-8")

            with mock.patch.dict(
                "os.environ",
                {"AI_STRATEGIST_THREADRIPPER": str(helper)},
                clear=False,
            ), mock.patch("prelaunch_manager.shutil.which", return_value="PATH_SHOULD_NOT_WIN"):
                self.assertEqual(prelaunch_manager.threadripper_command(), str(helper))

    def test_threadripper_command_ignores_missing_environment_path_without_path_fallback(self):
        with mock.patch.dict(
            "os.environ",
            {"AI_STRATEGIST_THREADRIPPER": "C:/missing/codex-threadripper.exe"},
            clear=False,
        ), mock.patch("prelaunch_manager.shutil.which", return_value="codex-threadripper"):
            self.assertIsNone(prelaunch_manager.threadripper_command())

    def test_windows_system_tool_prefers_system32_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            tool = Path(temp_dir) / "System32" / "reg.exe"
            tool.parent.mkdir(parents=True)
            tool.write_text("", encoding="utf-8")

            with mock.patch.dict("os.environ", {"SystemRoot": temp_dir}, clear=False):
                self.assertEqual(prelaunch_manager.windows_system_tool("reg.exe"), str(tool))

    def test_windows_system_tool_falls_back_to_name_when_missing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with mock.patch.dict("os.environ", {"SystemRoot": temp_dir}, clear=False):
                self.assertEqual(prelaunch_manager.windows_system_tool("reg.exe"), "reg.exe")

    def test_enhancer_enabled_returns_true_when_one_click_handoff_is_enabled(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            codex_home = Path(temp_dir)
            settings_dir = codex_home / "codexmate"
            settings_dir.mkdir(parents=True, exist_ok=True)
            (settings_dir / "settings.json").write_text(
                json.dumps({"enhancer": {"oneClickHandoffEnabled": True}}, ensure_ascii=False),
                encoding="utf-8",
            )

            self.assertTrue(prelaunch_manager.one_click_handoff_enabled(codex_home))
            self.assertTrue(prelaunch_manager.enhancer_enabled(codex_home))

    def test_prepare_report_dir_uses_product_managed_reports_root(self):
        with tempfile.TemporaryDirectory() as temp_dir, mock.patch.dict(
            "os.environ",
            {"AI_STRATEGIST_REPORTS_DIR": temp_dir},
            clear=False,
        ):
            report_dir = prelaunch_bridge.prepare_report_dir("launch", "official")

        self.assertTrue(str(report_dir).startswith(temp_dir))
        self.assertTrue(report_dir.name.endswith("-launch-official"))

    def test_launch_codex_desktop_prefers_appid_activation_over_product_resolved_exe(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            exe = Path(temp_dir) / "Codex.exe"
            exe.write_text("", encoding="utf-8")

            with mock.patch.dict(
                "os.environ",
                {
                    "AI_STRATEGIST_CODEX_DESKTOP": str(exe),
                    "AI_STRATEGIST_CODEX_DESKTOP_SOURCE": "managedLocal",
                },
                clear=False,
            ), mock.patch.object(prelaunch_manager.subprocess, "Popen") as popen, mock.patch.object(
                prelaunch_manager,
                "focus_codex_window",
                return_value={"ok": True},
            ), mock.patch.object(
                prelaunch_manager,
                "desktop_codex_running_processes",
                return_value=[],
            ), mock.patch.object(
                prelaunch_manager,
                "codex_running_processes",
                return_value=[],
            ), mock.patch.object(
                prelaunch_manager,
                "find_codex_desktop_appid",
                return_value="OpenAI.Codex_abc!App",
            ), mock.patch.object(
                prelaunch_manager,
                "prepare_codex_takeover",
                return_value={"ok": True, "skipped": True},
            ), mock.patch.object(
                prelaunch_manager,
                "wait_for_new_codex_pid",
                return_value=1001,
            ), mock.patch.object(
                prelaunch_manager,
                "wait_for_visible_codex_window",
                return_value=1001,
            ):
                popen.return_value.pid = 1001
                payload = prelaunch_manager.launch_codex_desktop()

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["method"], "appid")
        self.assertEqual(payload["appid"], "OpenAI.Codex_abc!App")
        self.assertEqual(payload["visible_pid"], 1001)
        popen.assert_called_once()

    def test_launch_codex_desktop_treats_appid_pid_as_started_even_when_focus_fails(self):
        with mock.patch.object(prelaunch_manager.subprocess, "Popen") as popen, mock.patch.object(
            prelaunch_manager,
            "focus_codex_window",
            return_value={"ok": False, "error": "focus denied"},
        ), mock.patch.object(
            prelaunch_manager,
            "desktop_codex_running_processes",
            return_value=[],
        ), mock.patch.object(
            prelaunch_manager,
            "codex_running_processes",
            return_value=[],
        ), mock.patch.object(
            prelaunch_manager,
            "find_codex_desktop_appid",
            return_value="OpenAI.Codex_abc!App",
        ), mock.patch.object(
            prelaunch_manager,
            "prepare_codex_takeover",
            return_value={"ok": True, "skipped": True},
        ), mock.patch.object(
            prelaunch_manager,
            "wait_for_new_codex_pid",
            return_value=1001,
        ), mock.patch.object(
            prelaunch_manager,
            "wait_for_visible_codex_window",
            return_value=None,
        ):
            popen.return_value.pid = 1001
            payload = prelaunch_manager.launch_codex_desktop()

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["method"], "appid")
        self.assertEqual(payload["pid"], 1001)
        self.assertIsNone(payload["error"])

    def test_launch_codex_desktop_focuses_existing_visible_window(self):
        running = [{"pid": 4242, "image": "Codex.exe", "exe": "C:/Program Files/WindowsApps/OpenAI.Codex/app/Codex.exe"}]
        popen_calls = []

        def fake_popen(command, *args, **kwargs):
            popen_calls.append(command)
            if isinstance(command, list) and command and command[0] == "explorer.exe":
                raise AssertionError("explorer.exe must not be called when a visible Codex window already exists")
            process = mock.Mock()
            process.communicate.return_value = ("", "")
            process.returncode = 0
            return process

        with mock.patch("prelaunch_manager.desktop_codex_running_processes", return_value=running), mock.patch(
            "prelaunch_manager.prepare_codex_takeover"
        ) as takeover, mock.patch("prelaunch_manager.focus_codex_window", return_value={"ok": True}) as focus, mock.patch(
            "prelaunch_manager.find_codex_desktop_appid", return_value="OpenAI.Codex_abc!App"
        ), mock.patch("prelaunch_manager.visible_codex_window_pids", return_value=[4242]), mock.patch.object(
            prelaunch_manager.subprocess,
            "Popen",
            side_effect=fake_popen,
        ):
            payload = prelaunch_manager.launch_codex_desktop()

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["method"], "already_running_visible_window")
        self.assertEqual(payload["processes"], running)
        self.assertEqual(payload["foreground"]["ok"], True)
        takeover.assert_not_called()
        focus.assert_called_once_with(4242)
        self.assertNotIn(["explorer.exe", "shell:AppsFolder\\OpenAI.Codex_abc!App"], popen_calls)

    def test_launch_codex_desktop_reactivates_existing_process_without_visible_window(self):
        running = [{"pid": 4242, "image": "Codex.exe", "exe": "C:/Program Files/WindowsApps/OpenAI.Codex/app/Codex.exe"}]
        with mock.patch("prelaunch_manager.desktop_codex_running_processes", return_value=running), mock.patch(
            "prelaunch_manager.prepare_codex_takeover"
        ) as takeover, mock.patch("prelaunch_manager.focus_codex_window", return_value={"ok": True}) as focus, mock.patch(
            "prelaunch_manager.find_codex_desktop_appid", return_value="OpenAI.Codex_abc!App"
        ), mock.patch("prelaunch_manager.visible_codex_window_pids", return_value=[]), mock.patch(
            "prelaunch_manager.terminate_desktop_codex_processes",
            side_effect=AssertionError("launch must not terminate Codex Desktop"),
        ) as terminate, mock.patch("prelaunch_manager.codex_running_processes", return_value=[]), mock.patch(
            "prelaunch_manager.wait_for_new_codex_pid", return_value=5151
        ), mock.patch(
            "prelaunch_manager.wait_for_visible_codex_window", return_value=5151
        ), mock.patch.object(prelaunch_manager.subprocess, "Popen") as popen:
            payload = prelaunch_manager.launch_codex_desktop()

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["method"], "appid_reactivate_stale_background")
        self.assertEqual(payload["processes"], running)
        takeover.assert_not_called()
        terminate.assert_not_called()
        focus.assert_called_once_with(5151)
        popen.assert_called_once()
        self.assertEqual(popen.call_args.args[0], ["explorer.exe", "shell:AppsFolder\\OpenAI.Codex_abc!App"])

    def test_resolved_codex_desktop_exe_prefers_explicit_environment_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            exe = Path(temp_dir) / "Codex.exe"
            exe.write_text("", encoding="utf-8")

            with mock.patch.dict("os.environ", {"AI_STRATEGIST_CODEX_DESKTOP": str(exe)}, clear=False):
                resolved = prelaunch_manager.resolved_codex_desktop_exe()

        self.assertEqual(resolved, str(exe))

    def test_resolved_codex_desktop_exe_accepts_installed_windowsapps_codex(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            exe = (
                Path(temp_dir)
                / "Microsoft"
                / "WindowsApps"
                / "OpenAI.Codex_26.519.5221.0_x64__2p2nqsd0c76g0"
                / "app"
                / "Codex.exe"
            )
            exe.parent.mkdir(parents=True)
            exe.write_text("", encoding="utf-8")

            with mock.patch.dict("os.environ", {"AI_STRATEGIST_CODEX_DESKTOP": str(exe)}, clear=False):
                resolved = prelaunch_manager.resolved_codex_desktop_exe()

        self.assertEqual(resolved, str(exe))

    def test_codex_desktop_env_path_candidates_include_common_localappdata_install(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with mock.patch.dict("os.environ", {"LOCALAPPDATA": temp_dir}, clear=False):
                candidates = prelaunch_manager.codex_desktop_env_path_candidates()

        self.assertIn(Path(temp_dir) / "Programs" / "Codex" / "Codex.exe", candidates)

    def test_find_codex_desktop_exe_falls_back_to_registry_then_non_windowsapps_path(self):
        with mock.patch.object(
            prelaunch_manager,
            "query_codex_desktop_from_registry",
            return_value="C:/registry/Codex.exe",
        ), mock.patch("prelaunch_manager.Path.exists", return_value=False), mock.patch("prelaunch_manager.shutil.which", return_value="C:/Users/test/AppData/Local/Microsoft/WindowsApps/Codex.exe"):
            resolved = prelaunch_manager.find_codex_desktop_exe()

        self.assertEqual(resolved, "C:/registry/Codex.exe")

    def test_find_codex_desktop_exe_accepts_non_windowsapps_path_fallback(self):
        with mock.patch.object(
            prelaunch_manager,
            "query_codex_desktop_from_registry",
            return_value=None,
        ), mock.patch("prelaunch_manager.Path.exists", return_value=False), mock.patch("prelaunch_manager.shutil.which", return_value="C:/Tools/Codex.exe"):
            resolved = prelaunch_manager.find_codex_desktop_exe()

        self.assertEqual(resolved, "C:/Tools/Codex.exe")

    def test_launch_codex_desktop_does_not_apply_hidden_console_flags_to_gui_app(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            exe = Path(temp_dir) / "Codex.exe"
            exe.write_text("", encoding="utf-8")

            with mock.patch.dict(
                "os.environ",
                {
                    "AI_STRATEGIST_CODEX_DESKTOP": str(exe),
                    "AI_STRATEGIST_CODEX_DESKTOP_SOURCE": "managedLocal",
                },
                clear=False,
            ), mock.patch.object(prelaunch_manager.subprocess, "Popen") as popen, mock.patch.object(
                prelaunch_manager,
                "focus_codex_window",
                return_value={"ok": True},
            ), mock.patch.object(
                prelaunch_manager,
                "prepare_codex_takeover",
                return_value={"ok": True, "skipped": True},
            ):
                popen.return_value.pid = 1002
                prelaunch_manager.launch_codex_desktop()

        _, kwargs = popen.call_args
        self.assertIn("env", kwargs)
        self.assertNotIn("creationflags", kwargs)
        self.assertNotIn("startupinfo", kwargs)

    def test_launch_codex_desktop_attempts_to_focus_window_after_spawn(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            exe = Path(temp_dir) / "Codex.exe"
            exe.write_text("", encoding="utf-8")

            with mock.patch.dict(
                "os.environ",
                {
                    "AI_STRATEGIST_CODEX_DESKTOP": str(exe),
                    "AI_STRATEGIST_CODEX_DESKTOP_SOURCE": "managedLocal",
                },
                clear=False,
            ), mock.patch.object(prelaunch_manager.subprocess, "Popen") as popen, mock.patch.object(
                prelaunch_manager,
                "focus_codex_window",
                return_value={"ok": True, "method": "wscript_appactivate", "pid": 2468},
            ) as focus, mock.patch.object(
                prelaunch_manager,
                "prepare_codex_takeover",
                return_value={"ok": True, "skipped": True},
            ):
                popen.return_value.pid = 2468
                payload = prelaunch_manager.launch_codex_desktop()

        focus.assert_called_once_with(2468)
        self.assertEqual(payload["foreground"], {"ok": True, "method": "wscript_appactivate", "pid": 2468})

    def test_launch_codex_desktop_with_args_does_not_apply_hidden_console_flags_to_gui_app(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            exe = Path(temp_dir) / "Codex.exe"
            exe.write_text("", encoding="utf-8")

            with mock.patch.dict(
                "os.environ",
                {
                    "AI_STRATEGIST_CODEX_DESKTOP": str(exe),
                    "AI_STRATEGIST_CODEX_DESKTOP_SOURCE": "managedLocal",
                },
                clear=False,
            ), mock.patch.object(prelaunch_manager.subprocess, "Popen") as popen, mock.patch.object(
                prelaunch_manager,
                "focus_codex_window",
                return_value={"ok": True},
            ), mock.patch.object(
                prelaunch_manager,
                "wait_for_cdp",
                return_value=True,
            ):
                popen.return_value.pid = 1003
                payload = prelaunch_manager.launch_codex_desktop_with_args(["--remote-debugging-port=9229"])

        args, kwargs = popen.call_args
        self.assertEqual(args[0][0], str(exe))
        self.assertRegex(args[0][1], r"^--remote-debugging-port=\d+$")
        launched_port = int(args[0][1].split("=", 1)[1])
        self.assertEqual(payload["debug_port"], launched_port)
        self.assertEqual(payload["method"], "product_resolved_exe")
        self.assertIn("env", kwargs)
        self.assertNotIn("creationflags", kwargs)
        self.assertNotIn("startupinfo", kwargs)

    def test_launch_codex_desktop_with_args_uses_packaged_activation_for_windowsapps(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            package_dir = Path(temp_dir) / "OpenAI.Codex_26.519.5221.0_x64__2p2nqsd0c76g0" / "app"
            package_dir.mkdir(parents=True, exist_ok=True)
            exe = package_dir / "Codex.exe"
            exe.write_text("", encoding="utf-8")

            with mock.patch.dict(
                "os.environ",
                {
                    "AI_STRATEGIST_CODEX_DESKTOP": str(exe),
                    "AI_STRATEGIST_CODEX_DESKTOP_SOURCE": "managedLocal",
                },
                clear=False,
            ), mock.patch.object(
                prelaunch_manager,
                "activate_packaged_app",
                return_value=2468,
            ) as activate, mock.patch.object(
                prelaunch_manager,
                "wait_for_cdp",
                return_value=True,
            ) as wait_for_cdp, mock.patch.object(
                prelaunch_manager,
                "focus_codex_window",
                return_value={"ok": True, "pid": 2468},
            ) as focus, mock.patch.object(
                prelaunch_manager.subprocess,
                "Popen",
            ) as popen:
                payload = prelaunch_manager.launch_codex_desktop_with_args(
                    ["--remote-debugging-port=9229", "--remote-allow-origins=http://127.0.0.1:9229"]
                )

        popen.assert_not_called()
        activate.assert_called_once()
        activation_args = activate.call_args.args[1]
        self.assertRegex(activation_args, r"--remote-debugging-port=\d+")
        launched_port = int(re.search(r"--remote-debugging-port=(\d+)", activation_args).group(1))
        wait_for_cdp.assert_called_once_with(launched_port)
        focus.assert_called_once_with(2468)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["method"], "product_resolved_packaged_activation")
        self.assertEqual(payload["debug_port"], launched_port)

    def test_launch_codex_desktop_with_args_temporarily_applies_proxy_env_for_packaged_activation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            package_dir = Path(temp_dir) / "OpenAI.Codex_26.519.5221.0_x64__2p2nqsd0c76g0" / "app"
            package_dir.mkdir(parents=True, exist_ok=True)
            exe = package_dir / "Codex.exe"
            exe.write_text("", encoding="utf-8")
            captured_proxy = {}

            def fake_activate(_appid, _arguments):
                captured_proxy["HTTP_PROXY"] = os.environ.get("HTTP_PROXY")
                captured_proxy["HTTPS_PROXY"] = os.environ.get("HTTPS_PROXY")
                captured_proxy["ALL_PROXY"] = os.environ.get("ALL_PROXY")
                return 2468

            with mock.patch.dict(
                os.environ,
                {
                    "AI_STRATEGIST_CODEX_DESKTOP": str(exe),
                    "AI_STRATEGIST_CODEX_DESKTOP_SOURCE": "managedLocal",
                },
                clear=False,
            ), mock.patch.object(
                prelaunch_manager,
                "activate_packaged_app",
                side_effect=fake_activate,
            ), mock.patch.object(
                prelaunch_manager,
                "wait_for_cdp",
                return_value=True,
            ), mock.patch.object(
                prelaunch_manager,
                "focus_codex_window",
                return_value={"ok": True, "pid": 2468},
            ), mock.patch.object(
                prelaunch_manager,
                "codex_process_environment",
                return_value={
                    "HTTP_PROXY": "http://127.0.0.1:7897",
                    "HTTPS_PROXY": "http://127.0.0.1:7897",
                    "ALL_PROXY": "http://127.0.0.1:7897",
                },
            ):
                prelaunch_manager.launch_codex_desktop_with_args(["--remote-debugging-port=9229"])

        self.assertEqual(captured_proxy["HTTP_PROXY"], "http://127.0.0.1:7897")
        self.assertEqual(captured_proxy["HTTPS_PROXY"], "http://127.0.0.1:7897")
        self.assertEqual(captured_proxy["ALL_PROXY"], "http://127.0.0.1:7897")
        self.assertIsNone(os.environ.get("HTTP_PROXY"))
        self.assertIsNone(os.environ.get("HTTPS_PROXY"))
        self.assertIsNone(os.environ.get("ALL_PROXY"))

    def test_launch_codex_desktop_with_args_switches_busy_debug_port(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            package_dir = Path(temp_dir) / "OpenAI.Codex_26.519.5221.0_x64__2p2nqsd0c76g0" / "app"
            package_dir.mkdir(parents=True, exist_ok=True)
            exe = package_dir / "Codex.exe"
            exe.write_text("", encoding="utf-8")

            with mock.patch.dict(
                "os.environ",
                {"AI_STRATEGIST_CODEX_DESKTOP": str(exe)},
                clear=False,
            ), mock.patch.object(
                prelaunch_manager,
                "select_windows_loopback_port",
                return_value=43001,
            ), mock.patch.object(
                prelaunch_manager,
                "activate_packaged_app",
                return_value=2468,
            ) as activate, mock.patch.object(
                prelaunch_manager,
                "wait_for_cdp",
                return_value=True,
            ), mock.patch.object(
                prelaunch_manager,
                "focus_codex_window",
                return_value={"ok": True},
            ):
                payload = prelaunch_manager.launch_codex_desktop_with_args(
                    ["--remote-debugging-port=9229", "--remote-allow-origins=http://127.0.0.1:9229"]
                )

        activation_args = activate.call_args.args[1]
        self.assertIn("--remote-debugging-port=43001", activation_args)
        self.assertIn("http://127.0.0.1:43001", activation_args)
        self.assertEqual(payload["debug_port"], 43001)

    def test_launch_codex_desktop_with_args_fails_when_cdp_never_comes_up(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            package_dir = Path(temp_dir) / "OpenAI.Codex_26.519.5221.0_x64__2p2nqsd0c76g0" / "app"
            package_dir.mkdir(parents=True, exist_ok=True)
            exe = package_dir / "Codex.exe"
            exe.write_text("", encoding="utf-8")

            with mock.patch.dict(
                "os.environ",
                {"AI_STRATEGIST_CODEX_DESKTOP": str(exe)},
                clear=False,
            ), mock.patch.object(
                prelaunch_manager,
                "activate_packaged_app",
                return_value=2468,
            ), mock.patch.object(
                prelaunch_manager,
                "wait_for_cdp",
                return_value=False,
            ), mock.patch.object(
                prelaunch_manager,
                "terminate_desktop_codex_processes",
                side_effect=AssertionError("launch must not terminate Codex Desktop"),
            ) as terminate:
                payload = prelaunch_manager.launch_codex_desktop_with_args(["--remote-debugging-port=9229"])

        terminate.assert_not_called()
        self.assertFalse(payload["ok"])
        self.assertIn("CDP did not come up", payload["error"])
        self.assertEqual(payload["cleanup"]["reason"], "preserve_existing_codex_desktop")

    def test_desktop_codex_running_processes_filters_out_non_desktop_cli_path(self):
        with mock.patch.object(
            prelaunch_manager,
            "codex_process_details",
            return_value=[
                {
                    "image": "Codex.exe",
                    "pid": 101,
                    "exe": "C:/Users/test/AppData/Local/Programs/Codex/Codex.exe",
                    "command_line": "\"C:/Users/test/AppData/Local/Programs/Codex/Codex.exe\"",
                },
                {
                    "image": "codex.exe",
                    "pid": 202,
                    "exe": "C:/Tools/codex.exe",
                    "command_line": "\"C:/Tools/codex.exe\" --help",
                },
            ],
        ), mock.patch.object(
            prelaunch_manager,
            "_known_desktop_codex_exe_paths",
            return_value={"c:\\users\\test\\appdata\\local\\programs\\codex\\codex.exe"},
        ):
            payload = prelaunch_manager.desktop_codex_running_processes()

        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["pid"], 101)

    def test_desktop_codex_running_processes_includes_windowsapps_resource_helper(self):
        with mock.patch.object(
            prelaunch_manager,
            "codex_process_details",
            return_value=[
                {
                    "image": "Codex.exe",
                    "pid": 101,
                    "exe": "C:/Program Files/WindowsApps/OpenAI.Codex_26.519.5221.0_x64__2p2nqsd0c76g0/app/Codex.exe",
                    "command_line": "\"C:/Program Files/WindowsApps/OpenAI.Codex_26.519.5221.0_x64__2p2nqsd0c76g0/app/Codex.exe\"",
                },
                {
                    "image": "codex.exe",
                    "pid": 202,
                    "exe": "C:/Program Files/WindowsApps/OpenAI.Codex_26.519.5221.0_x64__2p2nqsd0c76g0/app/resources/codex.exe",
                    "command_line": "\"C:/Program Files/WindowsApps/OpenAI.Codex_26.519.5221.0_x64__2p2nqsd0c76g0/app/resources/codex.exe\" app-server --analytics-default-enabled",
                },
            ],
        ), mock.patch.object(
            prelaunch_manager,
            "_known_desktop_codex_exe_paths",
            return_value={"c:\\program files\\windowsapps\\openai.codex_26.519.5221.0_x64__2p2nqsd0c76g0\\app\\codex.exe"},
        ):
            payload = prelaunch_manager.desktop_codex_running_processes()

        self.assertEqual([item["pid"] for item in payload], [101, 202])

    def test_launch_codex_desktop_with_retry_retries_after_cdp_failure(self):
        attempts: list[int] = []

        def fake_launch(args, debug_port):
            attempts.append(len(attempts) + 1)
            if len(attempts) == 1:
                return {
                    "ok": False,
                    "method": "product_resolved_packaged_activation",
                    "debug_port": debug_port,
                    "error": "Codex Desktop launched but CDP did not come up on port 9229.",
                }
            return {
                "ok": True,
                "method": "product_resolved_packaged_activation",
                "debug_port": debug_port,
                "pid": 2468,
            }

        with mock.patch.object(
            prelaunch_manager,
            "_launch_codex_desktop_with_args_once",
            side_effect=fake_launch,
        ) as launch_once, mock.patch.object(
            prelaunch_manager,
            "terminate_enhancer_runtime_processes",
            return_value={"ok": True, "killed": [], "remaining": [], "errors": []},
        ), mock.patch.object(
            prelaunch_manager,
            "cleanup_failed_enhanced_launch",
            return_value={"ok": True, "launcher": {"ok": True}, "desktop": {"ok": True}},
        ), mock.patch.object(
            prelaunch_manager,
            "prepare_codex_takeover",
            return_value={"ok": True, "skipped": False, "reason": "terminated_existing_codex", "killed": [], "remaining": [], "errors": []},
        ) as takeover:
            payload = prelaunch_manager.launch_codex_desktop_with_retry(
                ["--remote-debugging-port=9229"],
                attempts=3,
                allow_takeover=True,
            )

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["attempts"], 2)
        self.assertTrue(payload["recovered_after_retry"])
        self.assertEqual(len(payload["previous_attempts"]), 1)
        self.assertEqual(payload["previous_attempts"][0]["attempt"], 1)
        self.assertEqual(launch_once.call_count, 2)
        takeover.assert_called_once()

    def test_launch_codex_desktop_with_retry_requires_explicit_takeover(self):
        with mock.patch.object(
            prelaunch_manager,
            "_launch_codex_desktop_with_args_once",
            return_value={
                "ok": False,
                "method": "product_resolved_packaged_activation",
                "debug_port": 9229,
                "error": "Codex Desktop launched but CDP did not come up on port 9229.",
            },
        ) as launch_once, mock.patch.object(
            prelaunch_manager,
            "cleanup_failed_enhanced_launch",
            return_value={"ok": True, "launcher": {"ok": True}, "desktop": {"ok": True}},
        ), mock.patch.object(
            prelaunch_manager,
            "prepare_codex_takeover",
        ) as takeover:
            payload = prelaunch_manager.launch_codex_desktop_with_retry(
                ["--remote-debugging-port=9229"],
                attempts=3,
            )

        self.assertFalse(payload["ok"])
        self.assertEqual(payload["method"], "product_resolved_packaged_activation")
        self.assertEqual(payload["attempts"], 1)
        self.assertEqual(payload["retry_blocked"], "takeover_not_allowed")
        self.assertEqual(launch_once.call_count, 1)
        takeover.assert_not_called()

    def test_launch_codex_desktop_with_retry_stops_on_non_retryable_error(self):
        with mock.patch.object(
            prelaunch_manager,
            "_launch_codex_desktop_with_args_once",
            return_value={
                "ok": False,
                "method": "none",
                "error": "Unable to locate a direct Codex Desktop executable for enhancer launch.",
            },
        ) as launch_once, mock.patch.object(
            prelaunch_manager,
            "terminate_enhancer_runtime_processes",
            return_value={"ok": True, "killed": [], "remaining": [], "errors": []},
        ), mock.patch.object(
            prelaunch_manager,
            "cleanup_failed_enhanced_launch",
            return_value={"ok": True, "launcher": {"ok": True}, "desktop": {"ok": True}},
        ), mock.patch.object(
            prelaunch_manager,
            "prepare_codex_takeover",
        ) as takeover:
            payload = prelaunch_manager.launch_codex_desktop_with_retry(
                ["--remote-debugging-port=9229"],
                attempts=3,
            )

        self.assertFalse(payload["ok"])
        self.assertEqual(payload["attempts"], 1)
        self.assertEqual(payload["previous_attempts"], [])
        launch_once.assert_called_once()
        takeover.assert_not_called()

    def test_launch_codex_desktop_with_enhancer_waits_for_ready_status(self):
        class DummyProcess:
            pid = 9876

            def poll(self):
                return None

        def fake_popen(args, **kwargs):
            status_path = Path(args[args.index("--status-file") + 1])

            def writer():
                status_path.write_text(
                    json.dumps({"ok": True, "method": "enhancer_runtime", "debug_port": 43001}, ensure_ascii=False),
                    encoding="utf-8",
                )

            threading.Thread(target=writer, daemon=True).start()
            return DummyProcess()

        with mock.patch.object(prelaunch_manager.subprocess, "Popen", side_effect=fake_popen), mock.patch.object(
            prelaunch_manager,
            "cdp_available",
            return_value=True,
        ):
            payload = prelaunch_manager.launch_codex_desktop_with_enhancer(Path("C:/Users/test/.codex"), "official")

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["method"], "enhancer_runtime")
        self.assertEqual(payload["pid"], 9876)
        self.assertEqual(payload["debug_port"], 43001)

    def test_launch_codex_desktop_with_enhancer_prefers_resolved_python_runtime(self):
        class DummyProcess:
            pid = 1234

            def poll(self):
                return None

        seen = {}

        def fake_popen(args, **kwargs):
            seen["args"] = list(args)
            status_path = Path(args[args.index("--status-file") + 1])
            status_path.write_text(
                json.dumps({"ok": True, "method": "enhancer_runtime", "debug_port": 43001}, ensure_ascii=False),
                encoding="utf-8",
            )
            return DummyProcess()

        with mock.patch.object(
            prelaunch_manager,
            "resolved_python_runtime_executable",
            return_value="C:/Runtime/python/pythonw.exe",
        ), mock.patch.object(
            prelaunch_manager.subprocess,
            "Popen",
            side_effect=fake_popen,
        ), mock.patch.object(
            prelaunch_manager,
            "cdp_available",
            return_value=True,
        ):
            payload = prelaunch_manager.launch_codex_desktop_with_enhancer(Path("C:/Users/test/.codex"), "official")

        self.assertTrue(payload["ok"])
        self.assertTrue(seen["args"][0].lower().endswith("pythonw.exe"))

    def test_existing_session_enhancer_treats_cdp_not_ready_after_activation_as_partial_success(self):
        class DummyProcess:
            pid = 1234

            def poll(self):
                return None

        def fake_popen(args, **kwargs):
            status_path = Path(args[args.index("--status-file") + 1])
            status_path.write_text(
                json.dumps(
                    {
                        "ok": False,
                        "method": "windowsapps_packaged_activation",
                        "appid": "OpenAI.Codex_abc!App",
                        "pid": 4321,
                        "error": "Codex Desktop launched but CDP did not come up on port 9229.",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            return DummyProcess()

        with mock.patch.object(
            prelaunch_manager,
            "resolved_python_runtime_executable",
            return_value="C:/Runtime/python/pythonw.exe",
        ), mock.patch.object(
            prelaunch_manager.subprocess,
            "Popen",
            side_effect=fake_popen,
        ):
            payload = prelaunch_manager.launch_codex_desktop_with_enhancer(
                Path("C:/Users/test/.codex"),
                "existing-session",
            )

        self.assertTrue(payload["ok"])
        self.assertFalse(payload["enhancer_attached"])
        self.assertIsNone(payload["error"])
        self.assertIn("CDP did not come up", payload["warning"])

    def test_resolved_python_runtime_executable_falls_back_when_configured_runtime_lacks_modules(self):
        existing_paths = {
            "c:\\bad\\python.exe",
            "d:\\tools\\python312\\pythonw.exe",
        }
        with mock.patch.dict(
            "os.environ",
            {"AI_STRATEGIST_PYTHON_RUNTIME": "C:/Bad/python.exe"},
            clear=False,
        ), mock.patch.object(
            prelaunch_manager.Path,
            "exists",
            autospec=True,
            side_effect=lambda path_obj: str(path_obj).replace("/", "\\").lower() in existing_paths,
        ), mock.patch.object(
            prelaunch_manager,
            "python_runtime_supports_enhancer_modules",
            side_effect=lambda path: str(path).replace("/", "\\").lower() != "c:\\bad\\python.exe",
        ), mock.patch.object(
            prelaunch_manager.sys,
            "executable",
            "D:/Tools/Python312/python.exe",
        ):
            resolved = prelaunch_manager.resolved_python_runtime_executable()

        self.assertEqual(resolved, "D:\\Tools\\Python312\\pythonw.exe")

    def test_resolved_python_runtime_executable_in_frozen_bridge_uses_real_python(self):
        existing_paths = {
            "d:\\tools\\python312\\python.exe",
            "d:\\tools\\python312\\pythonw.exe",
            "d:\\app\\prelaunch_bridge.exe",
        }

        with mock.patch.dict("os.environ", {}, clear=True), mock.patch.object(
            prelaunch_manager.Path,
            "exists",
            autospec=True,
            side_effect=lambda path_obj: str(path_obj).replace("/", "\\").lower() in existing_paths,
        ), mock.patch.object(
            prelaunch_manager.shutil,
            "which",
            return_value=None,
        ), mock.patch.object(
            prelaunch_manager,
            "python_runtime_supports_enhancer_modules",
            side_effect=lambda path: str(path).replace("/", "\\").lower() == "d:\\tools\\python312\\python.exe",
        ), mock.patch.object(
            prelaunch_manager.sys,
            "executable",
            "D:/app/prelaunch_bridge.exe",
        ), mock.patch.object(
            prelaunch_manager.sys,
            "frozen",
            True,
            create=True,
        ):
            resolved = prelaunch_manager.resolved_python_runtime_executable()

        self.assertEqual(resolved, "D:\\Tools\\Python312\\pythonw.exe")

    def test_status_command_returns_json_payload(self):
        fake_evidence = {
            "config_path": "C:/Users/test/.codex/config.toml",
            "config_model_provider": "openai",
            "auth_mode": "chatgpt",
            "threadripper_available": True,
            "threadripper_target_provider": "openai",
            "rows_needing_reconcile": 0,
            "provider_distribution": {"openai": 12},
        }

        with mock.patch.object(prelaunch_bridge, "collect_prelaunch_evidence") as evidence:
            evidence.return_value.to_dict.return_value = fake_evidence

            payload = prelaunch_bridge.handle_status("C:/Users/test/.codex")

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["evidence"]["config_model_provider"], "openai")

    def test_runtime_status_returns_running_processes(self):
        with mock.patch.object(
            prelaunch_bridge,
            "codex_running_processes",
            return_value=[
                {"image": "Codex.exe", "pid": 1234},
                {"image": "codex.exe", "pid": 5678, "exe": r"C:\Users\test\AppData\Local\OpenAI\Codex\bin\hash\codex.exe"},
            ],
        ), mock.patch.object(
            prelaunch_manager,
            "desktop_codex_running_processes",
            return_value=[{"image": "Codex.exe", "pid": 1234}],
        ):
            payload = prelaunch_bridge.handle_runtime_status()

        self.assertTrue(payload["ok"])
        self.assertTrue(payload["codex_running"])
        self.assertEqual(payload["desktop_processes"], [{"image": "Codex.exe", "pid": 1234}])
        self.assertEqual(len(payload["processes"]), 2)

    def test_stop_runtime_terminates_enhancer_runtime_processes(self):
        with mock.patch.object(
            prelaunch_bridge,
            "terminate_enhancer_runtime_processes",
            return_value={"ok": True, "killed": [{"image": "python.exe", "pid": 1234}], "remaining": [], "errors": []},
        ) as terminate_enhancer_runtime_processes:
            payload = prelaunch_bridge.handle_stop_runtime()

        terminate_enhancer_runtime_processes.assert_called_once_with(current_runtime_pid=os.getpid())
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["killed"], [{"image": "python.exe", "pid": 1234}])

    def test_runtime_helper_filter_skips_codex_desktop_gui(self):
        gui = {
            "image": "Codex.exe",
            "pid": 1234,
            "exe": r"C:\Program Files\WindowsApps\OpenAI.Codex\app\Codex.exe",
        }
        helper = {
            "image": "codex.exe",
            "pid": 2345,
            "exe": r"C:\Program Files\WindowsApps\OpenAI.Codex\app\resources\codex.exe",
        }

        self.assertFalse(prelaunch_manager.is_runtime_helper_process(gui))
        self.assertTrue(prelaunch_manager.is_runtime_helper_process(helper))

    def test_terminate_codex_processes_only_targets_runtime_helpers_without_tree_kill(self):
        processes = [
            {
                "image": "Codex.exe",
                "pid": 1234,
                "exe": r"C:\Program Files\WindowsApps\OpenAI.Codex\app\Codex.exe",
            },
            {
                "image": "codex.exe",
                "pid": 2345,
                "exe": r"C:\Program Files\WindowsApps\OpenAI.Codex\app\resources\codex.exe",
            },
        ]
        calls = []

        def fake_run(args, **kwargs):
            calls.append(args)
            return mock.Mock(returncode=0, stdout="", stderr="")

        with mock.patch.object(
            prelaunch_manager,
            "codex_running_processes",
            side_effect=[processes, []],
        ), mock.patch.object(prelaunch_manager.subprocess, "run", side_effect=fake_run):
            payload = prelaunch_manager.terminate_codex_processes(timeout_seconds=0.1)

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["killed"], [processes[1]])
        self.assertEqual(calls, [["taskkill", "/PID", "2345", "/F"]])

    def test_official_launch_skips_history_restore_and_returns_structured_payload(self):
        calls = []
        compatibility_payload = {"ok": True, "skipped": True, "reason": "compatibility_check_only", "status": {"rows_needing_reconcile": 0}}
        launch_payload = {"ok": True, "method": "appid", "pid": 4321}

        with mock.patch.object(
            prelaunch_bridge,
            "run_threadripper_compatibility_check",
            side_effect=lambda *args, **kwargs: calls.append("compatibility") or compatibility_payload,
        ), mock.patch.object(
            prelaunch_bridge,
            "launch_codex_desktop",
            side_effect=lambda: calls.append("launch") or launch_payload,
        ), mock.patch.object(
            prelaunch_bridge,
            "launch_codex_desktop_with_enhancer",
        ) as enhanced_launch, mock.patch.object(
            prelaunch_bridge,
            "current_provider_config_payload",
            side_effect=lambda *args, **kwargs: calls.append("provider")
            or {
                "config_path": "config.toml",
                "backup_path": None,
                "mode": "official",
                "current_model_provider": "openai",
                "target_model_provider": "openai",
                "verified_model_provider": "openai",
                "source": "existing_config",
                "mutated": False,
            },
        ):
            payload = prelaunch_bridge.handle_launch(
                codex_home="C:/Users/test/.codex",
                mode="official",
                provider=None,
                projectless_mode="none",
            )

        self.assertEqual(calls, ["provider", "compatibility", "launch"])
        enhanced_launch.assert_not_called()
        self.assertTrue(payload["ok"])
        self.assertEqual(
            payload["provider_config"],
            {
                "config_path": "config.toml",
                "backup_path": None,
                "mode": "official",
                "current_model_provider": "openai",
                "target_model_provider": "openai",
                "verified_model_provider": "openai",
                "source": "existing_config",
                "mutated": False,
            },
        )
        self.assertEqual(payload["sync"], compatibility_payload)
        self.assertEqual(
            payload["repair"],
            {
                "ok": True,
                "skipped": True,
                "reason": "official_launch_keeps_original_chat_state",
            },
        )
        self.assertEqual(payload["launch"], launch_payload)

    def test_launch_flow_keeps_normal_launcher_even_when_enhancer_feature_is_enabled(self):
        calls = []
        compatibility_payload = {"ok": True, "skipped": True, "reason": "compatibility_check_only", "status": {"rows_needing_reconcile": 0}}
        launch_payload = {"ok": True, "method": "appid", "pid": 4321}

        with mock.patch.object(
            prelaunch_bridge,
            "run_threadripper_compatibility_check",
            side_effect=lambda *args, **kwargs: compatibility_payload,
        ), mock.patch.object(
            prelaunch_bridge,
            "current_provider_config_payload",
            return_value={
                "config_path": "config.toml",
                "backup_path": None,
                "mode": "official",
                "current_model_provider": "openai",
                "target_model_provider": "openai",
                "verified_model_provider": "openai",
                "source": "existing_config",
                "mutated": False,
            },
        ), mock.patch.object(
            prelaunch_bridge,
            "launch_codex_desktop",
            side_effect=lambda: calls.append(("normal",)) or launch_payload,
        ) as normal_launch, mock.patch.object(
            prelaunch_bridge,
            "launch_codex_desktop_with_enhancer",
        ) as enhanced_launch:
            payload = prelaunch_bridge.handle_launch(
                codex_home="C:/Users/test/.codex",
                mode="official",
                provider=None,
                projectless_mode="none",
            )

        normal_launch.assert_called_once_with()
        enhanced_launch.assert_not_called()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["launch"], launch_payload)
        self.assertEqual(calls, [("normal",)])

    def test_all_login_modes_repair_original_place_before_provider_compatibility_check(self):
        provider = {
            "key": "lac",
            "name": "LAC",
            "base_url": "http://127.0.0.1:20128/v1",
            "wire_api": "responses",
            "env_key": "OPENAI_API_KEY",
            "requires_openai_auth": True,
            "experimental_bearer_token": "sk-test",
        }

        for mode in ("official", "api", "hybrid"):
            with self.subTest(mode=mode):
                calls = []
                profile = None if mode == "official" else provider

                with mock.patch.object(
                    prelaunch_bridge,
                    "configure_provider_for_launch",
                    side_effect=lambda *args, **kwargs: calls.append("configure")
                    or mock.Mock(
                        config_path="config.toml",
                        backup_path="config.toml.backup",
                        mode=mode,
                        target_model_provider="openai" if mode == "official" else "lac",
                        verified_model_provider="openai" if mode == "official" else "lac",
                    ),
                ), mock.patch.object(
                    prelaunch_bridge,
                    "current_provider_config_payload",
                    side_effect=lambda *args, **kwargs: calls.append("provider")
                    or {
                        "config_path": "config.toml",
                        "backup_path": None,
                        "mode": "official",
                        "current_model_provider": "openai",
                        "target_model_provider": "openai",
                        "verified_model_provider": "openai",
                        "source": "existing_config",
                        "mutated": False,
                    },
                ), mock.patch.object(
                    prelaunch_bridge,
                    "run_threadripper_compatibility_check",
                    side_effect=lambda *args, **kwargs: calls.append("compatibility")
                    or {"ok": True, "skipped": True, "reason": "compatibility_check_only", "status": {"rows_needing_reconcile": 0}},
                ), mock.patch.object(
                    prelaunch_bridge,
                    "run_history_repair",
                    side_effect=lambda *args, **kwargs: calls.append("repair")
                    or {"ok": True, "summary": {"threads_selected": 1}},
                ), mock.patch.object(
                    prelaunch_bridge,
                    "launch_codex_desktop",
                    side_effect=lambda: calls.append("launch") or {"ok": True, "method": "appid"},
                ), mock.patch.object(
                    prelaunch_bridge,
                    "launch_codex_desktop_with_enhancer",
                ) as enhanced_launch:
                    payload = prelaunch_bridge.handle_launch(
                        codex_home="C:/Users/test/.codex",
                        mode=mode,
                        provider=profile,
                        projectless_mode="none",
                        restore_history=True,
                    )

                self.assertTrue(payload["ok"])
                expected_calls = ["provider", "compatibility", "launch"] if mode == "official" else ["repair", "configure", "compatibility", "launch"]
                self.assertEqual(calls, expected_calls)
                enhanced_launch.assert_not_called()

    def test_hide_official_quota_notice_prepares_marker_and_continues_for_official_launch(self):
        notice_payload = {
            "ok": True,
            "skipped": False,
            "method": "marker",
            "marker_path": "C:/Users/test/AppData/Local/Packages/OpenAI.Codex_2p2nqsd0c76g0/LocalCache/Roaming/Codex/ai-strategist-prelaunch-notice-state.json",
        }

        with mock.patch.object(
            prelaunch_bridge,
            "prepare_codex_desktop_notice_state",
            return_value=notice_payload,
        ) as prepare_notice, mock.patch.object(
            prelaunch_bridge,
            "configure_provider_for_launch",
        ) as configure_provider, mock.patch.object(
            prelaunch_bridge,
            "current_provider_config_payload",
            return_value={
                "config_path": "config.toml",
                "backup_path": None,
                "mode": "official",
                "current_model_provider": "codexzh",
                "target_model_provider": "openai",
                "verified_model_provider": "codexzh",
                "source": "transient_official_runtime_override",
                "mutated": False,
            },
        ) as current_provider, mock.patch.object(
            prelaunch_bridge,
            "run_threadripper_compatibility_check",
            return_value={"ok": True, "skipped": True, "reason": "compatibility_check_only", "status": {}},
        ) as run_compatibility, mock.patch.object(
            prelaunch_bridge,
            "run_history_repair",
        ) as run_repair, mock.patch.object(
            prelaunch_bridge,
            "launch_codex_desktop",
            return_value={"ok": True, "method": "appid"},
        ) as launch_codex, mock.patch.object(
            prelaunch_bridge,
            "launch_codex_desktop_with_enhancer",
        ) as enhanced_launch:
            payload = prelaunch_bridge.handle_launch(
                codex_home="C:/Users/test/.codex",
                mode="official",
                provider=None,
                projectless_mode="none",
                hide_official_quota_notice=True,
            )

        prepare_notice.assert_called_once_with()
        configure_provider.assert_not_called()
        current_provider.assert_called_once()
        run_compatibility.assert_called_once()
        run_repair.assert_not_called()
        launch_codex.assert_called_once_with()
        enhanced_launch.assert_not_called()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["notice_suppression"], notice_payload)
        self.assertEqual(payload["launch"]["method"], "appid")

    def test_launch_preserves_codex_when_takeover_would_have_failed(self):
        with mock.patch.object(
            prelaunch_bridge,
            "prepare_codex_takeover",
            return_value={
                "ok": False,
                "skipped": False,
                "reason": "terminate_failed",
                "killed": [],
                "remaining": [{"image": "Codex.exe", "pid": 1234}],
                "errors": ["Codex.exe PID 1234: access denied"],
            },
        ), mock.patch.object(
            prelaunch_bridge,
            "launch_codex_desktop",
            return_value={"ok": True, "method": "appid", "pid": 4321},
        ):
            payload = prelaunch_bridge.handle_launch(
                codex_home="C:/Users/test/.codex",
                mode="official",
                provider=None,
                projectless_mode="none",
            )

        self.assertEqual(payload["takeover"]["reason"], "launch_preserves_existing_codex")
        self.assertNotEqual(payload.get("launch"), {"ok": False, "skipped": True, "reason": "takeover_failed"})

    def test_hide_official_quota_notice_prepares_marker_and_continues_for_api_launch(self):
        calls = []
        notice_payload = {"ok": True, "skipped": False, "method": "marker"}
        provider = {
            "key": "lac",
            "name": "LAC",
            "base_url": "http://127.0.0.1:20128/v1",
            "wire_api": "responses",
            "env_key": "OPENAI_API_KEY",
        }

        with mock.patch.object(
            prelaunch_bridge,
            "prepare_codex_desktop_notice_state",
            side_effect=lambda: calls.append("notice") or notice_payload,
        ) as prepare_notice, mock.patch.object(
            prelaunch_bridge,
            "configure_provider_for_launch",
            side_effect=lambda *args, **kwargs: calls.append("configure")
            or mock.Mock(
                config_path="config.toml",
                backup_path="config.toml.backup",
                mode="api",
                target_model_provider="lac",
                verified_model_provider="lac",
            ),
        ), mock.patch.object(
            prelaunch_bridge,
            "run_threadripper_compatibility_check",
            side_effect=lambda *args, **kwargs: calls.append("compatibility")
            or {"ok": True, "skipped": True, "reason": "compatibility_check_only", "status": {}},
        ), mock.patch.object(
            prelaunch_bridge,
            "run_history_repair",
            side_effect=lambda *args, **kwargs: calls.append("repair")
            or {"ok": True, "summary": {"threads_selected": 1}},
        ), mock.patch.object(
            prelaunch_bridge,
            "launch_codex_desktop",
            side_effect=lambda: calls.append("launch") or {"ok": True, "method": "appid"},
        ):
            payload = prelaunch_bridge.handle_launch(
                "C:/Users/test/.codex",
                "api",
                provider,
                "none",
                hide_official_quota_notice=True,
            )

        prepare_notice.assert_called_once_with()
        self.assertEqual(calls, ["notice", "configure", "compatibility", "launch"])
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["repair"], {"ok": True, "skipped": True, "reason": "launch_history_restore_disabled"})
        self.assertEqual(payload["notice_suppression"], notice_payload)
        self.assertEqual(payload["provider_config"]["target_model_provider"], "lac")

    def test_api_launch_falls_back_to_existing_provider_profile(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            codex_home = Path(temp_dir)
            (codex_home / "config.toml").write_text(
                '\n'.join(
                    [
                        'model_provider = "lac"',
                        '',
                        '[model_providers.lac]',
                        'name = "LAC"',
                        'base_url = "http://127.0.0.1:20128/v1"',
                        'wire_api = "responses"',
                        'requires_openai_auth = true',
                        'experimental_bearer_token = "sk-test"',
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            with mock.patch.object(
                prelaunch_bridge,
                "run_threadripper_compatibility_check",
                return_value={"ok": True, "skipped": True, "reason": "compatibility_check_only", "status": {}},
            ), mock.patch.object(
                prelaunch_bridge,
                "run_history_repair",
                return_value={"ok": True, "summary": {"threads_selected": 1}},
            ), mock.patch.object(
                prelaunch_bridge,
                "launch_codex_desktop",
                return_value={"ok": True, "method": "appid"},
            ):
                payload = prelaunch_bridge.handle_launch(str(codex_home), "api", None, "none")

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["provider_config"]["target_model_provider"], "lac")
        self.assertEqual(payload["launch"]["method"], "appid")

    def test_hybrid_launch_reuses_existing_provider_config_without_mutating_it(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            codex_home = Path(temp_dir)
            (codex_home / "config.toml").write_text(
                '\n'.join(
                    [
                        'model_provider = "openai"',
                        '',
                        '[model_providers.lac]',
                        'name = "LAC"',
                        'base_url = "http://127.0.0.1:20128/v1"',
                        'wire_api = "responses"',
                        'requires_openai_auth = true',
                        'experimental_bearer_token = "sk-test"',
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            with mock.patch.object(
                prelaunch_bridge,
                "run_threadripper_compatibility_check",
                return_value={"ok": True, "skipped": True, "reason": "compatibility_check_only", "status": {}},
            ) as run_compatibility, mock.patch.object(
                prelaunch_bridge,
                "run_history_repair",
                return_value={"ok": True, "summary": {"threads_selected": 1}},
            ) as run_repair, mock.patch.object(
                prelaunch_bridge,
                "launch_codex_desktop",
                return_value={"ok": True, "method": "appid"},
            ) as launch_codex, mock.patch.object(
                prelaunch_bridge,
                "launch_codex_desktop_with_enhancer",
            ) as enhanced_launch:
                payload = prelaunch_bridge.handle_launch(str(codex_home), "hybrid", None, "none")

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["provider_config"]["target_model_provider"], "lac")
        self.assertEqual(payload["provider_config"]["verified_model_provider"], "lac")
        self.assertEqual(payload["repair"], {"ok": True, "skipped": True, "reason": "launch_history_restore_disabled"})
        self.assertEqual(payload["provider_compatibility"], {"ok": True, "skipped": True, "reason": "compatibility_check_only", "status": {}})
        self.assertEqual(payload["launch"]["method"], "appid")
        run_repair.assert_not_called()
        run_compatibility.assert_called_once()
        launch_codex.assert_called_once_with()
        enhanced_launch.assert_not_called()

    def test_hybrid_launch_skips_codex_takeover(self):
        with tempfile.TemporaryDirectory() as tmp:
            codex_home = Path(tmp) / ".codex"
            codex_home.mkdir()
            config_path = codex_home / "config.toml"
            config_path.write_text(
                "\n".join(
                    [
                        'model_provider = "lac"',
                        "",
                        "[model_providers.lac]",
                        'name = "LAC"',
                        'base_url = "http://127.0.0.1:20128/v1"',
                        'wire_api = "responses"',
                        'requires_openai_auth = true',
                        'experimental_bearer_token = "sk-test"',
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            with mock.patch.object(
                prelaunch_bridge,
                "prepare_codex_takeover",
                side_effect=AssertionError("launch must not stop existing Codex"),
            ), mock.patch.object(
                prelaunch_bridge,
                "run_threadripper_compatibility_check",
                return_value={"ok": True, "skipped": True, "reason": "compatibility_check_only", "status": {}},
            ), mock.patch.object(
                prelaunch_bridge,
                "launch_codex_desktop",
                return_value={"ok": True, "method": "appid"},
            ):
                payload = prelaunch_bridge.handle_launch(str(codex_home), "hybrid", None, "none")

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["takeover"]["reason"], "launch_preserves_existing_codex")
        self.assertEqual(payload["launch"]["method"], "appid")

    def test_hybrid_launch_requires_provider_token(self):
        with tempfile.TemporaryDirectory() as tmp:
            codex_home = Path(tmp) / ".codex"
            codex_home.mkdir()
            (codex_home / "config.toml").write_text(
                "\n".join(
                    [
                        'model_provider = "codexzh"',
                        "",
                        "[model_providers.codexzh]",
                        'name = "codexzh"',
                        'base_url = "https://api.codexzh.com/v1"',
                        'wire_api = "responses"',
                        'requires_openai_auth = true',
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            with mock.patch.object(
                prelaunch_bridge,
                "run_threadripper_compatibility_check",
                return_value={"ok": True, "skipped": True, "reason": "compatibility_check_only", "status": {}},
            ), mock.patch.object(
                prelaunch_bridge,
                "launch_codex_desktop",
                return_value={"ok": True, "method": "appid"},
            ):
                payload = prelaunch_bridge.handle_launch(str(codex_home), "hybrid", None, "none")

        self.assertFalse(payload["ok"])
        self.assertIn("No hybrid-capable provider found", payload["error"])

    def test_existing_session_enhanced_launch_does_not_touch_provider_or_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            codex_home = Path(tmp) / ".codex"
            codex_home.mkdir()
            (codex_home / "config.toml").write_text('model_provider = "codexzh"\n', encoding="utf-8")

            evidence = mock.Mock()
            evidence.to_dict.return_value = {"ok": True, "config_model_provider": "codexzh"}
            with mock.patch.object(
                prelaunch_bridge,
                "collect_prelaunch_evidence",
                return_value=evidence,
            ), mock.patch.object(
                prelaunch_bridge,
                "load_provider_profile_from_config",
                side_effect=AssertionError("existing-session launch must not read provider profiles"),
            ), mock.patch.object(
                prelaunch_bridge,
                "configure_provider_for_launch",
                side_effect=AssertionError("existing-session launch must not mutate provider config"),
            ), mock.patch.object(
                prelaunch_bridge,
                "run_history_repair",
                side_effect=AssertionError("existing-session launch must not repair history"),
            ), mock.patch.object(
                prelaunch_bridge,
                "launch_codex_desktop_with_enhancer",
                return_value={"ok": True, "method": "enhancer_runtime", "runtime_pid": 1234},
            ) as launch:
                payload = prelaunch_bridge.handle_enhanced_launch(str(codex_home))

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["mode"], "existing-session-enhancer")
        self.assertEqual(payload["stages"]["locate_codex"]["config_model_provider"], "codexzh")
        self.assertEqual(payload["launch"]["method"], "enhancer_runtime")
        launch.assert_called_once_with(codex_home, "existing-session")

    def test_existing_session_enhanced_launch_reports_locate_failures_in_locate_stage(self):
        with tempfile.TemporaryDirectory() as tmp:
            codex_home = Path(tmp) / ".codex"
            codex_home.mkdir()

            with mock.patch.object(
                prelaunch_bridge,
                "collect_prelaunch_evidence",
                side_effect=OSError(193, "%1 is not a valid Win32 application"),
            ), mock.patch.object(
                prelaunch_bridge,
                "launch_codex_desktop_with_enhancer",
            ) as launch:
                payload = prelaunch_bridge.handle_enhanced_launch(str(codex_home))

        self.assertFalse(payload["ok"])
        self.assertIn("locate_codex", payload["stages"])
        self.assertNotIn("launch_with_enhancer", payload["stages"])
        launch.assert_not_called()

    def test_threadripper_status_error_does_not_block_prelaunch_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            codex_home = Path(tmp) / ".codex"
            codex_home.mkdir()
            (codex_home / "config.toml").write_text('model_provider = "openai"\n', encoding="utf-8")
            fake_tool = Path(tmp) / "codex-threadripper"
            fake_tool.write_text("not a windows executable", encoding="utf-8")

            with mock.patch.dict(os.environ, {"AI_STRATEGIST_THREADRIPPER": str(fake_tool)}, clear=False), mock.patch.object(
                prelaunch_manager.subprocess,
                "run",
                side_effect=OSError(193, "%1 is not a valid Win32 application"),
            ):
                evidence = prelaunch_manager.collect_prelaunch_evidence(codex_home)

        self.assertTrue(evidence.threadripper_available)
        self.assertIsNone(evidence.threadripper_target_provider)
        self.assertIsNone(evidence.rows_needing_reconcile)

    def test_enhancer_runtime_ready_stable_wait_defaults_to_startup_settle_delay(self):
        with mock.patch.dict("os.environ", {}, clear=True):
            self.assertGreaterEqual(prelaunch_manager.enhancer_ready_stable_seconds(), 3.0)

    def test_enhancer_runtime_ready_stable_wait_can_be_overridden(self):
        with mock.patch.dict("os.environ", {"AI_STRATEGIST_ENHANCER_READY_STABLE_SECONDS": "0.5"}, clear=True):
            self.assertEqual(prelaunch_manager.enhancer_ready_stable_seconds(), 0.5)

    def test_stable_enhancer_runtime_script_copies_from_pyinstaller_temp_dir(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as local_app_data:
            mei_dir = Path(tmp) / "_MEI12345"
            mei_dir.mkdir()
            for name in (
                "enhancer_runtime.py",
                "enhancer_renderer_inject.js",
                "enhancer_runtime_watcher.py",
                "enhancer_handoff.py",
                "repair_codex_desktop_history.py",
                "prelaunch_manager.py",
                "codex_desktop_launcher.py",
                "codex_desktop_app_paths.py",
            ):
                (mei_dir / name).write_text(f"# {name}\n", encoding="utf-8")

            with mock.patch.dict(os.environ, {"LOCALAPPDATA": local_app_data}, clear=False):
                runtime_script = prelaunch_manager.stable_enhancer_runtime_script(
                    mei_dir / "enhancer_runtime.py"
                )

            self.assertEqual(
                runtime_script,
                Path(local_app_data) / "AI-Strategist" / "enhancer-runtime" / "enhancer_runtime.py",
            )
            self.assertTrue(runtime_script.exists())
            self.assertTrue((runtime_script.parent / "enhancer_renderer_inject.js").exists())
            self.assertTrue((runtime_script.parent / "enhancer_runtime_watcher.py").exists())

    def test_stable_enhancer_runtime_script_refreshes_local_app_data_copy(self):
        with tempfile.TemporaryDirectory() as repo_dir, tempfile.TemporaryDirectory() as local_app_data:
            repo_path = Path(repo_dir)
            stable_dir = Path(local_app_data) / "AI-Strategist" / "enhancer-runtime"
            stable_dir.mkdir(parents=True)
            modules = (
                "enhancer_runtime.py",
                "enhancer_renderer_inject.js",
                "enhancer_runtime_watcher.py",
                "enhancer_handoff.py",
                "repair_codex_desktop_history.py",
                "prelaunch_manager.py",
                "codex_desktop_launcher.py",
                "codex_desktop_app_paths.py",
            )
            for name in modules:
                (repo_path / name).write_text(f"# fresh {name}\n", encoding="utf-8")
                (stable_dir / name).write_text(f"# stale {name}\n", encoding="utf-8")

            with mock.patch.dict(os.environ, {"LOCALAPPDATA": local_app_data}, clear=False), mock.patch.object(
                prelaunch_manager,
                "__file__",
                str(repo_path / "prelaunch_manager.py"),
            ):
                runtime_script = prelaunch_manager.stable_enhancer_runtime_script(stable_dir / "enhancer_runtime.py")

            self.assertEqual(runtime_script, stable_dir / "enhancer_runtime.py")
            self.assertEqual(runtime_script.read_text(encoding="utf-8"), "# fresh enhancer_runtime.py\n")
            self.assertEqual(
                (runtime_script.parent / "codex_desktop_launcher.py").read_text(encoding="utf-8"),
                "# fresh codex_desktop_launcher.py\n",
            )

    def test_enhancer_runtime_launch_options_hide_console_windows(self):
        options = prelaunch_manager.enhancer_runtime_launch_options()

        self.assertIs(options["stdin"], prelaunch_manager.subprocess.DEVNULL)
        self.assertIs(options["stdout"], prelaunch_manager.subprocess.DEVNULL)
        self.assertIs(options["stderr"], prelaunch_manager.subprocess.DEVNULL)
        if os.name == "nt":
            self.assertTrue(options["creationflags"] & getattr(prelaunch_manager.subprocess, "CREATE_NO_WINDOW", 0))

    def test_main_status_command_prints_json(self):
        fake_payload = {"ok": True, "evidence": {"auth_mode": "chatgpt"}}

        with mock.patch.object(prelaunch_bridge, "handle_status", return_value=fake_payload), mock.patch(
            "sys.argv",
            ["prelaunch_bridge.py", "status", "--codex-home", "C:/Users/test/.codex"],
        ), mock.patch("sys.stdout", new_callable=io.StringIO) as stdout:
            exit_code = prelaunch_bridge.main()

        self.assertEqual(exit_code, 0)
        self.assertEqual(stdout.getvalue().strip(), '{"ok": true, "evidence": {"auth_mode": "chatgpt"}}')

    def test_main_launch_command_forwards_args_to_handle_launch(self):
        fake_payload = {"ok": True, "launch": {"method": "appid"}}

        with mock.patch.object(prelaunch_bridge, "handle_launch", return_value=fake_payload) as handle_launch, mock.patch(
            "sys.argv",
            [
                "prelaunch_bridge.py",
                "launch",
                "--codex-home",
                "C:/Users/test/.codex",
                "--mode",
                "official",
                "--projectless-mode",
                "none",
                "--provider-json",
                '{"key":"openai","name":"OpenAI","base_url":"https://api.openai.com/v1","wire_api":"responses"}',
                "--restore-history",
            ],
        ), mock.patch("sys.stdout", new_callable=io.StringIO) as stdout:
            exit_code = prelaunch_bridge.main()

        self.assertEqual(exit_code, 0)
        handle_launch.assert_called_once_with(
            "C:/Users/test/.codex",
            "official",
            {
                "key": "openai",
                "name": "OpenAI",
                "base_url": "https://api.openai.com/v1",
                "wire_api": "responses",
            },
            "none",
            False,
            True,
            include_archived=False,
            allow_missing_cwd=False,
            allow_empty_cwd=False,
            allow_missing_session=False,
            unarchive_selected=False,
        )
        self.assertEqual(stdout.getvalue().strip(), '{"ok": true, "launch": {"method": "appid"}}')

    def test_main_launch_command_forwards_hide_official_quota_notice_flag(self):
        fake_payload = {"ok": True, "launch": {"method": "appid"}}

        with mock.patch.object(prelaunch_bridge, "handle_launch", return_value=fake_payload) as handle_launch, mock.patch(
            "sys.argv",
            [
                "prelaunch_bridge.py",
                "launch",
                "--codex-home",
                "C:/Users/test/.codex",
                "--mode",
                "api",
                "--projectless-mode",
                "none",
                "--provider-json",
                '{"key":"lac","name":"LAC","base_url":"http://127.0.0.1:20128/v1","wire_api":"responses","env_key":"OPENAI_API_KEY"}',
                "--hide-official-quota-notice",
            ],
        ), mock.patch("sys.stdout", new_callable=io.StringIO):
            exit_code = prelaunch_bridge.main()

        self.assertEqual(exit_code, 0)
        handle_launch.assert_called_once_with(
            "C:/Users/test/.codex",
            "api",
            {
                "key": "lac",
                "name": "LAC",
                "base_url": "http://127.0.0.1:20128/v1",
                "wire_api": "responses",
                "env_key": "OPENAI_API_KEY",
            },
            "none",
            True,
            False,
            include_archived=False,
            allow_missing_cwd=False,
            allow_empty_cwd=False,
            allow_missing_session=False,
            unarchive_selected=False,
        )

    def test_main_launch_command_returns_nonzero_for_failed_payload(self):
        fake_payload = {
            "ok": False,
            "repair": {"ok": False, "error": "repair failed"},
            "launch": {"ok": False, "skipped": True, "reason": "prelaunch_repair_failed"},
        }

        with mock.patch.object(prelaunch_bridge, "handle_launch", return_value=fake_payload), mock.patch(
            "sys.argv",
            [
                "prelaunch_bridge.py",
                "launch",
                "--codex-home",
                "C:/Users/test/.codex",
                "--mode",
                "official",
                "--projectless-mode",
                "none",
                "--provider-json",
                '{"key":"openai","name":"OpenAI","base_url":"https://api.openai.com/v1","wire_api":"responses"}',
            ],
        ), mock.patch("sys.stdout", new_callable=io.StringIO) as stdout:
            exit_code = prelaunch_bridge.main()

        self.assertNotEqual(exit_code, 0)
        self.assertEqual(
            stdout.getvalue().strip(),
            '{"ok": false, "repair": {"ok": false, "error": "repair failed"}, "launch": {"ok": false, "skipped": true, "reason": "prelaunch_repair_failed"}}',
        )

    def test_main_rejects_invalid_provider_json_argument(self):
        with mock.patch(
            "sys.argv",
            [
                "prelaunch_bridge.py",
                "launch",
                "--codex-home",
                "C:/Users/test/.codex",
                "--provider-json",
                "{not-json}",
            ],
        ), mock.patch("sys.stdout", new_callable=io.StringIO) as stdout:
            exit_code = prelaunch_bridge.main()

        self.assertNotEqual(exit_code, 0)
        self.assertIn("provider-json", stdout.getvalue())

    def test_run_history_repair_performs_real_mutation_helpers(self):
        threads = [{"id": "t1", "cwd": r"C:\repo", "archived": 0, "model_provider": "openai"}]
        selected = [{"id": "t1", "cwd": r"C:\repo", "archived": 0, "model_provider": "openai"}]
        skipped = [{"id": "t2", "reason": "archived"}]
        summary = {"threads_total": 2, "threads_selected": 1}
        merged_rows = [{"id": "t1", "thread_name": "restored"}]
        repaired_state = {"thread_hints": 1, "saved_workspace_roots": 1}
        attributions = [
            {
                "id": "t1",
                "target_location": "workspace",
                "workspace_root": r"C:\repo",
                "reason": "cwd_exists_and_session_exists",
                "provider": "openai",
            }
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            codex_home = Path(temp_dir)
            (codex_home / "state_5.sqlite").write_text("", encoding="utf-8")
            (codex_home / ".codex-global-state.json").write_text("{}", encoding="utf-8")
            backup_dir = codex_home / "desktop_history_repair_backups" / "20260522-120000"

            with mock.patch.object(prelaunch_bridge.history_repair, "load_threads", return_value=threads) as load_threads, mock.patch.object(
                prelaunch_bridge.history_repair,
                "selected_threads",
                return_value=(selected, skipped),
            ) as selected_threads, mock.patch.object(
                prelaunch_bridge.history_repair,
                "build_result",
                return_value=dict(summary),
            ) as build_result, mock.patch.object(
                prelaunch_bridge.history_repair,
                "backup_files",
                return_value=backup_dir,
            ) as backup_files, mock.patch.object(
                prelaunch_bridge.history_repair,
                "read_jsonl",
                return_value=[{"id": "existing"}],
            ) as read_jsonl, mock.patch.object(
                prelaunch_bridge.history_repair,
                "make_index_rows",
                return_value=merged_rows,
            ) as make_index_rows, mock.patch.object(
                prelaunch_bridge.history_repair,
                "write_jsonl",
            ) as write_jsonl, mock.patch.object(
                prelaunch_bridge.history_repair,
                "repair_state",
                return_value=repaired_state,
            ) as repair_state, mock.patch.object(
                prelaunch_bridge.history_repair,
                "thread_attributions",
                return_value=attributions,
            ) as thread_attributions, mock.patch.object(
                prelaunch_bridge.history_repair,
                "unarchive_selected_threads",
            ) as unarchive_selected_threads:
                payload = prelaunch_bridge.run_history_repair(str(codex_home), "none")

        load_threads.assert_called_once_with(codex_home / "state_5.sqlite")
        selected_threads.assert_called_once()
        build_result.assert_called_once_with(codex_home, threads, selected, skipped, False)
        backup_files.assert_called_once_with(codex_home)
        read_jsonl.assert_called_once_with(codex_home / "session_index.jsonl")
        make_index_rows.assert_called_once_with([{"id": "existing"}], selected)
        write_jsonl.assert_called_once_with(codex_home / "session_index.jsonl", merged_rows)
        repair_state.assert_called_once_with(codex_home / ".codex-global-state.json", selected, None, "none")
        thread_attributions.assert_called_once()
        unarchive_selected_threads.assert_not_called()
        self.assertEqual(
            payload,
            {
                "ok": True,
                "summary": {
                    "threads_total": 2,
                    "threads_selected": 1,
                    "thread_attributions": attributions,
                    "backup_dir": str(backup_dir),
                    "session_index_rows": 1,
                    "unarchived": 0,
                    "thread_hints": 1,
                    "saved_workspace_roots": 1,
                },
            },
        )

    def test_selected_threads_keeps_rows_with_first_user_message_when_has_user_event_is_false(self):
        args = mock.Mock(
            include_archived=False,
            allow_missing_cwd=False,
            allow_empty_cwd=False,
            allow_missing_session=False,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            cwd = Path(temp_dir) / "project"
            cwd.mkdir()
            (cwd / "file.txt").write_text("content", encoding="utf-8")
            rollout = Path(temp_dir) / "rollout.jsonl"
            rollout.write_text("{}", encoding="utf-8")
            threads = [
                {
                    "id": "t1",
                    "cwd": str(cwd),
                    "archived": 0,
                    "rollout_path": str(rollout),
                    "has_user_event": 0,
                    "first_user_message": "真实用户对话",
                    "title": "真实用户对话",
                }
            ]

            selected, skipped = prelaunch_bridge.history_repair.selected_threads(threads, args)

        self.assertEqual([thread["id"] for thread in selected], ["t1"])
        self.assertEqual(skipped, [])

    def test_selected_threads_still_skips_rows_without_any_user_message(self):
        args = mock.Mock(
            include_archived=False,
            allow_missing_cwd=True,
            allow_empty_cwd=True,
            allow_missing_session=True,
        )
        threads = [
            {
                "id": "empty",
                "cwd": None,
                "archived": 0,
                "rollout_path": None,
                "has_user_event": 0,
                "first_user_message": "",
                "title": "只有标题不算真实用户消息",
            }
        ]

        selected, skipped = prelaunch_bridge.history_repair.selected_threads(threads, args)

        self.assertEqual(selected, [])
        self.assertEqual(skipped[0]["reason"], "no_user_message")

    def test_selected_threads_default_policy_skips_archived_deleted_and_empty_workspace_rows(self):
        args = mock.Mock(
            include_archived=False,
            allow_missing_cwd=False,
            allow_empty_cwd=False,
            allow_missing_session=False,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            active_cwd = root / "active"
            active_cwd.mkdir()
            (active_cwd / "file.txt").write_text("content", encoding="utf-8")
            empty_cwd = root / "empty"
            empty_cwd.mkdir()
            rollout = root / "rollout.jsonl"
            rollout.write_text("{}", encoding="utf-8")
            missing_rollout = root / "deleted.jsonl"

            threads = [
                {
                    "id": "active",
                    "cwd": str(active_cwd),
                    "archived": 0,
                    "rollout_path": str(rollout),
                    "has_user_event": 1,
                    "first_user_message": "keep",
                },
                {
                    "id": "archived",
                    "cwd": str(active_cwd),
                    "archived": 1,
                    "rollout_path": str(rollout),
                    "has_user_event": 1,
                    "first_user_message": "skip archived",
                },
                {
                    "id": "deleted",
                    "cwd": str(active_cwd),
                    "archived": 0,
                    "rollout_path": str(missing_rollout),
                    "has_user_event": 1,
                    "first_user_message": "skip missing session file",
                },
                {
                    "id": "empty-folder",
                    "cwd": str(empty_cwd),
                    "archived": 0,
                    "rollout_path": str(rollout),
                    "has_user_event": 1,
                    "first_user_message": "skip empty workspace",
                },
                {
                    "id": "missing-cwd",
                    "cwd": str(root / "missing"),
                    "archived": 0,
                    "rollout_path": str(rollout),
                    "has_user_event": 1,
                    "first_user_message": "skip missing cwd",
                },
            ]

            selected, skipped = prelaunch_bridge.history_repair.selected_threads(threads, args)

        self.assertEqual([thread["id"] for thread in selected], ["active"])
        self.assertEqual(
            {item["id"]: item["reason"] for item in skipped},
            {
                "archived": "archived",
                "deleted": "missing_session_file",
                "empty-folder": "empty_cwd",
                "missing-cwd": "missing_cwd",
            },
        )

    def test_run_history_repair_forwards_advanced_options_to_selection_policy(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            codex_home = Path(temp_dir)
            (codex_home / "state_5.sqlite").write_text("", encoding="utf-8")
            (codex_home / ".codex-global-state.json").write_text("{}", encoding="utf-8")

            with mock.patch.object(prelaunch_bridge.history_repair, "load_threads", return_value=[]) as load_threads, mock.patch.object(
                prelaunch_bridge.history_repair,
                "selected_threads",
                return_value=([], []),
            ) as selected_threads, mock.patch.object(
                prelaunch_bridge.history_repair,
                "build_result",
                return_value={"threads_total": 0, "threads_selected": 0},
            ), mock.patch.object(
                prelaunch_bridge.history_repair,
                "thread_attributions",
                return_value=[],
            ), mock.patch.object(
                prelaunch_bridge.history_repair,
                "backup_files",
                return_value=codex_home / "backup",
            ), mock.patch.object(
                prelaunch_bridge.history_repair,
                "read_jsonl",
                return_value=[],
            ), mock.patch.object(
                prelaunch_bridge.history_repair,
                "make_index_rows",
                return_value=[],
            ), mock.patch.object(
                prelaunch_bridge.history_repair,
                "write_jsonl",
            ), mock.patch.object(
                prelaunch_bridge.history_repair,
                "repair_state",
                return_value={"projectless_thread_ids": 0},
            ):
                prelaunch_bridge.run_history_repair(
                    str(codex_home),
                    projectless_mode="all",
                    include_archived=True,
                    allow_missing_cwd=True,
                    allow_empty_cwd=True,
                    allow_missing_session=True,
                    unarchive_selected=True,
                )

        load_threads.assert_called_once_with(codex_home / "state_5.sqlite")
        args = selected_threads.call_args.args[1]
        self.assertTrue(args.include_archived)
        self.assertTrue(args.allow_missing_cwd)
        self.assertTrue(args.allow_empty_cwd)
        self.assertTrue(args.allow_missing_session)
        self.assertTrue(args.unarchive_selected)
        self.assertEqual(args.projectless_mode, "all")

    def test_main_repair_command_forwards_advanced_recovery_flags(self):
        fake_payload = {"ok": True, "repair": {"summary": {}}}

        with mock.patch.object(prelaunch_bridge, "handle_repair", return_value=fake_payload) as handle_repair, mock.patch(
            "sys.argv",
            [
                "prelaunch_bridge.py",
                "repair",
                "--codex-home",
                "C:/Users/test/.codex",
                "--projectless-mode",
                "all",
                "--include-archived",
                "--allow-missing-cwd",
                "--allow-empty-cwd",
                "--allow-missing-session",
                "--unarchive-selected",
            ],
        ), mock.patch("sys.stdout", new_callable=io.StringIO):
            exit_code = prelaunch_bridge.main()

        self.assertEqual(exit_code, 0)
        handle_repair.assert_called_once_with(
            "C:/Users/test/.codex",
            "all",
            include_archived=True,
            allow_missing_cwd=True,
            allow_empty_cwd=True,
            allow_missing_session=True,
            unarchive_selected=True,
        )

    def test_handle_launch_does_not_block_when_provider_compatibility_check_fails(self):
        compatibility_payload = {"ok": False, "skipped": True, "reason": "status_failed", "error": "status failed"}

        with mock.patch.object(
            prelaunch_bridge,
            "current_provider_config_payload",
            return_value={
                "config_path": "config.toml",
                "backup_path": None,
                "mode": "official",
                "current_model_provider": "openai",
                "target_model_provider": "openai",
                "verified_model_provider": "openai",
                "source": "existing_config",
                "mutated": False,
            },
        ), mock.patch.object(
            prelaunch_bridge,
            "run_threadripper_compatibility_check",
            return_value=compatibility_payload,
        ), mock.patch.object(
            prelaunch_bridge,
            "launch_codex_desktop_with_enhancer",
            return_value={"ok": True, "method": "enhancer_runtime"},
        ) as launch_codex_desktop:
            payload = prelaunch_bridge.handle_launch("C:/Users/test/.codex", "official", None, "none")

        launch_codex_desktop.assert_called_once()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["sync"], compatibility_payload)
        self.assertEqual(payload["provider_compatibility"], compatibility_payload)

    def test_api_launch_stops_when_repair_raises(self):
        with mock.patch.object(
            prelaunch_bridge,
            "configure_provider_for_launch",
            return_value=mock.Mock(
                config_path="config.toml",
                backup_path="config.toml.backup",
                mode="official",
                target_model_provider="openai",
                verified_model_provider="openai",
            ),
        ), mock.patch.object(
            prelaunch_bridge,
            "run_threadripper_compatibility_check",
            return_value={"ok": True, "skipped": True, "reason": "compatibility_check_only", "status": {}},
        ), mock.patch.object(
            prelaunch_bridge,
            "run_history_repair",
            side_effect=RuntimeError("repair exploded"),
        ), mock.patch.object(prelaunch_bridge, "launch_codex_desktop") as launch_codex_desktop:
            payload = prelaunch_bridge.handle_launch(
                "C:/Users/test/.codex",
                "api",
                {
                    "key": "lac",
                    "name": "LAC",
                    "base_url": "http://127.0.0.1:20128/v1",
                    "wire_api": "responses",
                    "env_key": "OPENAI_API_KEY",
                    "requires_openai_auth": False,
                    "experimental_bearer_token": "",
                },
                "none",
                restore_history=True,
            )

        launch_codex_desktop.assert_not_called()
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["repair"], {"ok": False, "error": "repair exploded"})
        self.assertEqual(payload["launch"], {"ok": False, "skipped": True, "reason": "prelaunch_repair_failed"})

    def test_stop_runtime_only_stops_enhancer_runtime(self):
        with mock.patch.object(
            prelaunch_bridge,
            "terminate_enhancer_runtime_processes",
            return_value={"ok": True, "killed": [{"pid": 1234}], "remaining": []},
        ) as terminate_enhancer_runtime_processes:
            payload = prelaunch_bridge.handle_stop_runtime()

        terminate_enhancer_runtime_processes.assert_called_once_with(current_runtime_pid=os.getpid())
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["killed"], [{"pid": 1234}])

    def test_failed_enhanced_launch_cleanup_preserves_codex_desktop(self):
        terminate_runtimes = mock.Mock(return_value={"ok": True, "killed": [{"pid": 4321}]})
        terminate_desktop = mock.Mock(return_value={"ok": False, "killed": [{"pid": 9999}]})

        payload = codex_desktop_launcher.cleanup_failed_enhanced_launch(
            current_runtime_pid=1111,
            terminate_runtimes=terminate_runtimes,
            terminate_desktop=terminate_desktop,
            timeout_seconds=2.0,
        )

        terminate_runtimes.assert_called_once_with(1111, 2.0)
        terminate_desktop.assert_not_called()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["desktop"]["reason"], "preserve_existing_codex_desktop")
