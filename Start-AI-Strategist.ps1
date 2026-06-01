param(
    [string]$RepoRoot = $PSScriptRoot
)

$ErrorActionPreference = "Stop"

$resolvedRoot = (Resolve-Path -LiteralPath $RepoRoot).ProviderPath
$primaryExe = Join-Path $resolvedRoot "ai-strategist-desktop\src-tauri\target\release\AI-Strategist.exe"
$fallbackManagerExe = Join-Path $resolvedRoot "third_party\codex-plus-plus\target\release\codex-plus-plus-manager.exe"
$logDir = Join-Path $env:LOCALAPPDATA "AI-Strategist\logs"
$logPath = Join-Path $logDir "launcher.log"
$stdoutPath = Join-Path $logDir "ai-strategist.stdout.log"
$stderrPath = Join-Path $logDir "ai-strategist.stderr.log"

New-Item -ItemType Directory -Force -Path $logDir | Out-Null

function Write-LaunchLog {
    param([string]$Message)
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -LiteralPath $logPath -Encoding UTF8 -Value "[$timestamp] $Message"
}

function Format-Window {
    param($Window)
    if ($null -eq $Window) {
        return "<none>"
    }
    return "Handle=$($Window.Handle) Title='$($Window.Title)' Class='$($Window.ClassName)'"
}

Write-LaunchLog "Launch requested. RepoRoot=$resolvedRoot"

Add-Type @'
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;

public class AiStrategistWindow {
  public delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);
  [DllImport("user32.dll")] public static extern bool EnumWindows(EnumWindowsProc lpEnumFunc, IntPtr lParam);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern bool IsIconic(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT rect);
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint processId);

  [StructLayout(LayoutKind.Sequential)]
  public struct RECT {
    public int Left;
    public int Top;
    public int Right;
    public int Bottom;
  }
}
'@

function Get-ProcessWindows($process) {
    $windows = New-Object System.Collections.Generic.List[object]
    if ($null -eq $process) {
        return $windows
    }

    $callback = [AiStrategistWindow+EnumWindowsProc]{
        param([IntPtr]$handle, [IntPtr]$param)
        [uint32]$ownerProcessId = 0
        [void][AiStrategistWindow]::GetWindowThreadProcessId($handle, [ref]$ownerProcessId)
        if ($ownerProcessId -eq $process.Id) {
            $rect = New-Object AiStrategistWindow+RECT
            [void][AiStrategistWindow]::GetWindowRect($handle, [ref]$rect)
            $windows.Add([pscustomobject]@{
                Handle = $handle
                Visible = [AiStrategistWindow]::IsWindowVisible($handle)
                Minimized = [AiStrategistWindow]::IsIconic($handle)
                Width = $rect.Right - $rect.Left
                Height = $rect.Bottom - $rect.Top
            })
        }
        return $true
    }

    [void][AiStrategistWindow]::EnumWindows($callback, [IntPtr]::Zero)
    return $windows
}

function Get-BestWindow($process) {
    @(Get-ProcessWindows $process) |
        Where-Object { $_.Width -ge 320 -and $_.Height -ge 240 } |
        Sort-Object @{ Expression = { $_.Width * $_.Height }; Descending = $true } |
        Select-Object -First 1
}

function Show-Window($window) {
    if ($null -eq $window) {
        return
    }
    [void][AiStrategistWindow]::ShowWindow($window.Handle, 9)
    [void][AiStrategistWindow]::SetForegroundWindow($window.Handle)
}

$existing = @(Get-Process -Name "AI-Strategist" -ErrorAction SilentlyContinue)
foreach ($process in $existing) {
    $window = Get-BestWindow $process
    if ($null -ne $window) {
        Write-LaunchLog "Found existing window. PID=$($process.Id) Window=$(Format-Window $window)"
        Show-Window $window
        exit 0
    }

    Write-LaunchLog "Existing AI Strategist process has no visible window. PID=$($process.Id); preserving it and starting a fresh instance."
}

if (Test-Path -LiteralPath $primaryExe) {
    Write-LaunchLog "Starting primary executable: $primaryExe"
    Remove-Item -LiteralPath $stdoutPath, $stderrPath -Force -ErrorAction SilentlyContinue
    $started = Start-Process -FilePath $primaryExe -WorkingDirectory $resolvedRoot -PassThru -RedirectStandardOutput $stdoutPath -RedirectStandardError $stderrPath
    Start-Sleep -Seconds 2
    $started.Refresh()
    Write-LaunchLog "Primary executable started. PID=$($started.Id) HasExited=$($started.HasExited)"
    $window = Get-BestWindow $started
    if ($null -ne $window) {
        Write-LaunchLog "Found started window. PID=$($started.Id) Window=$(Format-Window $window)"
        Show-Window $window
        Start-Sleep -Seconds 3
        $started.Refresh()
        $exitCode = if ($started.HasExited) { $started.ExitCode } else { "<running>" }
        Write-LaunchLog "Post-window health. PID=$($started.Id) HasExited=$($started.HasExited) ExitCode=$exitCode"
    } else {
        $exitCode = if ($started.HasExited) { $started.ExitCode } else { "<running>" }
        Write-LaunchLog "Started process has no visible main window yet. PID=$($started.Id) HasExited=$($started.HasExited) ExitCode=$exitCode"
        if (Test-Path -LiteralPath $stderrPath) {
            $stderrTail = (Get-Content -LiteralPath $stderrPath -Tail 20 -ErrorAction SilentlyContinue) -join " | "
            if (-not [string]::IsNullOrWhiteSpace($stderrTail)) {
                Write-LaunchLog "stderr tail: $stderrTail"
            }
        }
    }
    exit 0
}

if (Test-Path -LiteralPath $fallbackManagerExe) {
    Write-LaunchLog "Primary executable missing. Starting fallback manager: $fallbackManagerExe"
    Start-Process -FilePath $fallbackManagerExe -WorkingDirectory $resolvedRoot
    exit 0
}

Write-LaunchLog "No executable found. Primary=$primaryExe Fallback=$fallbackManagerExe"
throw "AI Strategist executable was not found. Expected: $primaryExe"
