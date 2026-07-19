$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $PSScriptRoot
$venvPython = Join-Path $projectRoot '.venv\Scripts\python.exe'
$distDir = Join-Path $projectRoot 'dist'
$workDir = Join-Path $projectRoot 'build'
$specDir = Join-Path $projectRoot 'build-spec'

if (-not (Test-Path -LiteralPath $venvPython)) {
    throw 'Missing .venv. Follow the rebuild instructions in README.md first.'
}

& $venvPython -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --windowed `
    --name 'GameDamageCalculator' `
    --distpath $distDir `
    --workpath $workDir `
    --specpath $specDir `
    --add-data "$projectRoot\index.html;." `
    "$PSScriptRoot\main.py"

if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller failed with exit code $LASTEXITCODE"
}

Write-Host "Built: $distDir\GameDamageCalculator.exe"
