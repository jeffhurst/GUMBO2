$ErrorActionPreference = 'Stop'
Set-Location "$PSScriptRoot\..\frontend"

cmake -S . -B build
cmake --build build --config Release
