param(
    [switch]$Quick,
    [switch]$CaptureWindowsImportBaseline
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ProjectRoot = Split-Path -Parent $PSScriptRoot
Push-Location $ProjectRoot
try {
    $env:QT_QPA_PLATFORM = "offscreen"

    Write-Host "[1/4] Python og golden-tests" -ForegroundColor Cyan
    python -m pytest -q
    if ($LASTEXITCODE -ne 0) { throw "pytest fejlede" }

    Write-Host "[2/4] Importregler" -ForegroundColor Cyan
    if ((Test-Path "pyproject.toml") -and (Get-Command lint-imports -ErrorAction SilentlyContinue)) {
        lint-imports
        if ($LASTEXITCODE -ne 0) { throw "lint-imports fejlede" }
    }
    else {
        Write-Host "Springes over indtil fase 1 eller import-linter er installeret."
    }

    Write-Host "[3/4] Afhængighedskort" -ForegroundColor Cyan
    python tools/analyze_core_dependencies.py
    if ($LASTEXITCODE -ne 0) { throw "Afhængighedsanalysen fejlede" }

    Write-Host "[4/4] Importtid" -ForegroundColor Cyan
    if ($CaptureWindowsImportBaseline) {
        python tools/measure_import_time.py --samples 5 --write-baseline tests/golden/core_import_time_windows.json
    }
    elseif (-not $Quick) {
        python tools/measure_import_time.py --samples 3 --baseline tests/golden/core_import_time_baseline.json
    }
    if ($LASTEXITCODE -ne 0) { throw "Måling af importtid fejlede" }

    Write-Host "Alle lokale refaktor-kontroller bestod." -ForegroundColor Green
}
finally {
    Pop-Location
}
