$ErrorActionPreference = 'Stop'
Set-Location "$PSScriptRoot\..\backend"

if (!(Test-Path .venv)) {
    python -m venv .venv
}

.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\pip.exe install -r requirements.txt
