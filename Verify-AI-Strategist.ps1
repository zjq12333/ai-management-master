param(
    [string]$RepoRoot = $PSScriptRoot,
    [switch]$SkipPython,
    [switch]$SkipFrontend,
    [switch]$SkipFrontendBuild,
    [switch]$SkipBundleResources,
    [switch]$SkipRust
)

$ErrorActionPreference = "Stop"

$resolvedRoot = (Resolve-Path -LiteralPath $RepoRoot).ProviderPath
$desktopDir = Join-Path $resolvedRoot "ai-strategist-desktop"
$tauriManifest = Join-Path $desktopDir "src-tauri\Cargo.toml"
$tauriConfig = Join-Path $desktopDir "src-tauri\tauri.conf.json"
$prelaunchResourcesDir = Join-Path $desktopDir "src-tauri\resources\prelaunch"
$prelaunchBridgeExe = Join-Path $prelaunchResourcesDir "prelaunch_bridge.exe"
$pythonCandidates = @(
    (Join-Path $resolvedRoot ".venv\Scripts\python.exe"),
    "D:\Tools\Python312\python.exe",
    "python"
)
$pythonExe = $null
foreach ($candidate in $pythonCandidates) {
    try {
        $resolvedCandidate = (Get-Command $candidate -ErrorAction Stop).Source
        if ($resolvedCandidate -like "*\Microsoft\WindowsApps\python.exe") {
            continue
        }
        & $resolvedCandidate -c "import sys; print(sys.executable)" | Out-Null
        if ($LASTEXITCODE -eq 0) {
            $pythonExe = $resolvedCandidate
            break
        }
    } catch {
        continue
    }
}
if ($null -eq $pythonExe) {
    throw "Unable to locate a working Python runtime. WindowsApps python.exe stubs are ignored."
}

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

if (-not (Test-Path -LiteralPath $tauriConfig)) {
    throw "Tauri config was not found: $tauriConfig"
}

Write-Host "AI Strategist verification"
Write-Host "Repo root: $resolvedRoot"

if (-not $SkipPython) {
    Invoke-Step "Python tests" {
        Push-Location $resolvedRoot
        try {
            & $pythonExe -m pytest
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

if (-not $SkipBundleResources) {
    Invoke-Step "Bundled prelaunch bridge resource" {
        if (-not (Test-Path -LiteralPath $prelaunchBridgeExe)) {
            throw "Bundled prelaunch bridge was not found: $prelaunchBridgeExe"
        }

        $config = Get-Content -LiteralPath $tauriConfig -Raw | ConvertFrom-Json
        $resources = $config.bundle.resources
        if ($null -eq $resources -or $resources.PSObject.Properties.Name -notcontains "resources/prelaunch") {
            throw "Tauri config does not map resources/prelaunch in bundle.resources."
        }
        $tauriDir = Split-Path -Parent $tauriConfig
        foreach ($resource in $resources.PSObject.Properties) {
            $source = Join-Path $tauriDir $resource.Name
            if (-not (Test-Path -LiteralPath $source)) {
                throw "Tauri bundle resource source does not exist: $($resource.Name) -> $source"
            }
        }

        $prelaunchResource = $resources.PSObject.Properties["resources/prelaunch"].Value
        if ($prelaunchResource -ne "prelaunch") {
            throw "Tauri config maps resources/prelaunch to '$prelaunchResource'; expected 'prelaunch'."
        }

        if (-not (Test-Path -LiteralPath (Join-Path $prelaunchResourcesDir "prelaunch_bridge.exe"))) {
            throw "resources/prelaunch does not contain prelaunch_bridge.exe."
        }

        & $prelaunchBridgeExe --help | Out-Null
        if ($LASTEXITCODE -ne 0) {
            throw "Bundled prelaunch bridge --help failed with exit code $LASTEXITCODE"
        }

        & $prelaunchBridgeExe runtime-status | Out-Null
        if ($LASTEXITCODE -ne 0) {
            throw "Bundled prelaunch bridge runtime-status failed with exit code $LASTEXITCODE"
        }
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
