# AI Strategist Execution Plan

## Objective

Ship **AI Strategist** as a reliable Codex Desktop launch-and-repair application that can evolve into a **download-and-run desktop product** rather than a development-machine-only tool.

The active release target has two tracks:

1. `启动与修复` workflow remains stable and evidence-first.
2. Productization gaps are closed so the app does not depend on a lucky local environment.

## Scope for This Phase

In scope:

- top feature navigation with no left-side navigation
- `启动与修复` page as the main workflow
- three launch modes:
  - official account
  - API provider / relay
  - hybrid plugins + relay
- explicit provider input for API / hybrid launch
- prelaunch state inspection
- provider-bucket diagnostics
- manual repair action
- launch orchestration
- evidence-first result display and report files
- packaging as `AI Strategist`
- runtime / toolchain productization planning and document sync

Out of scope for the current phase:

- redesigning every retained module
- removing MCP/Skills/custom-instruction modules
- building a new session tree experience
- changing security-sensitive login/provider behavior as part of documentation cleanup
- full installer bundling implementation in the same pass as UI cleanup

## Product / UI Constraints

- Left side must remain empty of navigation and task entries.
- Main modules are placed in the top navigation.
- `启动与修复` is the only current priority workflow.
- Retained modules are allowed to stay, but should not distract from the launch/repair flow.
- Do not move the old app wholesale into this shell; only transfer the required launch/repair function modules.

## Current Implementation State

Completed:

- Tauri product metadata renamed to `AI Strategist`.
- package name renamed to `ai-strategist`.
- Tauri identifier set to `dev.ai.strategist`.
- app shell uses `TopFeatureNav` in the header.
- `loginRepair` route/page is the launch-and-repair page.
- three launch modes are available on that page.
- repair action is available on that page.
- API / hybrid launch now requires explicit provider input and no longer silently reuses stale config.
- Codex running-state guard is present before launch/repair actions.
- desktop build artifacts exist with `AI Strategist` naming.
- stale old desktop shortcut was removed.

Important implementation notes:

- `ai-strategist-desktop/src/components/layout/sidebar.tsx` is a historical filename. It currently exports `TopFeatureNav` and is used as a top navigation component, not a left sidebar.
- Default `WindowsApps` Codex CLI entrypoint is not reliable in this environment; local shim/workaround exists, but installer-grade runtime resolution is still pending.

## Phase Breakdown

### Phase 1: Launch / Repair Stability

Status: active and mostly completed for the current slice.

Deliverables:

- keep official / API / hybrid / repair flows in the current `启动与修复` page
- require explicit provider input for API / hybrid launch
- block runtime changes while Codex Desktop / codex CLI is still running
- preserve evidence-first reports under `reports/`

### Phase 2: Verification

Status: active.

Required commands:

```powershell
pnpm --dir ai-strategist-desktop test prelaunch-page
pnpm --dir ai-strategist-desktop build
python -m unittest tests.test_prelaunch_bridge -v
cargo test --manifest-path ai-strategist-desktop/src-tauri/Cargo.toml prelaunch
```

Manual checks:

- Open `AI Strategist.exe`.
- Confirm top nav is visible and left side has no navigation.
- Open `启动与修复`.
- Confirm official/API/hybrid launch modules are visible.
- Confirm provider input section is visible.
- Confirm repair action is visible.
- Confirm other modules remain available but are not the primary workflow.

### Phase 3: Productization Baseline

Status: active and newly introduced.

Deliverables:

- define which runtimes and helper tools must be bundled
- stop relying on `WindowsApps` default `codex.exe`
- stop relying on user `PATH` for mainline features
- define startup self-check and auto-repair behavior
- classify helper tools into required vs optional / degraded

Primary reference:

- `docs/plans/PRODUCTIZATION_CHECKLIST.md`

### Phase 4: Installer / Runtime Integration

Status: pending.

Target outcomes:

- internal runtime resolver for `codex`, Python, and helper binaries
- bundled or internally provisioned runtime for the Python bridge
- stable internal tool invocation without shell PATH assumptions
- first-run diagnostics and repair flow

### Phase 5: Clean-Machine Acceptance

Status: pending.

Target outcomes:

- verify install and first run on a clean Windows machine
- no requirement for preinstalled Python / Node / Git / Rust
- explicit downgrade behavior for optional tooling
- evidence bundle export for failure cases

## File Ownership

- `ai-strategist-desktop/src/main-app.tsx`
  - app layout and route mounting
- `ai-strategist-desktop/src/components/layout/sidebar.tsx`
  - top feature navigation despite historical filename
- `ai-strategist-desktop/src/components/login-repair/login-repair-page.tsx`
  - `启动与修复` workflow page
- `ai-strategist-desktop/src-tauri/src/commands/prelaunch.rs`
  - Tauri command bridge
- `prelaunch_bridge.py`
  - Python bridge CLI
- `prelaunch_manager.py`
  - provider configuration and evidence helpers
- `repair_codex_desktop_history.py`
  - chat/history repair behavior
- `README.md`
  - user-facing current behavior
- `docs/README.md`
  - documentation tree and source-of-truth map
- `docs/plans/PRODUCTIZATION_CHECKLIST.md`
  - productization execution checklist

## Documentation Cleanup Rule

Generated snapshots are not source of truth. If `ai-strategist-desktop/repomix.md` exists and contains stale old product names, delete it or regenerate it after current branding/docs are correct.
