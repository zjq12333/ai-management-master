# v0.1 Release Checklist (AI Strategist)

Goal of v0.1: ship a closed-source, end-user installable **AI Strategist** build whose primary page, **启动与修复**, reliably runs the three launch modes on a real machine with evidence-first diagnostics and safe rollback.

Important constraint for this checklist:

> Passing on the current developer machine is not enough. Release readiness requires explicit environment-independence review and clean-machine acceptance planning.

Installed-build smoke check:

```powershell
.\Test-AI-StrategistInstall.ps1 -InstallDir "C:\Program Files\AI Strategist"
```

Use `-SkipAppExe` only for staged resource smoke checks; release acceptance should verify the installed app executable too.

Current evidence:

- ✅ Release NSIS installer can install to a temporary directory on the developer machine.
- ✅ `Test-AI-StrategistInstall.ps1` passes against that installed directory.
- ✅ Silent uninstall exits successfully and removes the temporary install directory.
- ❌ Clean-machine or VM acceptance pass is still pending.

Release gates: every item below must be either ✅ Done or explicitly marked ❌ Deferred (with rationale) before publishing binaries.

## 1) Product Scope Lock

- ✅ The app’s identity is **AI Strategist**.
- ✅ The primary workflow page is **启动与修复**.
- ✅ Navigation is placed at the top; there must be no left-side navigation/task rail.
- ✅ The UI keeps the current modules available, but v0.1 focuses on launch and repair.
- ✅ The launch/repair page contains 4 action modules:
  - Official account launch
  - API provider launch
  - Hybrid launch (plugins + relay)
  - Repair
- ✅ API / Hybrid launch now requires explicit provider input; do not silently reuse stale provider config.
- ✅ All destructive actions have hard safety boundaries (see section 4).

## 2) Mode Matrix (Real-Machine Acceptance)

For each run, capture the following evidence in the UI log and persist to a timestamped file:

- `auth_mode` (from `auth.json`)
- `config.toml` current `model_provider`
- threadripper status: `Target provider`, `Rows needing reconcile`
- `state_5.sqlite` provider distribution (threads table)
- launch method (exe/AppID)
- outcome: chats visible + plugin availability behavior

Acceptance: each mode is reproducible **3 times in a row** with the same evidence pattern.

### 2.1 Official Mode

- ✅ Preconditions: Codex Desktop is signed in with official account (chatgpt auth state).
- ✅ Expected: plugins available; model channel is official provider.
- ✅ Expected: chats visible.

### 2.2 API Mode (Relay / Third-party)

- ✅ Preconditions: provider config is filled (base_url, wire_api, env_key or requires_openai_auth).
- ✅ Expected: model requests go through the configured provider.
- ✅ Expected: chats visible under the provider bucket (or a clear explanation if not possible).
- ✅ Expected: plugin behavior is documented (usually unavailable under apikey auth).

### 2.3 Hybrid Mode (Plugins + Relay)

- ✅ Preconditions: official sign-in state exists AND relay token is configured.
- ✅ Expected: plugins available AND model requests go through relay provider.
- ✅ Expected: thread provider distribution aligns with the relay provider (or auto-reconcile succeeds).

## 3) Rollback / Backup Guarantees

- ✅ Every operation that mutates any of:
  - `config.toml`
  - `state_5.sqlite` (+ wal/shm)
  - `.codex-global-state.json`
  - `session_index.jsonl`
  must create a timestamped backup first.
- ✅ The UI must print the backup directory path after each mutation.
- ✅ A “manual rollback” instruction exists in README (path + what to restore).

## 4) Safety Boundaries (Hard Gates)

### 4.1 Process Gate

- ✅ Any action that mutates `state_5.sqlite` or `.codex-global-state.json` must **block** if:
  - `Codex.exe` is running, or
  - `codex.exe` is running

### 4.2 Destructive Confirmation Gate

- ✅ Any destructive deletion must require:
  - dry-run / preview (count + samples)
  - explicit confirmation dialog
  - confirmation token input (e.g. typing `DELETE`)

### 4.3 Scope Gate

- ✅ “Dirty data cleanup” must only touch tool-generated artifacts under:
  - `desktop_history_repair_backups/`
- ✅ No feature may delete or modify files outside Codex home unless explicitly documented and confirmed.

## 5) Logging & Evidence Persistence

- ✅ UI log contains the minimum evidence items for every launch flow.
- ✅ Persist a JSON report per run to a local folder (e.g. `logs/` or `reports/` under this repo or Codex home), with:
  - timestamp
  - mode
  - evidence snapshot
  - user-visible outcome
  - backup paths (if any)
- ✅ Provide “Copy diagnosis bundle” behavior (zip is optional; a folder is acceptable for v0.1).

## 6) Packaging (Closed Source)

- ✅ Source repo remains private.
- ✅ Public distribution is **binary only** (installer/zip) plus usage docs.
- ✅ Build artifacts are versioned (semver or date-based).
- ❌ The binary is not yet fully environment-independent.
  - Reason: runtime resolution, bundled Python bridge strategy, and helper-tool bundling are still being productized.
- ✅ Expected artifact names for this slice:
  - `AI Strategist.exe`
  - `AI Strategist_1.0.0_x64-setup.exe`

## 7) Documentation

- ✅ `README.md` describes AI Strategist and the `启动与修复` workflow.
- ✅ `docs/README.md` maps the active docs tree and archived references.
- ✅ Historical handoff files live under `docs/archive/handoffs/` and must not define current branding.
- ✅ `docs/plans/EXECUTION_PLAN.md` references the current execution tracks and stays up-to-date.
- ✅ `docs/plans/PRODUCTIZATION_CHECKLIST.md` exists and defines required runtime/self-check work before claiming general delivery.
- ✅ A short operator guide exists in README/docs form:
  - how to run each mode
  - what success looks like
  - what evidence to check when it fails

## 8) Environment Independence Review

These items must be explicitly reviewed even if they are deferred from v0.1:

- ❌ Mainline workflows no longer depend on `WindowsApps` default `codex.exe`.
- ❌ Mainline workflows no longer depend on user PATH luck.
- ❌ Mainline workflows no longer require preinstalled Python / Git / helper tools.
- ❌ Clean-machine install acceptance has been completed.

## 9) Deferred Items (Must Be Explicit)

Deferred from v0.1:

- Session/folder tree redesign.
  - Reason: high iteration risk; keep focus on launch and repair.
- Full redesign or deletion of retained non-core modules.
  - Reason: current instruction is to keep them temporarily and evaluate later.
- API/LAC live switching follow-up.
  - Reason: touches live runtime/config state and should be handled separately from documentation sync.
- Full runtime bundling / environment independence completion.
  - Reason: requires a dedicated productization track beyond current shell stabilization.
