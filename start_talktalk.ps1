$ErrorActionPreference = "Stop"

Set-Location -Path $PSScriptRoot

$venvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
$appScript = Join-Path $PSScriptRoot "app.py"

if (-not (Test-Path $venvPython)) {
    Write-Error "Virtual environment not found at $venvPython"
    exit 1
}

& $venvPython $appScript @args

