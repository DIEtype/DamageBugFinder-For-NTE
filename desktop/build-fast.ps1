$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $PSScriptRoot
$venvPython = Join-Path $projectRoot '.venv\Scripts\python.exe'
$distDir = Join-Path $projectRoot 'dist-fast'
$workDir = Join-Path $projectRoot 'build-fast'
$specDir = Join-Path $projectRoot 'build-spec-fast'

if (-not (Test-Path -LiteralPath $venvPython)) {
    throw 'Missing .venv. Follow the rebuild instructions in README.md first.'
}

& $venvPython (Join-Path $projectRoot 'scripts\build-icon.py')
if ($LASTEXITCODE -ne 0) {
    throw "Icon build failed with exit code $LASTEXITCODE"
}

& node (Join-Path $projectRoot 'scripts\check-fragment.mjs')
if ($LASTEXITCODE -ne 0) {
    throw "Fragment check failed with exit code $LASTEXITCODE"
}

& node (Join-Path $projectRoot 'scripts\inject-desktop-bridge.mjs')
if ($LASTEXITCODE -ne 0) {
    throw "Desktop bridge injection failed with exit code $LASTEXITCODE"
}

& $venvPython -m PyInstaller `
    --noconfirm `
    --clean `
    --onedir `
    --windowed `
    --name 'DamageBugFinderForNTE' `
    --icon (Join-Path $projectRoot 'desktop\app.ico') `
    --distpath $distDir `
    --workpath $workDir `
    --specpath $specDir `
    --add-data "$projectRoot\index.html;." `
    "$PSScriptRoot\main.py"

if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller failed with exit code $LASTEXITCODE"
}

Write-Host "Built fast-start folder: $distDir\DamageBugFinderForNTE"
