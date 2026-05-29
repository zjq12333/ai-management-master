# Runtime Bundling Plan

## Goal

Create a product-controlled runtime resolution layer so AI Strategist no longer depends on user PATH luck or `WindowsApps` shell execution behavior.

## Current Problem

The current project still has scattered runtime assumptions:

- some logic relies on bare command names
- some logic relies on `WindowsApps`-backed executables
- Python bridge script resources are now bundled, but the Python executable itself still needs a product-owned distribution path
- helper-tool discovery is not classified into required vs optional

## Phase 1 Scope

This phase does not bundle everything yet. It establishes the structure that bundling will use.

Deliverables:

1. shared runtime resolver module under `src-tauri/src/platform/`
2. product-managed resolution order for Python bridge runtime
3. product-managed resolution order for Codex CLI path
4. typed helper result for optional helper tools like threadripper
5. command modules start consuming the shared resolver instead of local ad-hoc logic

## Resolution Order

### Python bridge runtime

1. explicit `AI_STRATEGIST_PYTHON` override for diagnostics and managed installs
2. bundled runtime path beside the app executable or under Tauri resources
3. product-managed local runtime under user profile / app data
4. fallback `python`

### Codex CLI runtime

1. product-managed local runtime / shim path
2. product-managed bundled runtime path
3. product-managed local OpenAI cache path
4. last-resort system discovery with explicit warning

### Optional helper tools

1. bundled helper path
2. product-managed local helper path
3. PATH lookup
4. unavailable state with graceful downgrade

## Target Module

Created:

- `ai-strategist-desktop/src-tauri/src/platform/runtime_resolver.rs`

Responsibilities:

- resolve Python executable path
- resolve Codex executable path
- resolve optional helper binaries
- expose diagnostics-friendly metadata about where the runtime came from

## First Consumers

The first migration target is:

- `ai-strategist-desktop/src-tauri/src/commands/prelaunch.rs`

## Current Status

- The shared resolver exists and is used by the prelaunch bridge command.
- `prelaunch_bridge.py` and its local Python modules are included in Tauri `bundle.resources`.
- The selected Python bridge delivery direction is a self-contained `prelaunch_bridge.exe` built into `ai-strategist-desktop/src-tauri/resources/prelaunch/`.
- `Build-PrelaunchBridge.ps1` builds that executable with PyInstaller when PyInstaller is installed in the active Python environment.
- Runtime lookup now supports explicit environment override, common Tauri bundled-resource layouts, product-managed local directories, and PATH fallback.
- The actual `prelaunch_bridge.exe` artifact is produced and committed under the Tauri prelaunch resources directory.
- Still pending: verify the bundled bridge in a clean-machine install flow.

Reason:

- it already embeds local Python discovery logic
- it currently pays the highest cost for runtime path inconsistency
- it is part of the mainline `启动与修复` workflow

## Next Consumers

After the prelaunch bridge is migrated:

- `ai-strategist-desktop/src-tauri/src/platform/process.rs`
- system-level commands that need Codex app / CLI path awareness
- diagnostics export code

## Acceptance

Phase 1 is complete when:

- prelaunch bridge command no longer owns its own Python lookup logic
- runtime resolution lives under the shared platform layer
- the source of the resolved runtime can be explained in diagnostics
- existing prelaunch tests still pass
