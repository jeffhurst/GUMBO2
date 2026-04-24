$ErrorActionPreference = 'Stop'
Set-Location "$PSScriptRoot\..\frontend"

$releaseExe = "build\Release\gumbo_frontend.exe"
$debugExe = "build\gumbo_frontend.exe"

if (Test-Path $releaseExe) {
    & $releaseExe
} elseif (Test-Path $debugExe) {
    & $debugExe
} else {
    Write-Host "Frontend executable not found. Run .\scripts\build_frontend.ps1 first."
    exit 1
}
