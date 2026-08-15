$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

if (-not (Test-Path ".venv")) {
    py -m venv .venv
}

& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
& .\.venv\Scripts\python.exe -m pytest
& .\.venv\Scripts\python.exe -m PyInstaller --clean --noconfirm BenkyouStudio.spec

$portableDir = Join-Path (Get-Location) "dist\BenkyouStudio"
$executablePath = Join-Path $portableDir "BenkyouStudio.exe"
& powershell -ExecutionPolicy Bypass -File .\scripts\sign_windows.ps1 -FilePath $executablePath

$dataDir = Join-Path $portableDir "data"
New-Item -ItemType Directory -Force -Path $dataDir | Out-Null

$releaseDir = Join-Path (Get-Location) "release"
New-Item -ItemType Directory -Force -Path $releaseDir | Out-Null
$zipPath = Join-Path $releaseDir "BenkyouStudio-Portable-0.11.1.zip"
if (Test-Path $zipPath) { Remove-Item $zipPath -Force }
Compress-Archive -Path "$portableDir\*" -DestinationPath $zipPath -CompressionLevel Optimal

# Garante que o executável principal do BenkyouStudio esteja na raiz do ZIP.
Add-Type -AssemblyName System.IO.Compression.FileSystem
$archive = [System.IO.Compression.ZipFile]::OpenRead($zipPath)
try {
    $hasRootExecutable = $archive.Entries | Where-Object { $_.FullName -eq "BenkyouStudio.exe" }
    if (-not $hasRootExecutable) {
        throw "Pacote portátil inválido: BenkyouStudio.exe não está na raiz do ZIP."
    }
}
finally {
    $archive.Dispose()
}

Write-Host "Build portátil concluído:" -ForegroundColor Green
Write-Host "  Executável: dist\BenkyouStudio\BenkyouStudio.exe"
Write-Host "  Pacote: release\BenkyouStudio-Portable-0.11.1.zip"
Write-Host "  Dados locais: dist\BenkyouStudio\data\"
