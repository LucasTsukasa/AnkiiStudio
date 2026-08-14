param(
    [Parameter(Mandatory=$true)][string]$FilePath
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $FilePath)) {
    throw "Arquivo para assinatura não encontrado: $FilePath"
}

$pfxPath = $env:ANKIISTUDIO_SIGN_PFX
$pfxPassword = $env:ANKIISTUDIO_SIGN_PASSWORD
$signtool = $env:ANKIISTUDIO_SIGNTOOL
if (-not $signtool) { $signtool = "signtool.exe" }

if (-not $pfxPath) {
    Write-Host "Assinatura Authenticode não configurada; build continuará sem assinatura." -ForegroundColor Yellow
    Write-Host "Para distribuição pública, configure SignPath Foundation ou ANKIISTUDIO_SIGN_PFX/ANKIISTUDIO_SIGN_PASSWORD." -ForegroundColor Yellow
    exit 0
}
if (-not (Test-Path $pfxPath)) {
    throw "Certificado PFX não encontrado em ANKIISTUDIO_SIGN_PFX."
}
if (-not $pfxPassword) {
    throw "ANKIISTUDIO_SIGN_PASSWORD não foi definida."
}

& $signtool sign /fd SHA256 /f $pfxPath /p $pfxPassword /tr "http://timestamp.digicert.com" /td SHA256 $FilePath
if ($LASTEXITCODE -ne 0) { throw "SignTool falhou ao assinar $FilePath." }

& $signtool verify /pa /v $FilePath
if ($LASTEXITCODE -ne 0) { throw "A assinatura de $FilePath não pôde ser verificada." }
Write-Host "Assinatura Authenticode aplicada e verificada: $FilePath" -ForegroundColor Green
