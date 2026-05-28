import unittest

import enhancer_runtime_watcher


class EnhancerRuntimeWatcherTests(unittest.TestCase):
    def test_watch_step_enters_idle_when_no_codex_process_exists(self):
        state = enhancer_runtime_watcher.WatcherState()

        enhancer_runtime_watcher.watch_step(
            state,
            now=10.0,
            cdp_listening=False,
            codex_pids=[],
            takeover=lambda: False,
        )

        self.assertEqual(state.last_state, "idle")
        self.assertIsNone(state.candidate_pids)

    def test_watch_step_waits_for_grace_period_before_takeover(self):
        state = enhancer_runtime_watcher.WatcherState()

        enhancer_runtime_watcher.watch_step(
            state,
            now=10.0,
            cdp_listening=False,
            codex_pids=[200, 100],
            takeover=lambda: False,
        )

        self.assertEqual(state.last_state, "grace")
        self.assertEqual(state.candidate_pids, (100, 200))
        self.assertEqual(state.candidate_since, 10.0)

    def test_watch_step_triggers_takeover_after_grace_period(self):
        calls: list[str] = []
        state = enhancer_runtime_watcher.WatcherState(
            last_state="grace",
            candidate_pids=(100, 200),
            candidate_since=10.0,
        )

        enhancer_runtime_watcher.watch_step(
            state,
            now=10.0 + enhancer_runtime_watcher.TAKEOVER_GRACE_SECONDS + 1.0,
            cdp_listening=False,
            codex_pids=[100, 200],
            takeover=lambda: calls.append("takeover") or True,
        )

        self.assertEqual(calls, ["takeover"])
        self.assertEqual(state.last_state, "cdp_ok")
        self.assertGreater(state.cooldown_until, 13.5)
        self.assertIsNone(state.candidate_pids)

    def test_default_grace_does_not_takeover_after_short_cdp_gap(self):
        calls: list[str] = []
        state = enhancer_runtime_watcher.WatcherState(
            last_state="grace",
            candidate_pids=(100, 200),
            candidate_since=10.0,
        )

        enhancer_runtime_watcher.watch_step(
            state,
            now=13.5,
            cdp_listening=False,
            codex_pids=[100, 200],
            takeover=lambda: calls.append("takeover") or True,
        )

        self.assertEqual(calls, [])
        self.assertEqual(state.last_state, "grace")
        self.assertEqual(state.candidate_pids, (100, 200))

    def test_watch_step_applies_backoff_after_failed_takeover(self):
        state = enhancer_runtime_watcher.WatcherState(
            last_state="grace",
            candidate_pids=(300,),
            candidate_since=10.0,
        )

        enhancer_runtime_watcher.watch_step(
            state,
            now=10.0 + enhancer_runtime_watcher.TAKEOVER_GRACE_SECONDS + 1.0,
            cdp_listening=False,
            codex_pids=[300],
            takeover=lambda: False,
        )

        self.assertEqual(state.last_state, "failed")
        self.assertGreater(state.backoff_until, 13.0)
        self.assertIsNone(state.candidate_pids)
