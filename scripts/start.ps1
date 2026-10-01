$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
Push-Location $projectRoot
try {
    Write-Host 'CNC Guard: http://127.0.0.1:8000 - Ctrl+C para detener'
    & (Join-Path $projectRoot '.venv/Scripts/python.exe') -m cnc_guard.cli serve
} finally { Pop-Location }
