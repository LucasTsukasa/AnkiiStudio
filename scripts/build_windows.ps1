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
$legacyExecutablePath = Join-Path $portableDir "AnkiiStudio.exe"
& powershell -ExecutionPolicy Bypass -File .\scripts\sign_windows.ps1 -FilePath $executablePath

# Compatibilidade de transição: a beta.9 procura AnkiiStudio.exe no ZIP.
# O executável principal continua sendo BenkyouStudio.exe.
Copy-Item -LiteralPath $executablePath -Destination $legacyExecutablePath -Force
$dataDir = Join-Path $portableDir "data"
New-Item -ItemType Directory -Force -Path $dataDir | Out-Null

$releaseDir = Join-Path (Get-Location) "release"
New-Item -ItemType Directory -Force -Path $releaseDir | Out-Null
$zipPath = Join-Path $releaseDir "BenkyouStudio-Portable-0.11.0.zip"
if (Test-Path $zipPath) { Remove-Item $zipPath -Force }
Compress-Archive -Path "$portableDir\*" -DestinationPath $zipPath -CompressionLevel Optimal

# Garante compatibilidade inclusive com atualizadores antigos, que exigem o EXE na raiz.
Add-Type -AssemblyName System.IO.Compression.FileSystem
$archive = [System.IO.Compression.ZipFile]::OpenRead($zipPath)
try {
    $hasRootExecutable = $archive.Entries | Where-Object { $_.FullName -eq "BenkyouStudio.exe" }
    if (-not $hasRootExecutable) {
        throw "Pacote portátil inválido: BenkyouStudio.exe não está na raiz do ZIP."
    }
    $hasLegacyExecutable = $archive.Entries | Where-Object { $_.FullName -eq "AnkiiStudio.exe" }
    if (-not $hasLegacyExecutable) {
        throw "Pacote portátil inválido: alias de compatibilidade AnkiiStudio.exe ausente."
    }
}
finally {
    $archive.Dispose()
}

Write-Host "Build portátil concluído:" -ForegroundColor Green
Write-Host "  Executável: dist\BenkyouStudio\BenkyouStudio.exe"
Write-Host "  Pacote: release\BenkyouStudio-Portable-0.11.0.zip"
Write-Host "  Dados locais: dist\BenkyouStudio\data\"
