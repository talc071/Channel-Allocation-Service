# One-command test runner for Windows PowerShell.
# Creates a venv if missing, installs deps, then runs pytest.
# Usage:  .\run_tests.ps1

$ErrorActionPreference = "Stop"

Push-Location $PSScriptRoot
try {
    if (-not (Test-Path ".venv")) {
        Write-Host "Creating virtual environment..." -ForegroundColor Cyan
        py -3 -m venv .venv
    }

    $python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"

    Write-Host "Installing dependencies..." -ForegroundColor Cyan
    & $python -m pip install --quiet --disable-pip-version-check -r requirements.txt

    Write-Host "Running tests..." -ForegroundColor Cyan
    & $python -m pytest
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
