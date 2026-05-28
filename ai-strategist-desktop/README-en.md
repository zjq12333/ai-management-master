<p align="center">
  <img src="assets/app-icon.png" alt="AI Strategist" width="128" height="128" />
</p>

<h1 align="center">AI Strategist Desktop</h1>

<p align="center">
  A local Codex Desktop launch-and-repair shell. The current mainline is <b>Launch & Repair</b>, not the earlier account-rotation or session-tree product direction.
</p>

<p align="center">
  <b>English</b> | <a href="README.md">简体中文</a>
</p>

## Current Positioning

`ai-strategist-desktop/` is the Tauri frontend for AI Strategist. It brings local Codex Desktop launch, preflight checks, repair actions, and evidence into one stable desktop interface.

Current mainline goals:

- Keep the `Launch & Repair` workflow stable.
- Support official-account, API-channel, and hybrid launch paths.
- Show provider, chat bucket, plugin, and running-process evidence before launch.
- Productize the Python bridge and Tauri command bridge so the app depends less on the developer machine being configured perfectly.

Not active mainline scope:

- Multi-account rotation.
- Session tree management.
- Smart model routing.
- A broad Codex management console.

Those ideas can remain historical context or future candidates, but they must not override the current `Launch & Repair` mainline.

## Common Commands

```powershell
pnpm --dir ai-strategist-desktop dev
pnpm --dir ai-strategist-desktop build
pnpm --dir ai-strategist-desktop test
pnpm --dir ai-strategist-desktop tauri dev
```

Tauri/Rust tests:

```powershell
cargo test --manifest-path ai-strategist-desktop/src-tauri/Cargo.toml
```

Python bridge tests from the repository root:

```powershell
python -m pytest
```

## Key Directories

- `src/main-app.tsx`: current desktop app mount.
- `src/components/login-repair/`: `Launch & Repair` page.
- `src/components/enhancer/`: handoff and enhancer frontend helpers.
- `src-tauri/src/commands/`: Tauri command bridge.
- `src-tauri/resources/`: desktop runtime resources.

## Documentation

- Root project README: `../README.md`
- Documentation map: `../docs/README.md`
- Active execution plan: `../docs/plans/EXECUTION_PLAN.md`
- Productization checklist: `../docs/plans/PRODUCTIZATION_CHECKLIST.md`
- Release checklist: `../docs/release/V0_1_RELEASE_CHECKLIST.md`
