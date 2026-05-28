param(
    [string]$RepoRoot = $PSScriptRoot,
    [switch]$SkipPython,
    [switch]$SkipFrontend,
    [switch]$SkipFrontendBuild,
    [switch]$SkipRust
)

$ErrorActionPreference = "Stop"

$resolvedRoot = (Resolve-Path -LiteralPath $RepoRoot).ProviderPath
$desktopDir = Join-Path $resolvedRoot "ai-strategist-desktop"
$tauriManifest = Join-Path $desktopDir "src-tauri\Cargo.toml"

function Invoke-Step {
    param(
        [string]$Name,
        [scriptblock]$Action
    )

    $started = Get-Date
    Write-Host ""
    Write-Host "==> $Name" -ForegroundColor Cyan
    & $Action
    $elapsed = (Get-Date) - $started
    Write-Host ("<== {0} passed in {1:n1}s" -f $Name, $elapsed.TotalSeconds) -ForegroundColor Green
}

if (-not (Test-Path -LiteralPath $desktopDir)) {
    throw "Desktop project was not found: $desktopDir"
}

if (-not (Test-Path -LiteralPath $tauriManifest)) {
    throw "Tauri manifest was not found: $tauriManifest"
}

Write-Host "AI Strategist verification"
Write-Host "Repo root: $resolvedRoot"

if (-not $SkipPython) {
    Invoke-Step "Python tests" {
        Push-Location $resolvedRoot
        try {
            python -m pytest
        } finally {
            Pop-Location
        }
    }
}

if (-not $SkipFrontend) {
    Invoke-Step "Frontend tests" {
        pnpm --dir $desktopDir test
    }
}

if (-not $SkipFrontendBuild) {
    Invoke-Step "Frontend production build" {
        pnpm --dir $desktopDir build
    }
}

if (-not $SkipRust) {
    Invoke-Step "Rust prelaunch tests" {
        cargo test --manifest-path $tauriManifest prelaunch -- --nocapture
    }

    Invoke-Step "Rust cargo check" {
        cargo check --manifest-path $tauriManifest
    }
}

Write-Host ""
Write-Host "All requested checks passed." -ForegroundColor Green
