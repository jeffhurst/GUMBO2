$ErrorActionPreference = 'Stop'
Set-Location "$PSScriptRoot\..\backend"

if (Test-Path ".venv\Scripts\Activate.ps1") {
    . .venv\Scripts\Activate.ps1
} else {
    Write-Error "Virtual environment not found. Please run setup_backend.ps1 first."
    exit 1
}


python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
