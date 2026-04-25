param(
    [switch]$ForceRestart
)

$ErrorActionPreference = 'Stop'

Set-Location "$PSScriptRoot\..\backend"

if (Test-Path ".venv\Scripts\Activate.ps1") {
    . .venv\Scripts\Activate.ps1
} else {
    Write-Error "Virtual environment not found. Please run setup_backend.ps1 first."
    exit 1
}

$backendHost = "127.0.0.1"
$port = 8000
$healthUrl = "http://$backendHost`:$port/health"

function Get-ListeningPids([int]$LocalPort) {
    $listeners = Get-NetTCPConnection -LocalPort $LocalPort -State Listen -ErrorAction SilentlyContinue

    if (-not $listeners) {
        return @()
    }

    return $listeners | Select-Object -ExpandProperty OwningProcess -Unique
}

if ($ForceRestart) {
    $existingPids = Get-ListeningPids -LocalPort $port

    if ($existingPids.Count -gt 0) {
        Write-Host "Stopping process(es) already listening on $backendHost`:$port -> $($existingPids -join ', ')"

        foreach ($processId in $existingPids) {
            Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
        }

        Start-Sleep -Seconds 1
    }
} else {
    try {
        $health = Invoke-WebRequest -UseBasicParsing -Uri $healthUrl -TimeoutSec 2

        if ($health.StatusCode -eq 200) {
            Write-Host "Backend already running at $healthUrl. Reusing existing process."
            exit 0
        }
    } catch {
        # No healthy listener on expected backend port; continue launching.
    }
}

python -m uvicorn app.main:app --host $backendHost --port $port
