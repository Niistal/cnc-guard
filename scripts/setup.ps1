$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
Push-Location $projectRoot
try {
    & uv sync --frozen --extra dev
    if ($LASTEXITCODE -ne 0) { throw 'No se pudo preparar Python.' }
    Push-Location (Join-Path $projectRoot 'web')
    try {
        & pnpm install --frozen-lockfile --ignore-scripts
        if ($LASTEXITCODE -ne 0) { throw 'No se pudo preparar la web.' }
        & pnpm build
        if ($LASTEXITCODE -ne 0) { throw 'No se pudo compilar la web.' }
    } finally { Pop-Location }
} finally { Pop-Location }
