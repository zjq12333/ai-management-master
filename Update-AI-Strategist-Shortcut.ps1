param(
    [string]$RepoRoot = $PSScriptRoot
)

$ErrorActionPreference = "Stop"

$resolvedRoot = (Resolve-Path -LiteralPath $RepoRoot).ProviderPath
$launcherPath = Join-Path $resolvedRoot "Launch-AI-Strategist.cmd"
$startScript = Join-Path $resolvedRoot "Start-AI-Strategist.ps1"
$primaryExe = Join-Path $resolvedRoot "ai-strategist-desktop\src-tauri\target\release\AI-Strategist.exe"
$fallbackManagerExe = Join-Path $resolvedRoot "third_party\codex-plus-plus\target\release\codex-plus-plus-manager.exe"

if (-not (Test-Path -LiteralPath $startScript)) {
    throw "Start-AI-Strategist.ps1 was not found: $startScript"
}

$desktopDir = [Environment]::GetFolderPath("Desktop")
if ([string]::IsNullOrWhiteSpace($desktopDir)) {
    throw "Desktop path could not be resolved."
}

$shortcutStamp = Get-Date -Format "yyyyMMdd-HHmmss"
$shortcutPaths = @(
    (Join-Path $desktopDir "AI Strategist.lnk"),
    (Join-Path $desktopDir "AI Strategist - $shortcutStamp.lnk")
)
$targetPath = Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0\powershell.exe"
$arguments = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$startScript`" -RepoRoot `"$resolvedRoot`""
$iconPath = if (Test-Path -LiteralPath $primaryExe) {
    $primaryExe
} elseif (Test-Path -LiteralPath $fallbackManagerExe) {
    $fallbackManagerExe
} else {
    $launcherPath
}

$shell = New-Object -ComObject WScript.Shell
foreach ($shortcutPath in $shortcutPaths) {
    $shortcut = $shell.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = $targetPath
    $shortcut.Arguments = $arguments
    $shortcut.WorkingDirectory = $resolvedRoot
    $shortcut.Description = "Launch AI Strategist"
    $shortcut.IconLocation = $iconPath
    $shortcut.Save()
}

Write-Host "Shortcut updated: $($shortcutPaths[0])"
Write-Host "Fresh shortcut created: $($shortcutPaths[1])"
Write-Host "Target: $targetPath"
Write-Host "Arguments: $arguments"
Write-Host "WorkingDirectory: $resolvedRoot"
