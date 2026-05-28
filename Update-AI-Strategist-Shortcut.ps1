param(
    [string]$RepoRoot = $PSScriptRoot
)

$ErrorActionPreference = "Stop"

$resolvedRoot = (Resolve-Path -LiteralPath $RepoRoot).ProviderPath
$launcherPath = Join-Path $resolvedRoot "Launch-AI-Strategist.cmd"
$releaseExe = Join-Path $resolvedRoot "ai-strategist-desktop\src-tauri\target\release\AI-Strategist.exe"

if (-not (Test-Path -LiteralPath $launcherPath)) {
    throw "Launch-AI-Strategist.cmd was not found: $launcherPath"
}

$desktopDir = [Environment]::GetFolderPath("Desktop")
if ([string]::IsNullOrWhiteSpace($desktopDir)) {
    throw "Desktop path could not be resolved."
}

$shortcutPath = Join-Path $desktopDir "AI Strategist.lnk"
$iconPath = if (Test-Path -LiteralPath $releaseExe) { $releaseExe } else { $launcherPath }
$targetPath = if (Test-Path -LiteralPath $releaseExe) { $releaseExe } else { $launcherPath }

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $targetPath
$shortcut.WorkingDirectory = $resolvedRoot
$shortcut.Description = "Launch AI Strategist"
$shortcut.IconLocation = $iconPath
$shortcut.Save()
