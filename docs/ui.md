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
- La watchlist muestra una franja verde para lecturas alcistas, roja para bajistas y gris cuando
  no hay una señal utilizable; la lectura se actualiza con datos del proveedor.
- Usa el centro de control para lanzar un escaneo, elegir timeframe e historial, activar el
  escaneo periodico y actualizar el estado de la aplicacion.
- Cambia el intervalo entre 1m, 5m, 30m, 1h, 6h, 12h, 1d, 1w, 1mo, 3mo, 6mo, 1y, 3y y
  `total`.
- Alterna entre `Línea` y `Velas OHLC`; las velas muestran apertura, máximo, mínimo y cierre.
- El grafico muestra OHLCV historico, cambio del intervalo, dirección única, predicción central,
  confianza, entrada, objetivo y stop. Entrada, objetivo y stop aparecen como bloques separados
  y coloreados para no confundir sus precios.
- El cuadro **Por qué el modelo marca esta lectura** explica por qué el activo aparece alcista,
  bajista o en espera usando momentum, medias, RSI, Bollinger, volumen y advertencias. También
  explica que la entrada usa el último cierre y cómo el ATR, los costes, el movimiento esperado
  y el ratio riesgo/beneficio determinan objetivo y stop.
- El eje inferior muestra la linea temporal. Al pasar el raton por encima del grafico aparece la
  fecha/hora y el precio del punto histórico; en la zona futura muestra la predicción central y
  su rango aproximado.
- El panel de paper trading muestra PnL estimado/realizado/total, VaR, CVaR, Sharpe, Sortino,
  drawdown, profit factor, win rate, expectancy, exposicion y operaciones simuladas.
- El panel **Modo simulación** mantiene una cuenta virtual independiente. Permite fijar el capital
  inicial, elegir el activo seleccionado, usar un margen, escoger apalancamiento de 1x a 10x y
  abrir posiciones `LONG` o `SHORT`. Las posiciones abiertas muestran entrada, precio actual,
  PnL no realizado y liquidación aproximada; el botón `Cerrar` fija el PnL realizado.
- La cuenta de simulación se marca con precios del proveedor aproximadamente cada 15 segundos
  mientras la UI permanece abierta. Si el proveedor no entrega un precio nuevo, conserva el último
  precio marcado y lo indica en el estado. `Reiniciar simulación` borra el historial después de
  cerrar las posiciones abiertas.
- El panel de salud muestra estado del servicio, modelo cuantitativo, drift, uso de Astra y la
  ultima ejecucion. El modelo adaptativo se vuelve a entrenar al detectar una vela nueva durante
  un escaneo; con poco historial se indica `Baseline de respaldo`.
- El menú superior abre **Análisis de predicciones**. La aplicación guarda automáticamente las
  predicciones de cada producto y horizonte mientras el servidor está abierto, las compara con el
  precio real cuando vence cada horizonte y muestra aciertos, fallos, pendientes, mejor horizonte,
  retorno medio y detalle por producto. La tabla de resultados muestra todos los horizontes
  configurados, aunque todavía tengan cero muestras. Puedes filtrar por símbolo, timeframe,
  horizonte y estado.
- El historial de simulación conserva margen, apalancamiento, notional, costes de entrada y salida,
  PnL y motivo de cierre. El monitor automático se ejecuta en segundo plano cada 60 segundos por
  defecto, aunque estés en otra pestaña, siempre que el servidor siga abierto, y
  evita duplicar una predicción para la misma vela; una predicción nueva aparece al llegar una vela
  nueva del timeframe correspondiente.
- Los sábados y domingos el monitor pausa acciones, ETFs, índices, divisas y materias primas;
  las criptomonedas continúan al estar disponibles 24/7. Las predicciones del viernes esperan a
  la primera vela real posterior para poder medirse correctamente.
- La dirección central es la lectura del modelo para el horizonte elegido. La banda futura superior
  e inferior es un rango aproximado calculado con ATR y momentum, no una segunda predicción
  contraria. No es una prediccion garantizada, asesoramiento financiero ni una orden automatica.
- Al cambiar de ventana, la aplicación recalcula las velas, indicadores y predicción del nuevo
  horizonte. Si el mercado está cerrado y no hay velas exactamente en esa ventana, recupera la
  última sesión disponible, recalcula con historial suficiente y muestra un aviso de antigüedad.
  Mientras carga o si falla, limpia la lectura anterior para evitar mezclar horizontes.

El panel sigue siendo alert-only, paper trading y simulación local. No envia ordenes reales ni
conecta con un broker.

El puerto predeterminado es `8765`. Puedes cambiarlo antes de abrir el lanzador con
`$env:MARKET_SENTINEL_PORT=9000` si tambien necesitas reservar ese puerto.
