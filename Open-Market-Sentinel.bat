@echo off
setlocal
cd /d "%~dp0"
powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0Open-Market-Sentinel.ps1"
if errorlevel 1 (
    echo.
    echo El lanzador termino con un error. La ventana se mantiene abierta para leerlo.
    pause
)
endlocal
