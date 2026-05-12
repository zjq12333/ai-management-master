# Codex Desktop History Repair

One-click local repair tool for Codex Desktop history visibility.

It combines two fixes:

1. `codex-threadripper sync` aligns all Codex threads into the active `model_provider` bucket.
2. The desktop repair step updates Codex Desktop state so conversations show in the app and return to their original workspace positions.

## Files

- `Repair-CodexDesktopHistory.ps1` - main PowerShell launcher.
- `repair_codex_desktop_history.py` - SQLite and Desktop-state repair core.

## Normal Use

Open PowerShell and run:

```powershell
cd path\to\codex-desktop-history-repair
.\Repair-CodexDesktopHistory.ps1
```

The script will:

- install `codex-threadripper` with npm if it is missing;
- run `codex-threadripper --codex-home <home> sync`;
- close Codex Desktop;
- back up `state_5.sqlite` and `.codex-global-state.json`;
- unarchive hidden threads;
- restore each thread's original workspace hint from `state_5.sqlite`;
- restart Codex Desktop.

## Dry Run

Use this first when you only want to inspect what would be repaired:

```powershell
.\Repair-CodexDesktopHistory.ps1 -DryRun
```

Dry run does not close Codex and does not write files.

## Useful Options

```powershell
.\Repair-CodexDesktopHistory.ps1 -NoRestart
```

Repair but leave Codex Desktop closed.

```powershell
.\Repair-CodexDesktopHistory.ps1 -SkipThreadripperInstall
```

Do not attempt npm installation; use an existing `codex-threadripper` if present.

```powershell
.\Repair-CodexDesktopHistory.ps1 -ProjectlessMode current-only
```

Keep only the current repair thread in the projectless bucket. This is the default and usually keeps restored conversations in their original workspace groups.

## Backups

Every real repair writes timestamped backups in:

```text
%USERPROFILE%\.codex
```

Backup names look like:

```text
.codex-global-state.json.backup_desktop_repair_YYYYMMDD-HHMMSS
state_5.sqlite.backup_desktop_repair_YYYYMMDD-HHMMSS
```

## Notes

- Run this while you are okay with Codex Desktop being restarted.
- If the app is open, the script closes it before editing state files. This matters because Codex Desktop can overwrite `.codex-global-state.json` from memory while it is running.
- The tool does not delete conversations or rollout files.
