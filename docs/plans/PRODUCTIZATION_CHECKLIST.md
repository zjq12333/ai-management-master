# Productization Checklist

## Purpose

This checklist turns AI Strategist from a development-machine-only tool into a **download-and-run desktop product**.

The guiding rule is simple:

> Do not depend on the user machine being lucky.

That means:

- do not depend on user PATH being correct
- do not depend on `WindowsApps` Codex entrypoints
- do not depend on user-preinstalled Python / Git / helper tools
- do not treat current developer-machine success as release readiness

## 1. Must Bundle

These items are required for the main workflow. If missing, the product is not considered generally deliverable.

### 1.1 Runtime Resolution

- [x] Build a single internal runtime resolver for `codex`, Python, and helper binaries.
- [ ] Stop calling bare commands like `codex`, `python`, `git`, `codex-threadripper` in mainline logic.
  - `codex-threadripper` no longer falls back to user PATH from prelaunch status checks; it only runs when product-injected through `AI_STRATEGIST_THREADRIPPER`.
- [ ] Resolve binaries in this order:
  1. bundled application runtime
  2. product-managed local runtime directory
  3. explicit fallback with warning
- [ ] Never rely on `WindowsApps` as the main product execution path.

### 1.2 Codex Runtime

- [ ] Bundle or product-manage a stable runnable Codex CLI path.
- [x] Ensure launch/bridge logic rejects `WindowsApps` Codex shim paths from explicit runtime injection.
- [ ] Ensure all internal wrappers use product-controlled paths.

Evidence:

- `codex_desktop_app_paths.resolved_codex_desktop_exe()` rejects `WindowsApps\OpenAI.Codex_...\app\Codex.exe` even when explicitly injected through `AI_STRATEGIST_CODEX_DESKTOP`.
- Tauri `runtime_resolver` rejects the same shim from `AI_STRATEGIST_CODEX_DESKTOP` before falling back to safer discovery.
- Regression coverage: `python -m pytest tests/test_prelaunch_bridge.py -q` and `cargo test runtime_resolver`.

### 1.3 Python Bridge Runtime

- [x] Bundle a Python runtime or ship the bridge in a form that removes Python as a user prerequisite.
- [x] Add a repeatable build script for a self-contained `prelaunch_bridge.exe`.
- [x] Ensure `prelaunch_bridge.py`, `prelaunch_manager.py`, and `repair_codex_desktop_history.py` are callable through product-owned script resource paths.
- [x] Remove any assumption that system Python exists for the mainline prelaunch bridge path.

Evidence:

- `prelaunch_bridge.exe` is committed under `ai-strategist-desktop/src-tauri/resources/prelaunch/`.
- `Verify-AI-Strategist.ps1` verifies the bundled bridge resource and safe smoke commands.
- `Test-AI-StrategistInstall.ps1` passed against a release NSIS install on the developer machine.

Remaining caveat:

- Clean-machine / VM installed-build verification is still required before release acceptance.

### 1.4 Mainline Helper Tools

- [x] Decide whether `codex-threadripper` is required or optional.
- [ ] If required: bundle it.
- [x] If optional: implement graceful downgrade and remove hard dependency from the mainline repair promise.

Evidence:

- `threadripper_command()` now returns a helper only when `AI_STRATEGIST_THREADRIPPER` points to an existing file.
- If unavailable, `run_threadripper_status()` returns `None` and prelaunch evidence reports `threadripper_available=False` without blocking launch.
- Regression coverage: `test_threadripper_command_ignores_missing_environment_path_without_path_fallback`.

## 2. Can Degrade

These features may be unavailable without making the product unusable, but the UI and diagnostics must explicitly reflect that.

### 2.1 Optional Tooling

- [ ] `git`-related flows may degrade if Git is unavailable.
- [ ] patch/diff developer workflows may degrade if internal patch runner is unavailable.
- [ ] non-core MCP / Skills / maintenance modules may load lazily or show unavailable state.

### 2.2 UI Rules for Degraded Features

- [ ] Never crash or white-screen when optional tooling is unavailable.
- [ ] Show a clear unavailable/degraded badge in the relevant module.
- [ ] Keep `启动与修复` usable even if optional modules are broken.

## 3. First-Run Repair

These checks should happen automatically on first launch or through a guided “Initialize / Repair Environment” flow.

### 3.1 Directory Preparation

- [ ] Create product-managed runtime directory.
- [ ] Create logs / reports / diagnostics directory.
- [ ] Create backup directory for runtime-managed files.

### 3.2 Environment Checks

- [ ] Detect Codex Desktop install path.
- [ ] Detect product-managed Codex CLI path.
- [ ] Detect bridge runtime availability.
- [ ] Detect access to `.codex`, `config.toml`, `auth.json`, `state_5.sqlite`.
- [ ] Detect whether the product can write report and backup files.

### 3.3 Auto Repair Actions

- [ ] If a stable Codex CLI path is missing, provision or repair it automatically.
- [ ] If runtime wrapper paths are stale, rebuild them automatically.
- [ ] If required directories are missing, create them automatically.
- [ ] If old shortcuts / old product names remain, clean them automatically where safe.

### 3.4 User Experience

- [ ] Replace raw internal errors with guided first-run repair outcomes.
- [ ] Show only three outcomes:
  - ready
  - repaired automatically
  - blocked with explicit next action

## 4. Release Acceptance

These gates must pass before claiming the product is broadly downloadable.

### 4.1 Clean Machine Acceptance

- [ ] Install on a clean Windows machine without preinstalled Python / Node / Rust / Git.
- [ ] Open `AI Strategist.exe` successfully.
- [ ] Enter `启动与修复` successfully.
- [ ] Official launch visible and runnable.
- [ ] API launch visible, provider input visible, and runnable.
- [ ] Hybrid launch visible, provider input visible, and runnable.
- [ ] Repair visible and runnable.

### 4.2 Runtime Independence Acceptance

- [ ] Mainline product workflows do not require user PATH edits.
- [ ] Mainline product workflows do not require `WindowsApps` executable access.
- [ ] Mainline product workflows do not require manual dependency installation.

### 4.3 Diagnostics Acceptance

- [ ] Export a stable diagnostics bundle for failures.
- [ ] Diagnostics include:
  - app version
  - runtime resolution results
  - Codex path actually used
  - Python bridge runtime path actually used
  - helper tool availability
  - permission check results
  - latest failure summary

### 4.4 Safety Acceptance

- [ ] Repair and launch mutation paths still enforce running-process guards.
- [ ] Backup paths are always created before mutation.
- [ ] External file operations remain scoped.

## 5. Current Known Gaps

These are already confirmed in the current repo/environment and must not be ignored.

- [ ] default `WindowsApps` `codex.exe` path is not a reliable execution target
- [ ] current `apply_patch` chain still depends on blocked Codex entrypoint
- [ ] `git` is not currently available in the active shell environment
- [ ] `codex-threadripper` is not currently available in the active shell environment
- [ ] the installer/runtime packaging strategy is not yet product-complete

## 6. Execution Order

Recommended implementation order:

1. runtime resolver
2. bundled / managed Codex CLI path
3. bundled / managed Python bridge runtime
4. required-vs-optional helper classification
5. first-run self-check screen
6. diagnostics bundle export
7. clean-machine acceptance run

## 7. Current Owner Files

Primary files involved in this checklist:

- `ai-strategist-desktop/src/components/login-repair/login-repair-page.tsx`
- `ai-strategist-desktop/src-tauri/src/commands/prelaunch.rs`
- `prelaunch_bridge.py`
- `prelaunch_manager.py`
- `repair_codex_desktop_history.py`
- `README.md`
- `HANDOFF.md`
- `EXECUTION_PLAN.md`
- `V0_1_RELEASE_CHECKLIST.md`

## 8. Definition of Done

AI Strategist can be considered productized for this workflow only when:

- a clean-user install can open and use the main workflow
- API / Hybrid launch no longer depends on stale local config luck
- the product controls its runtime paths
- missing optional tools degrade gracefully
- users do not need to understand shell PATH, WindowsApps, or developer environment setup to use the product
