$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
Push-Location $projectRoot
try {
    & (Join-Path $projectRoot '.venv/Scripts/python.exe') -m cnc_guard.cli prepare --dataset all
    if ($LASTEXITCODE -ne 0) { throw 'La preparación no finalizó; consulta el error anterior.' }
} finally { Pop-Location }
