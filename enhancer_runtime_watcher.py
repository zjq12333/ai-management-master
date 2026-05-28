from __future__ import annotations

import time
from dataclasses import dataclass
from threading import Event
from typing import Callable


WATCHER_INTERVAL_SECONDS = 3.0
TAKEOVER_GRACE_SECONDS = 20.0
TAKEOVER_FAILURE_BACKOFF_SECONDS = 30.0
TAKEOVER_SUCCESS_COOLDOWN_SECONDS = 15.0


@dataclass
class WatcherState:
    last_state: str | None = None
    backoff_until: float = 0.0
    cooldown_until: float = 0.0
    candidate_pids: tuple[int, ...] | None = None
    candidate_since: float = 0.0


def watch_step(
    state: WatcherState,
    *,
    now: float,
    cdp_listening: bool,
    codex_pids: list[int],
    takeover: Callable[[], bool],
    log: Callable[[str], None] | None = None,
    grace_seconds: float = TAKEOVER_GRACE_SECONDS,
    failure_backoff_seconds: float = TAKEOVER_FAILURE_BACKOFF_SECONDS,
    success_cooldown_seconds: float = TAKEOVER_SUCCESS_COOLDOWN_SECONDS,
) -> WatcherState:
    logger = log or (lambda _line: None)

    if cdp_listening:
        if state.last_state != "cdp_ok":
            logger("CDP is up")
        state.last_state = "cdp_ok"
        state.candidate_pids = None
        return state

    if not codex_pids:
        if state.last_state != "idle":
            logger("no Codex running; idling")
        state.last_state = "idle"
        state.candidate_pids = None
        return state

    if now < state.cooldown_until:
        if state.last_state != "cooldown":
            logger(f"in cooldown after takeover; {state.cooldown_until - now:.1f}s remaining")
        state.last_state = "cooldown"
        return state

    if now < state.backoff_until:
        if state.last_state != "backoff":
            logger(f"in backoff after failed takeover; {state.backoff_until - now:.1f}s remaining")
        state.last_state = "backoff"
        return state

    codex_key = tuple(sorted(codex_pids))
    if state.candidate_pids != codex_key:
        state.candidate_pids = codex_key
        state.candidate_since = now
        state.last_state = "grace"
        logger(f"Codex running without CDP (pids={codex_pids}); waiting before takeover")
        return state

    if now - state.candidate_since < grace_seconds:
        if state.last_state != "grace":
            logger(f"waiting for Codex CDP grace period (pids={codex_pids})")
        state.last_state = "grace"
        return state

    logger(f"Codex running without CDP after grace period (pids={codex_pids}); attempting takeover")
    state.last_state = "takeover"
    success = takeover()
    state.candidate_pids = None
    if success:
        state.cooldown_until = now + success_cooldown_seconds
        state.last_state = "cdp_ok"
        logger("takeover succeeded")
    else:
        state.backoff_until = now + failure_backoff_seconds
        state.last_state = "failed"
        logger("takeover failed")
    return state


def watch_loop(
    *,
    cdp_listening: Callable[[], bool],
    codex_pids: Callable[[], list[int]],
    takeover: Callable[[], bool],
    log: Callable[[str], None] | None = None,
    stop_event: Event | None = None,
    interval_seconds: float = WATCHER_INTERVAL_SECONDS,
) -> int:
    logger = log or (lambda _line: None)
    state = WatcherState()
    logger(f"watcher started (interval={interval_seconds}s)")

    while True:
        if stop_event is not None and stop_event.is_set():
            logger("watcher stopped")
            return 0

        try:
            watch_step(
                state,
                now=time.time(),
                cdp_listening=cdp_listening(),
                codex_pids=codex_pids(),
                takeover=takeover,
                log=logger,
            )
        except Exception as exc:
            logger(f"watch loop error: {exc}")

        time.sleep(interval_seconds)
