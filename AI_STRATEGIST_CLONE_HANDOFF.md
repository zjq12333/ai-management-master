# AI Strategist Shell Handoff

## Purpose

`ai-strategist-desktop/` started as an open-source UI snapshot used to accelerate the desktop shell. It is no longer treated as a 1:1 clone target. The current product direction is **AI Strategist**, with **启动与修复** as the primary workflow page.

Path:

- `D:\我的空间\工作\pilot文件夹\AI管理大师文件夹\ai-strategist-desktop`

## Current Status (2026-05-22)

- Product name: `AI Strategist`.
- Package name: `ai-strategist`.
- Tauri identifier: `dev.ai.strategist`.
- Current shell uses a top feature navigation bar.
- There must be no left-side navigation in the product shell.
- The current main workflow is `启动与修复` / `loginRepair`.
- Other modules remain available for now but are not the current delivery focus.

## Historical Source Note

The shell originally used code from the Apache-2.0 `borawong/AI Strategist` source project as a UI starting point. That history is only useful for provenance and migration context. It should not drive current product copy, binary names, installer names, or user-facing docs.

Do not reintroduce the old product name into:

- app title
- package metadata
- Tauri config
- README copy
- installer output
- desktop shortcuts
- user-facing navigation labels

## Current UI Shape

- Header: app identity and top feature navigation.
- Main page area: active module content.
- Current priority page: `启动与修复`.
- Top nav entries currently include overview, launch/repair, custom instructions, MCP, Skills, maintenance, settings.
- The launch/repair page contains the three launch modes and repair action; these are functional modules moved into the current shell, not a wholesale migration of the old app.

## Current Packaging Note

The desktop build output is now expected to use `AI Strategist` naming:

- `AI Strategist.exe`
- `AI Strategist_1.0.0_x64-setup.exe`

A stale old desktop shortcut was found and removed:

- `?????????`

## Development Commands

From repo root:

```powershell
rtk pnpm --dir ai-strategist-desktop test
rtk pnpm --dir ai-strategist-desktop build
rtk cargo test --manifest-path ai-strategist-desktop/src-tauri/Cargo.toml
```

Python bridge:

```powershell
rtk python -m unittest tests.test_prelaunch_bridge -v
```

## Documentation Rule

If current product behavior changes, update:

- `README.md`
- `HANDOFF.md`
- `EXECUTION_PLAN.md`
- this file

Do not rely on old generated snapshots for product truth. If a repo snapshot is needed again, regenerate it from the current tree after the docs and branding are correct.
