param(
    [string]$CodexHome = "$env:USERPROFILE\.codex",
    [string]$CurrentThreadId = $env:CODEX_THREAD_ID,
    [string]$HistoryRoot = "$([Environment]::GetFolderPath('MyDocuments'))\Codex",
    [switch]$DryRun,
    [switch]$IncludeArchived,
    [switch]$ExcludeArchived,
    [switch]$AllowMissingCwd,
    [switch]$AllowEmptyCwd,
    [switch]$AllowMissingSession,
    [switch]$UnarchiveSelected,
    [switch]$SyncProvider,
    [switch]$NoProviderSync,
    [switch]$InstallThreadripper,
    [switch]$SkipThreadripperInstall,
    [switch]$NoRestart,
    [switch]$LegacyCwdFiltering,
    [ValidateSet('current-only', 'all', 'none')]
    [string]$ProjectlessMode = 'none'
)

$ErrorActionPreference = 'Stop'
$OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

function Write-Step($Message) {
    Write-Host "==> $Message"
}

function Find-Python {
    $bundledPython = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
    if (Test-Path -LiteralPath $bundledPython) {
        return $bundledPython
    }
    return 'python'
}

function Get-ThreadripperCommand {
    return Get-Command codex-threadripper -ErrorAction SilentlyContinue
}

function Ensure-Threadripper {
    $existing = Get-ThreadripperCommand
    if ($existing) {
        return $true
    }

    if (-not $InstallThreadripper) {
        Write-Step "codex-threadripper not found; provider sync skipped. Use -InstallThreadripper to install it."
        return $false
    }

    Write-Step "Installing codex-threadripper with npm"
    npm i -g codex-threadripper | Tee-Object -FilePath $LogPath -Append
    return [bool](Get-ThreadripperCommand)
}

$ToolDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepairPy = Join-Path $ToolDir 'repair_codex_desktop_history.py'
$Stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$LogPath = Join-Path $ToolDir "repair-$Stamp.log"
$Python = Find-Python

Write-Step "Codex home: $CodexHome"
Write-Step "Log: $LogPath"

if (-not (Test-Path -LiteralPath $RepairPy)) {
    throw "Missing repair script: $RepairPy"
}

$RepairArgs = @(
    '-X', 'utf8',
    $RepairPy,
    '--codex-home', $CodexHome,
    '--history-root', $HistoryRoot,
    '--projectless-mode', $ProjectlessMode
)

if ($CurrentThreadId) {
    $RepairArgs += @('--current-thread-id', $CurrentThreadId)
}
if ($DryRun) {
    $RepairArgs += '--dry-run'
}
if ($IncludeArchived -or (-not $ExcludeArchived)) {
    $RepairArgs += '--include-archived'
}
if ($AllowMissingCwd -or (-not $LegacyCwdFiltering)) {
    $RepairArgs += '--allow-missing-cwd'
}
if ($AllowEmptyCwd -or (-not $LegacyCwdFiltering)) {
    $RepairArgs += '--allow-empty-cwd'
}
if ($AllowMissingSession) {
    $RepairArgs += '--allow-missing-session'
}
if ($UnarchiveSelected -or (-not $ExcludeArchived)) {
    $RepairArgs += '--unarchive-selected'
}

if ($DryRun) {
    if ((-not $NoProviderSync) -and (Get-ThreadripperCommand)) {
        Write-Step "Running codex-threadripper status"
        codex-threadripper --codex-home $CodexHome status | Tee-Object -FilePath $LogPath -Append
    } else {
        Write-Step "Provider status skipped"
    }

    Write-Step "Running dry run"
    & $Python @RepairArgs | Tee-Object -FilePath $LogPath -Append
    exit $LASTEXITCODE
}

if ($SyncProvider -and (-not $NoProviderSync)) {
    if (Ensure-Threadripper) {
        Write-Step "Running codex-threadripper sync"
        codex-threadripper --codex-home $CodexHome sync | Tee-Object -FilePath $LogPath -Append
    }
} else {
    Write-Step "Provider sync skipped. Use -SyncProvider to reconcile model provider buckets."
}

Write-Step "Repairing Desktop history placement"
Write-Step "Close Codex Desktop first if it is currently open, then press Enter to continue."
[void](Read-Host)

& $Python @RepairArgs | Tee-Object -FilePath $LogPath -Append
if ($LASTEXITCODE -ne 0) {
    throw "Repair script failed with exit code $LASTEXITCODE"
}

Write-Step "Done. Restart Codex Desktop manually to load the repaired state."
