# Guia de la interfaz local

## Abrir la aplicacion

1. Instala las dependencias una vez desde PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev,ml,api]"
```

2. Haz doble clic en `Open-Market-Sentinel.bat`.
3. El navegador se abrira en [http://127.0.0.1:8000](http://127.0.0.1:8000).
4. Para detener la aplicacion, cierra la ventana de PowerShell del servidor.

La primera ejecucion crea `.env` desde `.env.example`. El modo predeterminado usa datos demo
deterministas. Para consultar datos de mercado actuales sin una clave, edita `.env` y usa
`MARKET_DATA_PROVIDER=yahoo`; la busqueda de instrumentos usa Yahoo por defecto.

## Analizar un producto

- Haz clic en cualquier fila de la watchlist para abrir su grafico.
- Usa el buscador para localizar otro simbolo y pulsa `Add` para anadirlo.
- Cambia el intervalo entre 1m, 5m, 30m, 1h, 6h, 12h, 1d, 1w, 1mo, 3mo, 6mo, 1y, 3y y
  `total`.
- El grafico muestra OHLCV historico, cambio del intervalo, confianza, entrada, objetivo y stop.
- La banda futura superior e inferior es un escenario aproximado calculado con ATR y momentum.
  No es una prediccion garantizada, asesoramiento financiero ni una orden automatica.

El panel sigue siendo alert-only y paper trading. No envia ordenes reales.
