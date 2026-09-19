$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

if (-not (Test-Path -LiteralPath ".env") -and (Test-Path -LiteralPath ".env.example")) {
    Copy-Item -LiteralPath ".env.example" -Destination ".env"
}

$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
    $python = (Get-Command python -ErrorAction Stop).Source
}

Start-Process powershell -WindowStyle Hidden -ArgumentList @(
    "-NoProfile",
    "-Command",
    "Start-Sleep -Seconds 2; Start-Process 'http://127.0.0.1:8000'"
)

Write-Host "Market Sentinel AI se abrira en http://127.0.0.1:8000"
Write-Host "Cierra esta ventana para detener el servidor."
& $python -m market_sentinel_ai serve --host 127.0.0.1 --port 8000
