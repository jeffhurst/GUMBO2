$ErrorActionPreference = 'Stop'
Set-Location "$PSScriptRoot\..\backend"

if (Test-Path .venv\Scripts\python.exe) {
    .\.venv\Scripts\python.exe -m pytest tests -q
} else {
    python -m pytest tests -q
}
