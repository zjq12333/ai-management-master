param(
    [string]$RepoRoot = $PSScriptRoot,
    [string]$OutputDir,
    [switch]$Clean
)

$ErrorActionPreference = "Stop"

$resolvedRoot = (Resolve-Path -LiteralPath $RepoRoot).ProviderPath
$bridgeScript = Join-Path $resolvedRoot "prelaunch_bridge.py"
$rendererInjectScript = Join-Path $resolvedRoot "enhancer_renderer_inject.js"
$runtimeDataFiles = @(
    "enhancer_runtime.py",
    "enhancer_runtime_watcher.py",
    "enhancer_handoff.py",
    "repair_codex_desktop_history.py",
    "prelaunch_manager.py",
    "codex_desktop_launcher.py",
    "codex_desktop_app_paths.py"
)
$distDir = if ($OutputDir) {
    $OutputDir
} else {
    Join-Path $resolvedRoot "ai-strategist-desktop\src-tauri\resources\prelaunch"
}
$buildDir = Join-Path $resolvedRoot "artifacts\pyinstaller-prelaunch-build"
$specDir = Join-Path $resolvedRoot "artifacts\pyinstaller-prelaunch-spec"

if (-not (Test-Path -LiteralPath $bridgeScript)) {
    throw "prelaunch_bridge.py was not found: $bridgeScript"
}
if (-not (Test-Path -LiteralPath $rendererInjectScript)) {
    throw "enhancer_renderer_inject.js was not found: $rendererInjectScript"
}
foreach ($fileName in $runtimeDataFiles) {
    $filePath = Join-Path $resolvedRoot $fileName
    if (-not (Test-Path -LiteralPath $filePath)) {
        throw "$fileName was not found: $filePath"
    }
}

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$pyInstallerVersion = & python -m PyInstaller --version 2>$null
$pyInstallerExitCode = $LASTEXITCODE
$ErrorActionPreference = $previousErrorActionPreference
if ($pyInstallerExitCode -ne 0 -or [string]::IsNullOrWhiteSpace($pyInstallerVersion)) {
    throw "PyInstaller is not installed. Install it in the active Python environment, then rerun this script: python -m pip install pyinstaller"
}

if ($Clean) {
    Remove-Item -LiteralPath $distDir -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $buildDir -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $specDir -Recurse -Force -ErrorAction SilentlyContinue
}

New-Item -ItemType Directory -Force -Path $distDir, $buildDir, $specDir | Out-Null

python -m PyInstaller `
    --onefile `
    --name prelaunch_bridge `
    --distpath $distDir `
    --workpath $buildDir `
    --specpath $specDir `
    --paths $resolvedRoot `
    --hidden-import prelaunch_manager `
    --hidden-import repair_codex_desktop_history `
    --hidden-import codex_desktop_app_paths `
    --hidden-import codex_desktop_launcher `
    --add-data "$rendererInjectScript;." `
    --add-data "$(Join-Path $resolvedRoot 'enhancer_runtime.py');." `
    --add-data "$(Join-Path $resolvedRoot 'enhancer_runtime_watcher.py');." `
    --add-data "$(Join-Path $resolvedRoot 'enhancer_handoff.py');." `
    --add-data "$(Join-Path $resolvedRoot 'repair_codex_desktop_history.py');." `
    --add-data "$(Join-Path $resolvedRoot 'prelaunch_manager.py');." `
    --add-data "$(Join-Path $resolvedRoot 'codex_desktop_launcher.py');." `
    --add-data "$(Join-Path $resolvedRoot 'codex_desktop_app_paths.py');." `
    $bridgeScript

$exePath = Join-Path $distDir "prelaunch_bridge.exe"
if (-not (Test-Path -LiteralPath $exePath)) {
    throw "PyInstaller completed but output exe was not found: $exePath"
}

Write-Host "Built prelaunch bridge: $exePath" -ForegroundColor Green
