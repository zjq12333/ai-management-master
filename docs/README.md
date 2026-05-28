# AI Strategist Documentation

This directory is the documentation map for the current AI Strategist project.

## Start Here

- [Project README](../README.md): current product positioning and daily development entry point.
- [Execution Plan](plans/EXECUTION_PLAN.md): active delivery plan for the `启动与修复` mainline and productization track.
- [Productization Checklist](plans/PRODUCTIZATION_CHECKLIST.md): gaps that must close before AI Strategist behaves like a download-and-run desktop product.
- [v0.1 Release Checklist](release/V0_1_RELEASE_CHECKLIST.md): release readiness checklist for the current milestone.

## Current Planning

- [Runtime Bundling Plan](plans/RUNTIME_BUNDLING_PLAN.md): bundled runtime and dependency strategy.
- [Enhancer MVP Plan](plans/enhancer/ENHANCER_MVP_PLAN.md): first controlled enhancer slice.
- [Enhancer Feature Matrix](plans/enhancer/ENHANCER_FEATURE_MATRIX.md): feature classification and sequencing.
- [Enhancer Architecture Options](plans/enhancer/ENHANCER_ARCHITECTURE_OPTIONS.md): architecture tradeoffs for enhancer work.

## Verification

Run the local verification suite from the repository root:

```powershell
.\Verify-AI-Strategist.ps1
```

Useful fast-path options:

```powershell
.\Verify-AI-Strategist.ps1 -SkipFrontendBuild
.\Verify-AI-Strategist.ps1 -SkipRust
```

## Archive

- [Historical handoffs](archive/handoffs/): previous project handoff files. These preserve context but should not override the current README or execution plan.
- [Legacy plans](archive/legacy/): deprecated or superseded plans kept for reference only.
- [Superpowers plans](superpowers/plans/): imported planning records from earlier workflow experiments.

## Documentation Rules

- Keep the repository root focused: `README.md`, launch scripts, and source files only.
- Put active plans under `docs/plans/`.
- Put release checklists under `docs/release/`.
- Move outdated handoffs and superseded plans into `docs/archive/` instead of leaving them in the root.
- When project direction changes, update this map and the root README together.
