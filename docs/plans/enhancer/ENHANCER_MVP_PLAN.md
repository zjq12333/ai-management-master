# AI Strategist Enhancer MVP Plan

Updated: 2026-05-25

## Goal

Ship the first enhancer slice without derailing the existing `启动与修复` mainline.

This MVP should prove that AI Strategist can add high-value local Codex capabilities while preserving:

- workspace/session-first ownership logic
- backup-first mutation safety
- productization discipline

## MVP Scope

In scope for enhancer MVP:

1. Session workspace reassignment

Out of scope for this MVP:

- provider-sync style ownership rewriting
- Codex window hover controls
- timeline UI inside the Codex renderer
- plugin unlock / forced plugin install
- full CDP injection platform
- batch multi-session operations

## MVP Product Shape

The enhancer MVP should appear as a controlled module inside AI Strategist, not as a new launcher replacement.

Recommended product shape:

- keep `启动与修复` as the first-class default page
- add a separate top-nav module such as `增强器`
- inside that module, expose one focused action:
  - workspace 调整

The UI should stay operator-style and explicit:

- select a session
- inspect preview
- execute one action
- see backup/report/result

## User Flows

### Flow A: Workspace reassignment

1. User selects a conversation.
2. App shows current workspace and target workspace.
3. User enters or picks the target workspace path.
4. App validates the path and previews changes.
5. App checks that Codex is not running.
6. App creates backup.
7. App updates:
   - `threads.cwd`
   - rollout `session_meta.cwd`
8. App writes a mutation report.

## Technical Direction

## Recommended route

Use a desktop-owned backend route first:

- React/Tauri UI
- Rust commands as the stable boundary
- Python implementation for fast delivery against the already-working local data layer

This route matches the current repo best because:

- `prelaunch.rs` already wraps Python commands
- `prelaunch_bridge.py` already handles report bundles and process guards
- `repair_codex_desktop_history.py` already knows the same SQLite/state files
- the productization work already assumes product-controlled runtime invocation

## Suggested backend split

Recommended structure:

- keep prelaunch/repair commands separate
- add a new enhancer backend boundary rather than overloading prelaunch semantics

Suggested command families:

- `enhancer_list_sessions`
- `enhancer_move_session_workspace`
- `enhancer_preview_move_session_workspace`

Suggested implementation organization:

- Tauri Rust command layer
- one Python bridge for enhancer actions, or a shared bridge with subcommands
- a focused Python module for local session operations

## Reuse Opportunities

Existing repo capabilities to reuse:

- runtime resolution in `prelaunch.rs`
- running-process guard in current prelaunch flow
- report directory generation pattern in `prelaunch_bridge.py`
- backup discipline and thread attribution logic in `repair_codex_desktop_history.py`

External reference worth adapting from Codex++:

- workspace move handling for `threads.cwd` plus rollout metadata

## Safety Requirements

These are MVP requirements, not optional polish.

### For workspace reassignment

- mandatory backup before mutation
- no mutation while Codex is running
- validate target path shape
- report old and new workspace values
- keep change scoped to selected session metadata only

## MVP Deliverables

### Product

- enhancer module available in top nav
- single-session operation for workspace reassignment
- recent result panel
- clear degraded/unavailable states

### Engineering

- Rust command surface for enhancer operations
- Python implementation with tests
- mutation reports under product-managed reports directory
- shared process-guard behavior

### Verification

- unit tests for workspace metadata rewrite
- manual check against a real local Codex home copy

## Sequencing

Recommended implementation order:

1. session listing + preview support
2. workspace reassignment preview + mutate
3. enhancer UI integration

This order gives the fastest path to visible value while de-risking destructive actions.

## Go / No-Go Decision

The enhancer MVP is worth starting now because it does not require AI Strategist to solve injection first.

The right technical bet is:

- `Go` on desktop-owned local-data enhancer MVP
- `No-go for now` on making CDP injection the foundation of phase one
