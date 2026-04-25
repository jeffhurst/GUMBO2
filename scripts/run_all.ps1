$ErrorActionPreference = 'Stop'

function Restart-BackendIfRunning {
    $backendPort = 8000
    $owningPids = @()

    try {
        $connections = Get-NetTCPConnection -LocalPort $backendPort -State Listen -ErrorAction Stop
        $owningPids = $connections | Select-Object -ExpandProperty OwningProcess -Unique
    } catch {
        # Fallback when Get-NetTCPConnection is unavailable in constrained shells.
        $owningPids = @()
    }

    if (-not $owningPids -or $owningPids.Count -eq 0) {
        Write-Host "No existing backend listener found on port $backendPort."
        return
    }

    foreach ($processId in $owningPids) {
        try {
            Stop-Process -Id $processId -Force -ErrorAction Stop
            Write-Host "Stopped existing backend process (PID: $processId) on port $backendPort."
        } catch {
            Write-Warning "Unable to stop process $processId on port ${backendPort}: $($_.Exception.Message)"
        }
    }

    Start-Sleep -Milliseconds 500
}

Restart-BackendIfRunning
& "$PSScriptRoot\build_frontend.ps1"
& "$PSScriptRoot\run_frontend.ps1"
