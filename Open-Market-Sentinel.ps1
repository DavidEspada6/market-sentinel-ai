$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

try {
    if (-not (Test-Path -LiteralPath ".env") -and (Test-Path -LiteralPath ".env.example")) {
        Copy-Item -LiteralPath ".env.example" -Destination ".env"
    }

    $python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
    if (-not (Test-Path -LiteralPath $python)) {
        $systemPython = (Get-Command python -ErrorAction Stop).Source
        Write-Host "Creando el entorno local de Python..."
        & $systemPython -m venv (Join-Path $PSScriptRoot ".venv")
        if ($LASTEXITCODE -ne 0) { throw "No se pudo crear el entorno de Python." }
    }

    $env:PYTHONPATH = "$(Join-Path $PSScriptRoot 'src');$env:PYTHONPATH"
    $imports = & $python -c "import fastapi, uvicorn" 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Faltan dependencias de la UI. Instalando FastAPI y Uvicorn..."
        & $python -m pip install --disable-pip-version-check -e ".[api]"
        if ($LASTEXITCODE -ne 0) {
            throw "No se pudieron instalar las dependencias. Ejecuta: python -m pip install -e `".[api]`""
        }
    }

    $port = if ($env:MARKET_SENTINEL_PORT) { [int]$env:MARKET_SENTINEL_PORT } else { 8765 }
    Start-Process powershell -WindowStyle Hidden -ArgumentList @(
        "-NoProfile",
        "-Command",
        "Start-Sleep -Seconds 2; Start-Process 'http://127.0.0.1:$port'"
    )

    Write-Host "Market Sentinel AI se abrira en http://127.0.0.1:$port"
    Write-Host "Cierra esta ventana para detener el servidor."
    & $python -m market_sentinel_ai serve --host 127.0.0.1 --port $port
    if ($LASTEXITCODE -ne 0) { throw "El servidor no pudo iniciarse. Comprueba si el puerto $port esta ocupado." }
}
catch {
    Write-Host ""
    Write-Host "ERROR: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
