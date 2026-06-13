param(
    [string]$RepoRoot = $PSScriptRoot
)

$ErrorActionPreference = "Stop"

$resolvedRoot = (Resolve-Path -LiteralPath $RepoRoot).ProviderPath
$primaryExe = Join-Path $resolvedRoot "ai-strategist-desktop\src-tauri\target\release\AI-Strategist.exe"
$debugExe = Join-Path $resolvedRoot "ai-strategist-desktop\src-tauri\target\debug\AI-Strategist.exe"
$prelaunchBridgeScript = Join-Path $resolvedRoot "prelaunch_bridge.py"
$pythonRuntime = Join-Path $resolvedRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $pythonRuntime)) {
    $pythonRuntime = "D:\Tools\Python312\python.exe"
}
$pythonRuntimeDir = Split-Path -Parent $pythonRuntime
$logDir = Join-Path $env:LOCALAPPDATA "AI-Strategist\logs"
$logPath = Join-Path $logDir "launcher.log"
$stdoutPath = Join-Path $logDir "ai-strategist.stdout.log"
$stderrPath = Join-Path $logDir "ai-strategist.stderr.log"

New-Item -ItemType Directory -Force -Path $logDir | Out-Null

$env:AI_STRATEGIST_PYTHON_RUNTIME = $pythonRuntime
$env:AI_STRATEGIST_PYTHON = $pythonRuntime
if (Test-Path -LiteralPath $pythonRuntimeDir) {
    $env:PATH = "$pythonRuntimeDir;$env:PATH"
}

function Write-LaunchLog {
    param([string]$Message)
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -LiteralPath $logPath -Encoding UTF8 -Value "[$timestamp] $Message"
}

Write-LaunchLog "Development launcher started. RepoRoot=$resolvedRoot"
Write-LaunchLog "Python runtime: $pythonRuntime"

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

function Wait-ForMainWindow {
    param(
        $Process,
        [double]$TimeoutSeconds = 3.0
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        $Process.Refresh()
        if ($Process.HasExited) {
            return $null
        }

        $window = Get-BestWindow $Process
        if ($null -ne $window) {
            return $window
        }

        Start-Sleep -Milliseconds 150
    } while ((Get-Date) -lt $deadline)

    return $null
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
    if (Test-Path -LiteralPath $prelaunchBridgeScript) {
        $env:AI_STRATEGIST_PRELAUNCH_BRIDGE = $prelaunchBridgeScript
        Write-LaunchLog "Using source prelaunch bridge: $prelaunchBridgeScript"
    }
    Remove-Item -LiteralPath $stdoutPath, $stderrPath -Force -ErrorAction SilentlyContinue
    $started = Start-Process -FilePath $primaryExe -WorkingDirectory $resolvedRoot -PassThru -RedirectStandardOutput $stdoutPath -RedirectStandardError $stderrPath
    $started.Refresh()
    Write-LaunchLog "Primary executable started. PID=$($started.Id) HasExited=$($started.HasExited)"
    $window = Wait-ForMainWindow -Process $started -TimeoutSeconds 3.0
    if ($null -ne $window) {
        Write-LaunchLog "Found started window. PID=$($started.Id) Window=$(Format-Window $window)"
        Show-Window $window
        $started.Refresh()
        $exitCode = if ($started.HasExited) { $started.ExitCode } else { "<running>" }
        Write-LaunchLog "Post-window status. PID=$($started.Id) HasExited=$($started.HasExited) ExitCode=$exitCode"
    } else {
        $exitCode = if ($started.HasExited) { $started.ExitCode } else { "<running>" }
        Write-LaunchLog "Started process has no visible main window after short wait. PID=$($started.Id) HasExited=$($started.HasExited) ExitCode=$exitCode"
        if (Test-Path -LiteralPath $stderrPath) {
            $stderrTail = (Get-Content -LiteralPath $stderrPath -Tail 20 -ErrorAction SilentlyContinue) -join " | "
            if (-not [string]::IsNullOrWhiteSpace($stderrTail)) {
                Write-LaunchLog "stderr tail: $stderrTail"
            }
        }
    }
    exit 0
}

if (Test-Path -LiteralPath $debugExe) {
    Write-LaunchLog "Primary executable missing. Starting debug executable: $debugExe"
    Start-Process -FilePath $debugExe -WorkingDirectory $resolvedRoot
    exit 0
}

Write-LaunchLog "No source-tree AI Strategist executable found. Expected release=$primaryExe debug=$debugExe"
throw "No source-tree AI Strategist executable was found. Build it first with `pnpm --dir ai-strategist-desktop tauri build` or run the installed AI Strategist shortcut instead."
Write-LaunchLog "No executable found. Primary=$primaryExe Debug=$debugExe"
throw "AI Strategist executable was not found. Expected: $primaryExe"
