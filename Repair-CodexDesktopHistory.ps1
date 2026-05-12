param(
    [string]$CodexHome = "$env:USERPROFILE\.codex",
    [string]$CurrentThreadId = $env:CODEX_THREAD_ID,
    [switch]$DryRun,
    [switch]$NoRestart,
    [switch]$SkipThreadripperInstall,
    [ValidateSet('current-only', 'all', 'none')]
    [string]$ProjectlessMode = 'current-only'
)

$ErrorActionPreference = 'Stop'

function Write-Step($Message) {
    Write-Host "==> $Message"
}

$ToolDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepairPy = Join-Path $ToolDir 'repair_codex_desktop_history.py'
$Stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$LogPath = Join-Path $ToolDir "repair-$Stamp.log"

$BundledPython = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
if (Test-Path -LiteralPath $BundledPython) {
    $Python = $BundledPython
} else {
    $Python = 'python'
}

$CodexExe = Get-ChildItem -LiteralPath 'C:\Program Files\WindowsApps' -Directory -Filter 'OpenAI.Codex_*' -ErrorAction SilentlyContinue |
    Sort-Object Name -Descending |
    ForEach-Object { Join-Path $_.FullName 'app\Codex.exe' } |
    Where-Object { Test-Path -LiteralPath $_ } |
    Select-Object -First 1

Write-Step "Codex home: $CodexHome"
Write-Step "Log: $LogPath"

if (-not (Test-Path -LiteralPath $RepairPy)) {
    throw "Missing repair script: $RepairPy"
}

if ((-not $DryRun) -and (-not $SkipThreadripperInstall)) {
    $existing = Get-Command codex-threadripper -ErrorAction SilentlyContinue
    if (-not $existing) {
        Write-Step "Installing codex-threadripper with npm"
        npm i -g codex-threadripper | Tee-Object -FilePath $LogPath -Append
    }
}

if ($DryRun) {
    if (Get-Command codex-threadripper -ErrorAction SilentlyContinue) {
        Write-Step "Running codex-threadripper status"
        codex-threadripper --codex-home $CodexHome status | Tee-Object -FilePath $LogPath -Append
    } else {
        Write-Step "codex-threadripper not found; skipping provider status"
    }
    Write-Step "Running dry run"
    & $Python -X utf8 $RepairPy --codex-home $CodexHome --current-thread-id $CurrentThreadId --projectless-mode $ProjectlessMode --dry-run | Tee-Object -FilePath $LogPath -Append
    exit $LASTEXITCODE
}

if (Get-Command codex-threadripper -ErrorAction SilentlyContinue) {
    Write-Step "Running codex-threadripper sync"
    codex-threadripper --codex-home $CodexHome sync | Tee-Object -FilePath $LogPath -Append
} else {
    Write-Step "codex-threadripper not found; skipping provider reconciliation"
}

Write-Step "Closing Codex Desktop before state repair"
Get-Process -Name Codex,codex -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 3

$GlobalState = Join-Path $CodexHome '.codex-global-state.json'
$StateDb = Join-Path $CodexHome 'state_5.sqlite'
$BackupGlobalState = Join-Path $CodexHome ".codex-global-state.json.backup_desktop_repair_$Stamp"
$BackupStateDb = Join-Path $CodexHome "state_5.sqlite.backup_desktop_repair_$Stamp"

Write-Step "Creating backups"
Copy-Item -LiteralPath $GlobalState -Destination $BackupGlobalState -Force
Copy-Item -LiteralPath $StateDb -Destination $BackupStateDb -Force

Write-Step "Repairing Desktop history placement"
& $Python -X utf8 $RepairPy --codex-home $CodexHome --current-thread-id $CurrentThreadId --projectless-mode $ProjectlessMode | Tee-Object -FilePath $LogPath -Append
if ($LASTEXITCODE -ne 0) {
    throw "Repair script failed with exit code $LASTEXITCODE"
}

Write-Step "Backups written:"
Write-Host "  $BackupGlobalState"
Write-Host "  $BackupStateDb"

if (-not $NoRestart) {
    if ($CodexExe) {
        Write-Step "Restarting Codex Desktop"
        Start-Process -FilePath $CodexExe
    } else {
        Write-Step "Codex.exe not found automatically; open Codex Desktop manually"
    }
}

Write-Step "Done"
