# Guia de la interfaz local

## Abrir la aplicacion

1. Haz doble clic en el lanzador. La primera vez creara `.venv` e instalara automaticamente las
   dependencias de la UI. Si la instalacion falla, la ventana mostrara el motivo y no se cerrara.
   Tambien puedes instalarlo manualmente desde PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev,ml,api]"
```

2. Haz doble clic en `Open-Market-Sentinel.bat`.
3. El navegador se abrira en [http://127.0.0.1:8765](http://127.0.0.1:8765).
4. Para detener la aplicacion, cierra la ventana de PowerShell del servidor.

La primera ejecucion crea `.env` desde `.env.example` y el lanzador carga sus variables al iniciar.
El modo operativo predeterminado usa datos actuales de Yahoo Finance sin una clave. Los datos demo
solo se usan si eliges explicitamente `MARKET_DATA_PROVIDER=demo`. Las variables definidas
externamente tienen prioridad sobre `.env`.

## Analizar un producto

- Haz clic en cualquier fila de la watchlist para abrir su grafico.
- Usa el buscador para localizar otro simbolo y pulsa `Add` para anadirlo.
- Usa el centro de control para lanzar un escaneo, elegir timeframe e historial, activar el
  escaneo periodico y actualizar el estado de la aplicacion.
- Cambia el intervalo entre 1m, 5m, 30m, 1h, 6h, 12h, 1d, 1w, 1mo, 3mo, 6mo, 1y, 3y y
  `total`.
- Alterna entre `Línea` y `Velas OHLC`; las velas muestran apertura, máximo, mínimo y cierre.
- El grafico muestra OHLCV historico, cambio del intervalo, dirección única, predicción central,
  confianza, entrada, objetivo y stop.
- El panel de paper trading muestra PnL estimado/realizado/total, VaR, CVaR, Sharpe, Sortino,
  drawdown, profit factor, win rate, expectancy, exposicion y operaciones simuladas.
- El panel de salud muestra estado del servicio, drift, uso de Astra y la ultima ejecucion.
- La dirección central es la lectura del modelo para el horizonte elegido. La banda futura superior
  e inferior es un rango aproximado calculado con ATR y momentum, no una segunda predicción
  contraria. No es una prediccion garantizada, asesoramiento financiero ni una orden automatica.

El panel sigue siendo alert-only y paper trading. No envia ordenes reales.

El puerto predeterminado es `8765`. Puedes cambiarlo antes de abrir el lanzador con
`$env:MARKET_SENTINEL_PORT=9000` si tambien necesitas reservar ese puerto.
