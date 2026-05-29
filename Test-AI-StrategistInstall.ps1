param(
    [Parameter(Mandatory = $true)]
    [string]$InstallDir,
    [switch]$SkipAppExe
)

$ErrorActionPreference = "Stop"

$resolvedInstallDir = (Resolve-Path -LiteralPath $InstallDir).ProviderPath
$appExe = Join-Path $resolvedInstallDir "AI Strategist.exe"
$bridgeExe = Join-Path $resolvedInstallDir "prelaunch\prelaunch_bridge.exe"

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

Write-Host "AI Strategist installed-app verification"
Write-Host "Install dir: $resolvedInstallDir"

if (-not $SkipAppExe) {
    Invoke-Step "Installed app executable exists" {
        if (-not (Test-Path -LiteralPath $appExe)) {
            throw "AI Strategist executable was not found: $appExe"
        }
    }
}

Invoke-Step "Installed prelaunch bridge exists" {
    if (-not (Test-Path -LiteralPath $bridgeExe)) {
        throw "prelaunch_bridge.exe was not found: $bridgeExe"
    }
}

Invoke-Step "Installed prelaunch bridge smoke commands" {
    & $bridgeExe --help | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "prelaunch_bridge.exe --help failed with exit code $LASTEXITCODE"
    }

    & $bridgeExe runtime-status | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "prelaunch_bridge.exe runtime-status failed with exit code $LASTEXITCODE"
    }
}

Write-Host ""
Write-Host "Installed-app verification passed." -ForegroundColor Green
