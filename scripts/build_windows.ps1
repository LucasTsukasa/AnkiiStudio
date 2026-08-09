$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

if (-not (Test-Path ".venv")) {
    py -m venv .venv
}

& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
& .\.venv\Scripts\python.exe -m pytest
& .\.venv\Scripts\python.exe -m PyInstaller --clean --noconfirm AnkiiStudio.spec

$portableDir = Join-Path (Get-Location) "dist\AnkiiStudio"
$dataDir = Join-Path $portableDir "data"
New-Item -ItemType Directory -Force -Path $dataDir | Out-Null

$releaseDir = Join-Path (Get-Location) "release"
New-Item -ItemType Directory -Force -Path $releaseDir | Out-Null
$zipPath = Join-Path $releaseDir "AnkiiStudio-Portable-0.10.0.zip"
if (Test-Path $zipPath) { Remove-Item $zipPath -Force }
Compress-Archive -Path "$portableDir\*" -DestinationPath $zipPath -CompressionLevel Optimal

Write-Host "Build portátil concluído:" -ForegroundColor Green
Write-Host "  Executável: dist\AnkiiStudio\AnkiiStudio.exe"
Write-Host "  Pacote: release\AnkiiStudio-Portable-0.10.0.zip"
Write-Host "  Dados locais: dist\AnkiiStudio\data\"
