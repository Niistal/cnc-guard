$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
Push-Location $projectRoot
try {
    $projectPython = Join-Path $projectRoot '.venv/Scripts/python.exe'
    & $projectPython -m ruff check src tests app.py
    if ($LASTEXITCODE -ne 0) { throw 'Lint Python fallido.' }
    & $projectPython -m pytest -q
    if ($LASTEXITCODE -ne 0) { throw 'Pruebas Python fallidas.' }
    & $projectPython -m build --no-isolation
    if ($LASTEXITCODE -ne 0) { throw 'Build Python fallido.' }
    Push-Location (Join-Path $projectRoot 'web')
    try {
        & pnpm lint
        if ($LASTEXITCODE -ne 0) { throw 'Lint web fallido.' }
        & pnpm build
        if ($LASTEXITCODE -ne 0) { throw 'Build web fallido.' }
        & pnpm test
        if ($LASTEXITCODE -ne 0) { throw 'Pruebas de navegador fallidas.' }
    } finally { Pop-Location }
} finally { Pop-Location }
