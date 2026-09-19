# ruff: noqa: E501

from __future__ import annotations

from dataclasses import dataclass
from html import escape

from market_sentinel_ai.analytics import chart_window_specs
from market_sentinel_ai.domain.instruments import Instrument
from market_sentinel_ai.domain.operations import AlertRecord, SignalRecord
from market_sentinel_ai.domain.prediction import Signal
from market_sentinel_ai.ports.backtesting import BacktestReport

# The dashboard is rendered as one HTML/JavaScript template; embedded lines are intentionally long.


@dataclass(frozen=True)
class DashboardViewModel:
    title: str
    generated_at_iso: str
    signals: tuple[Signal, ...]
    backtest: BacktestReport
    walk_forward: dict[str, float | int]


def render_dashboard(model: DashboardViewModel) -> str:
    signals_html = "\n".join(_render_signal(signal) for signal in model.signals) or (
        '<tr><td colspan="5">No active signals</td></tr>'
    )
    chart_bars = _metric_bars(
        {
            "Win rate": model.backtest.win_rate,
            "WF accuracy": float(model.walk_forward.get("average_accuracy", 0.0)),
            "WF coverage": float(model.walk_forward.get("average_coverage", 0.0)),
        }
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(model.title)}</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f5f7f8;
      --panel: #ffffff;
      --ink: #182026;
      --muted: #5e6a72;
      --line: #d9e0e4;
      --teal: #087f8c;
      --amber: #b7791f;
      --red: #b42318;
      --green: #16803c;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Inter, Segoe UI, Arial, sans-serif;
      background: var(--bg);
      color: var(--ink);
      letter-spacing: 0;
    }}
    header {{
      border-bottom: 1px solid var(--line);
      background: var(--panel);
      padding: 18px 24px;
      display: flex;
      justify-content: space-between;
      gap: 16px;
      align-items: center;
    }}
    h1 {{ font-size: 22px; margin: 0; font-weight: 700; }}
    main {{ padding: 24px; max-width: 1180px; margin: 0 auto; }}
    .grid {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; }}
    .panel {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 16px;
    }}
    .metric-label {{ color: var(--muted); font-size: 12px; text-transform: uppercase; }}
    .metric-value {{ margin-top: 8px; font-size: 24px; font-weight: 700; }}
    section {{ margin-top: 20px; }}
    h2 {{ font-size: 16px; margin: 0 0 12px; }}
    table {{ width: 100%; border-collapse: collapse; background: var(--panel); }}
    th, td {{ border-bottom: 1px solid var(--line); padding: 10px 12px; text-align: left; }}
    th {{ color: var(--muted); font-size: 12px; text-transform: uppercase; }}
    .direction-LONG {{ color: var(--green); font-weight: 700; }}
    .direction-SHORT {{ color: var(--red); font-weight: 700; }}
    .direction-NO_TRADE {{ color: var(--muted); font-weight: 700; }}
    .bars {{ display: grid; gap: 10px; }}
    .bar-row {{
      display: grid;
      grid-template-columns: 110px 1fr 54px;
      gap: 10px;
      align-items: center;
    }}
    .track {{ height: 12px; background: #edf1f3; border-radius: 999px; overflow: hidden; }}
    .fill {{ height: 100%; background: var(--teal); }}
    .muted {{ color: var(--muted); }}
    @media (max-width: 760px) {{
      header {{ align-items: flex-start; flex-direction: column; }}
      main {{ padding: 14px; }}
      .grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      th, td {{ padding: 8px; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>{escape(model.title)}</h1>
    <div class="muted">{escape(model.generated_at_iso)}</div>
  </header>
  <main>
    <div class="grid">
      {_metric_panel("Trades", str(model.backtest.trades))}
      {_metric_panel("Expectancy", f"{model.backtest.expectancy_bps:.2f} bps")}
      {_metric_panel("Profit Factor", _format_float(model.backtest.profit_factor))}
      {_metric_panel("Max Drawdown", f"{model.backtest.max_drawdown_pct:.2f}%")}
    </div>
    <section class="panel">
      <h2>Model Snapshot</h2>
      <div class="bars">{chart_bars}</div>
    </section>
    <section>
      <h2>Signals</h2>
      <table>
        <thead>
          <tr>
            <th>Symbol</th>
            <th>Direction</th>
            <th>Confidence</th>
            <th>Model</th>
            <th>Rationale</th>
          </tr>
        </thead>
        <tbody>
          {signals_html}
        </tbody>
      </table>
    </section>
  </main>
</body>
</html>
"""


def _metric_panel(label: str, value: str) -> str:
    return (
        '<div class="panel">'
        f'<div class="metric-label">{escape(label)}</div>'
        f'<div class="metric-value">{escape(value)}</div>'
        "</div>"
    )


def _metric_bars(metrics: dict[str, float]) -> str:
    rows: list[str] = []
    for label, value in metrics.items():
        bounded = max(0.0, min(1.0, value))
        rows.append(
            '<div class="bar-row">'
            f"<span>{escape(label)}</span>"
            f'<div class="track"><div class="fill" style="width: {bounded * 100:.1f}%"></div></div>'
            f"<span>{bounded * 100:.1f}%</span>"
            "</div>"
        )
    return "\n".join(rows)


def _render_signal(signal: Signal) -> str:
    direction = signal.prediction.direction.value
    return (
        "<tr>"
        f"<td>{escape(signal.prediction.symbol)}</td>"
        f'<td class="direction-{escape(direction)}">{escape(direction)}</td>'
        f"<td>{signal.confidence:.2f}</td>"
        f"<td>{escape(signal.prediction.model_name)}</td>"
        f"<td>{escape(signal.rationale)}</td>"
        "</tr>"
    )


def _format_float(value: float) -> str:
    if value == float("inf"):
        return "inf"
    return f"{value:.2f}"


def render_operational_dashboard(
    signals: list[SignalRecord],
    alerts: list[AlertRecord],
    *,
    generated_at_iso: str,
    environment: str,
    watchlist: list[Instrument] | None = None,
    risk_metrics: dict[str, object] | None = None,
) -> str:
    watchlist = watchlist or []
    risk_metrics = risk_metrics or {}
    signal_rows = "\n".join(_render_signal_record(signal) for signal in signals) or (
        '<tr><td colspan="6">No persisted signals</td></tr>'
    )
    alert_rows = "\n".join(_render_alert_record(alert) for alert in alerts) or (
        '<tr><td colspan="5">No persisted alerts</td></tr>'
    )
    watchlist_rows = "\n".join(_render_instrument_row(item) for item in watchlist) or (
        '<tr><td colspan="5">Watchlist is empty</td></tr>'
    )
    default_symbol = watchlist[0].symbol if watchlist else ""
    window_buttons = "".join(
        f'<button type="button" class="window-button'
        f'{" active" if spec.window.value == "1d" else ""}'
        f'" data-window="{escape(spec.window.value)}">{escape(spec.label)}</button>'
        for spec in chart_window_specs()
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Market Sentinel AI</title>
  <style>
    :root {{ color-scheme: light; --bg: #f5f7f8; --panel: #fff; --ink: #182026;
      --muted: #5e6a72; --line: #d9e0e4; --teal: #087f8c; --red: #b42318; --green: #16803c;
      --blue: #2563eb; --amber: #b7791f; }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; font-family: Inter, Segoe UI, Arial, sans-serif; background: var(--bg);
      color: var(--ink); letter-spacing: 0; }}
    header {{ background: var(--panel); border-bottom: 1px solid var(--line); padding: 18px 24px;
      display: flex; justify-content: space-between; align-items: center; gap: 16px; }}
    h1 {{ font-size: 22px; margin: 0; }}
    h2 {{ font-size: 16px; margin: 0 0 12px; }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 24px; }}
    .meta {{ color: var(--muted); font-size: 13px; }}
    .toolbar {{ display: flex; align-items: center; gap: 12px; }}
    .searchbar {{ display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 14px; }}
    input, select {{ border: 1px solid var(--line); border-radius: 4px; padding: 8px 10px;
      font: inherit; min-height: 38px; }}
    button {{ background: var(--teal); border: 0; border-radius: 5px; color: #fff; cursor: pointer;
      font: inherit; padding: 8px 12px; }}
    button.secondary {{ background: #e8eef0; color: var(--ink); }}
    .search-results {{ display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 14px; }}
    .search-results:empty {{ display: none; }}
    .status {{ min-height: 20px; color: var(--muted); margin: 8px 0; }}
    section {{ margin-top: 20px; }}
    .panel {{ background: var(--panel); border: 1px solid var(--line); border-radius: 6px;
      padding: 16px; }}
    .summary {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }}
    .metric {{ border-left: 3px solid var(--teal); padding-left: 12px; }}
    .metric strong {{ display: block; font-size: 24px; margin-top: 4px; }}
    table {{ width: 100%; border-collapse: collapse; background: var(--panel); }}
    th, td {{ border-bottom: 1px solid var(--line); padding: 10px 12px; text-align: left; }}
    th {{ color: var(--muted); font-size: 12px; text-transform: uppercase; }}
    .long {{ color: var(--green); font-weight: 700; }}
    .short {{ color: var(--red); font-weight: 700; }}
    .no-trade, .muted {{ color: var(--muted); }}
    .watchlist-row {{ cursor: pointer; transition: background .15s ease; }}
    .watchlist-row:hover {{ background: #eef8f8; }}
    .watchlist-row.selected {{ background: #dff3f3; box-shadow: inset 3px 0 var(--teal); }}
    .market-panel {{ overflow: hidden; }}
    .market-heading {{ display: flex; justify-content: space-between; align-items: flex-start;
      gap: 16px; margin-bottom: 14px; }}
    .market-title {{ font-size: 20px; font-weight: 700; margin: 0 0 4px; }}
    .market-badges {{ display: flex; flex-wrap: wrap; gap: 8px; justify-content: flex-end; }}
    .pill {{ border-radius: 999px; padding: 5px 9px; font-size: 12px; font-weight: 700;
      background: #e8eef0; color: var(--muted); }}
    .pill.long {{ background: #e1f4e8; color: var(--green); }}
    .pill.short {{ background: #fde8e7; color: var(--red); }}
    .pill.wait {{ background: #eef1f3; color: var(--muted); }}
    .window-buttons {{ display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 14px; }}
    .window-button {{ background: #edf3f4; color: var(--ink); border: 1px solid transparent;
      padding: 7px 9px; font-size: 12px; }}
    .window-button:hover, .window-button.active {{ background: var(--teal); color: #fff; }}
    .chart-summary {{ display: grid; grid-template-columns: repeat(5, minmax(0, 1fr));
      gap: 10px; margin-bottom: 14px; }}
    .chart-stat {{ border-left: 3px solid var(--teal); padding: 6px 0 6px 10px; }}
    .chart-stat span {{ display: block; color: var(--muted); font-size: 11px; text-transform: uppercase; }}
    .chart-stat strong {{ display: block; margin-top: 3px; font-size: 16px; }}
    .chart-wrap {{ width: 100%; min-height: 340px; border: 1px solid var(--line); background: #fbfcfc; }}
    #market-chart {{ display: block; width: 100%; height: 340px; }}
    .chart-legend {{ display: flex; flex-wrap: wrap; gap: 12px; margin-top: 10px; color: var(--muted);
      font-size: 12px; }}
    .legend-item::before {{ content: ""; display: inline-block; width: 22px; height: 3px;
      vertical-align: middle; margin-right: 5px; background: var(--teal); }}
    .legend-item.forecast::before {{ background: var(--amber); }}
    .legend-item.target::before {{ background: var(--green); }}
    .legend-item.stop::before {{ background: var(--red); }}
    .forecast-note {{ color: var(--muted); font-size: 12px; margin-top: 10px; }}
    .market-empty {{ color: var(--muted); padding: 70px 16px; text-align: center; }}
    @media (max-width: 760px) {{ header {{ align-items: flex-start; flex-direction: column; }}
      main {{ padding: 14px; }} .summary {{ grid-template-columns: 1fr; }}
      .panel {{ overflow-x: auto; }} table {{ min-width: 680px; }}
      .market-heading {{ flex-direction: column; }} .market-badges {{ justify-content: flex-start; }}
      .chart-summary {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .window-buttons {{ min-width: 620px; }} }}
  </style>
</head>
<body>
  <header>
    <div><h1>Market Sentinel AI</h1><div class="meta">Operational dashboard</div></div>
    <div class="toolbar"><span class="meta">{escape(environment)} -
      {escape(generated_at_iso)}</span>
      <button type="button" onclick="window.location.reload()">Refresh</button></div>
  </header>
  <main>
    <div class="summary">
      {_operational_metric("Persisted signals", str(len(signals)))}
      {_operational_metric("Alert records", str(len(alerts)))}
      {_operational_metric(
          "Actionable signals",
          str(sum(signal.direction.value != "NO_TRADE" for signal in signals))
      )}
      {_operational_metric("Estimated PnL", _format_money(risk_metrics.get("estimated_pnl")))}
      {_operational_metric("Realized PnL", _format_money(risk_metrics.get("realized_pnl")))}
      {_operational_metric("VaR 95%", _format_money(risk_metrics.get("var_95")))}
      {_operational_metric("Max Drawdown", _format_percent(risk_metrics.get("max_drawdown_pct")))}
    </div>
    <section><div class="panel"><h2>Watchlist</h2>
      <form class="searchbar" id="instrument-search">
        <input id="instrument-query" type="search" placeholder="Search symbol or name"
          aria-label="Search symbol or name">
        <select id="instrument-class" aria-label="Asset class">
          <option value="">All asset classes</option>
          <option value="equity">Equities</option>
          <option value="etf">ETFs</option>
          <option value="crypto">Crypto</option>
          <option value="commodity">Commodities</option>
          <option value="fx">FX</option>
          <option value="index">Indices</option>
        </select>
        <select id="instrument-source" aria-label="Search source">
          <option value="auto">Local + provider</option>
          <option value="local">Local catalog</option>
          <option value="provider">Provider only</option>
        </select>
        <button type="submit">Search</button>
        <button type="button" class="secondary" id="scan-watchlist">Scan now</button>
      </form>
      <div id="instrument-results" class="search-results" aria-live="polite"></div>
      <div id="watchlist-status" class="status" aria-live="polite"></div>
      <table><thead><tr><th>Symbol</th><th>Name</th><th>Class</th><th>Exchange</th><th></th></tr>
      </thead><tbody id="watchlist-rows">{watchlist_rows}</tbody></table>
    </div></section>
    <section><div class="panel market-panel" id="market-detail">
      <div class="market-heading">
        <div><h2 class="market-title" id="market-title">Selecciona un producto</h2>
          <div class="meta" id="market-meta">Haz clic en una fila de la watchlist para cargar su análisis.</div>
        </div>
        <div class="market-badges"><span class="pill wait" id="market-action">SIN SEÑAL</span>
          <span class="pill" id="market-source">-</span></div>
      </div>
      <div class="window-buttons" id="window-buttons">{window_buttons}</div>
      <div class="chart-summary" id="market-summary">
        <div class="chart-stat"><span>Último</span><strong>-</strong></div>
        <div class="chart-stat"><span>Cambio ventana</span><strong>-</strong></div>
        <div class="chart-stat"><span>Confianza</span><strong>-</strong></div>
        <div class="chart-stat"><span>Entrada</span><strong>-</strong></div>
        <div class="chart-stat"><span>Objetivo / stop</span><strong>-</strong></div>
      </div>
      <div class="chart-wrap"><canvas id="market-chart" height="340" aria-label="Gráfico de mercado"></canvas>
        <div class="market-empty" id="market-empty">No hay un activo seleccionado.</div></div>
      <div class="chart-legend"><span class="legend-item">Histórico</span>
        <span class="legend-item forecast">Escenario futuro aprox.</span>
        <span class="legend-item target">Objetivo</span><span class="legend-item stop">Stop</span></div>
      <div class="forecast-note" id="market-disclaimer">Las líneas futuras aparecerán al seleccionar un activo.</div>
    </div></section>
    <section><div class="panel"><h2>Latest signals</h2>
      <table><thead><tr><th>Symbol</th><th>Timeframe</th><th>Direction</th><th>Confidence</th>
        <th>Model</th><th>Generated</th></tr></thead><tbody>{signal_rows}</tbody></table>
    </div></section>
    <section><div class="panel"><h2>Alert history</h2>
      <table><thead><tr><th>Channel</th><th>Status</th><th>External ID</th><th>Created</th>
        <th>Error</th>
        </tr></thead><tbody>{alert_rows}</tbody></table>
    </div></section>
  </main>
  <script>
    const status = document.getElementById('watchlist-status');
    const results = document.getElementById('instrument-results');
    const rows = document.getElementById('watchlist-rows');
    const query = document.getElementById('instrument-query');
    const assetClass = document.getElementById('instrument-class');
    const source = document.getElementById('instrument-source');
    const marketTitle = document.getElementById('market-title');
    const marketMeta = document.getElementById('market-meta');
    const marketAction = document.getElementById('market-action');
    const marketSource = document.getElementById('market-source');
    const marketSummary = document.getElementById('market-summary');
    const marketCanvas = document.getElementById('market-chart');
    const marketEmpty = document.getElementById('market-empty');
    const marketDisclaimer = document.getElementById('market-disclaimer');
    const defaultSymbol = "{escape(default_symbol)}";
    let selectedSymbol = defaultSymbol;
    let selectedWindow = '1d';

    function setStatus(message) {{ status.textContent = message; }}

    function formatPrice(value) {{
      return typeof value === 'number' ? value.toLocaleString(undefined, {{maximumFractionDigits: 6}}) : '-';
    }}

    function formatPercent(value) {{
      return typeof value === 'number' ? `${{value >= 0 ? '+' : ''}}${{value.toFixed(2)}}%` : '-';
    }}

    function formatConfidence(value) {{
      return typeof value === 'number' ? `${{(value * 100).toFixed(1)}}%` : '-';
    }}

    function setSummary(payload) {{
      const levels = payload.levels || {{}};
      const signal = payload.signal || {{}};
      const values = [
        formatPrice(payload.latest && payload.latest.close),
        formatPercent(payload.change_pct),
        formatConfidence(signal.confidence),
        formatPrice(levels.entry),
        `${{formatPrice(levels.target)}} / ${{formatPrice(levels.stop)}}`
      ];
      [...marketSummary.querySelectorAll('strong')].forEach((node, index) => {{
        node.textContent = values[index];
      }});
    }}

    function drawMarketChart(payload) {{
      const historical = payload.candles || [];
      const future = (payload.forecast && payload.forecast.center) || [];
      const upper = (payload.forecast && payload.forecast.upper) || [];
      const lower = (payload.forecast && payload.forecast.lower) || [];
      if (!historical.length) return;
      const rect = marketCanvas.getBoundingClientRect();
      const width = Math.max(640, Math.floor(rect.width || 900));
      const height = 340;
      const dpr = window.devicePixelRatio || 1;
      marketCanvas.width = width * dpr; marketCanvas.height = height * dpr;
      const ctx = marketCanvas.getContext('2d');
      ctx.scale(dpr, dpr);
      const left = 56, right = 18, top = 18, bottom = 32;
      const plotWidth = width - left - right, plotHeight = height - top - bottom;
      const allValues = historical.flatMap((item) => [item.high, item.low]).concat(
        upper.map((item) => item.value), lower.map((item) => item.value));
      const minimum = Math.min(...allValues), maximum = Math.max(...allValues);
      const padding = Math.max((maximum - minimum) * 0.08, maximum * 0.001);
      const minValue = minimum - padding, maxValue = maximum + padding;
      const total = Math.max(2, historical.length + future.length - 1);
      const x = (index) => left + (index / (total - 1)) * plotWidth;
      const y = (value) => top + ((maxValue - value) / (maxValue - minValue)) * plotHeight;
      ctx.clearRect(0, 0, width, height); ctx.fillStyle = '#fbfcfc'; ctx.fillRect(0, 0, width, height);
      ctx.font = '11px Segoe UI, Arial'; ctx.strokeStyle = '#e2e8eb'; ctx.fillStyle = '#5e6a72';
      for (let index = 0; index <= 4; index += 1) {{
        const yy = top + (index / 4) * plotHeight;
        ctx.beginPath(); ctx.moveTo(left, yy); ctx.lineTo(width - right, yy); ctx.stroke();
        const label = maxValue - (index / 4) * (maxValue - minValue);
        ctx.fillText(formatPrice(label), 6, yy + 4);
      }}
      const line = (points, color, dashed = false, startIndex = 0) => {{
        if (!points.length) return;
        ctx.beginPath(); ctx.setLineDash(dashed ? [6, 5] : []); ctx.strokeStyle = color; ctx.lineWidth = 2;
        points.forEach((item, index) => {{
          const xx = x(startIndex + index); const yy = y(item.value);
          if (index === 0) ctx.moveTo(xx, yy); else ctx.lineTo(xx, yy);
        }}); ctx.stroke(); ctx.setLineDash([]);
      }};
      line(historical.map((item) => ({{value: item.close}})), '#087f8c');
      if (upper.length && lower.length) {{
        ctx.beginPath(); ctx.fillStyle = 'rgba(183, 121, 31, 0.14)';
        upper.forEach((item, index) => {{ const xx = x(historical.length - 1 + index); const yy = y(item.value);
          if (index === 0) ctx.moveTo(xx, yy); else ctx.lineTo(xx, yy); }});
        [...lower].reverse().forEach((item, index) => {{ const xx = x(historical.length - 1 + lower.length - 1 - index);
          ctx.lineTo(xx, y(item.value)); }}); ctx.closePath(); ctx.fill();
        line(upper, '#b7791f', true, historical.length - 1);
        line(lower, '#b7791f', true, historical.length - 1);
        line(future, '#b7791f', true, historical.length - 1);
      }}
      const horizontal = (value, color, label) => {{
        if (typeof value !== 'number') return;
        ctx.beginPath(); ctx.setLineDash([4, 4]); ctx.strokeStyle = color; ctx.lineWidth = 1;
        ctx.moveTo(left, y(value)); ctx.lineTo(width - right, y(value)); ctx.stroke(); ctx.setLineDash([]);
        ctx.fillStyle = color; ctx.fillText(`${{label}} ${{formatPrice(value)}}`, width - 150, y(value) - 5);
      }};
      horizontal(payload.levels && payload.levels.entry, '#2563eb', 'Entrada');
      horizontal(payload.levels && payload.levels.target, '#16803c', 'Objetivo');
      horizontal(payload.levels && payload.levels.stop, '#b42318', 'Stop');
    }}

    function markSelectedRow(symbol) {{
      document.querySelectorAll('.watchlist-row').forEach((row) => {{
        row.classList.toggle('selected', row.dataset.symbol === symbol);
      }});
    }}

    async function loadMarket(symbol, windowValue) {{
      if (!symbol) return;
      selectedSymbol = symbol; selectedWindow = windowValue; markSelectedRow(symbol);
      document.querySelectorAll('.window-button').forEach((button) => {{
        button.classList.toggle('active', button.dataset.window === windowValue);
      }});
      marketMeta.textContent = 'Cargando velas, señal y escenario...';
      const response = await fetch(`/api/v1/market/${{encodeURIComponent(symbol)}}?window=${{windowValue}}`);
      if (!response.ok) {{ marketMeta.textContent = 'No hay datos para este intervalo.'; return; }}
      const payload = await response.json();
      marketTitle.textContent = `${{payload.symbol}} · ${{payload.name}}`;
      marketMeta.textContent = `${{payload.window_label}} · ${{payload.candle_count}} velas · ` +
        `${{payload.timeframe}} · ${{payload.currency}}`;
      marketAction.textContent = payload.signal.action;
      marketAction.className = 'pill ' + (payload.signal.direction === 'LONG' ? 'long' :
        payload.signal.direction === 'SHORT' ? 'short' : 'wait');
      marketSource.textContent = `${{payload.source === 'provider' ? 'Proveedor' : 'Caché local'}} · ${{payload.provider}}`;
      setSummary(payload); marketDisclaimer.textContent = payload.disclaimer;
      marketCanvas.style.display = 'block'; marketEmpty.style.display = 'none'; drawMarketChart(payload);
    }}

    function addSearchButton(item) {{
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'secondary';
      button.textContent = `Add ${{item.symbol}}`;
      button.title = `${{item.name}} (${{item.asset_class}})`;
      button.addEventListener('click', async () => {{
        const response = await fetch('/api/v1/watchlist', {{
          method: 'POST', headers: {{'Content-Type': 'application/json'}},
          body: JSON.stringify({{symbol: item.symbol, name: item.name,
            asset_class: item.asset_class, exchange: item.exchange,
            currency: item.currency, provider_symbol: item.provider_symbol}})
        }});
        setStatus(response.ok ? `${{item.symbol}} added to watchlist` : 'Could not add instrument');
        if (response.ok) window.location.reload();
      }});
      results.appendChild(button);
    }}

    async function searchInstruments(event) {{
      if (event) event.preventDefault();
      const params = new URLSearchParams({{q: query.value, asset_class: assetClass.value,
        source: source.value}});
      const response = await fetch(`/api/v1/instruments?${{params}}`);
      results.replaceChildren();
      if (!response.ok) {{ setStatus('Search failed'); return; }}
      const items = await response.json();
      items.forEach(addSearchButton);
      setStatus(`${{items.length}} instruments found`);
    }}

    document.getElementById('instrument-search').addEventListener('submit', searchInstruments);
    document.querySelectorAll('.remove-instrument').forEach((button) => {{
      button.addEventListener('click', async (event) => {{
        event.stopPropagation();
        const symbol = button.dataset.symbol;
        const response = await fetch(
          `/api/v1/watchlist/${{encodeURIComponent(symbol)}}`, {{method: 'DELETE'}}
        );
        setStatus(
          response.ok ? `${{symbol}} removed from watchlist` : 'Could not remove instrument'
        );
        if (response.ok) window.location.reload();
      }});
    }});
    document.querySelectorAll('.watchlist-row').forEach((row) => {{
      row.addEventListener('click', (event) => {{
        if (event.target.closest('button')) return;
        loadMarket(row.dataset.symbol, selectedWindow);
      }});
    }});
    document.querySelectorAll('.window-button').forEach((button) => {{
      button.addEventListener('click', () => loadMarket(selectedSymbol, button.dataset.window));
    }});
    window.addEventListener('resize', () => {{
      if (selectedSymbol) loadMarket(selectedSymbol, selectedWindow);
    }});
    if (defaultSymbol) loadMarket(defaultSymbol, selectedWindow);
    document.getElementById('scan-watchlist').addEventListener('click', async () => {{
      setStatus('Scanning watchlist...');
      const response = await fetch('/api/v1/watchlist/scan', {{
        method: 'POST', headers: {{'Content-Type': 'application/json'}},
        body: JSON.stringify({{timeframe: '5m', days: 5}})
      }});
      setStatus(response.ok ? 'Scan completed; refresh to see new signals' : 'Scan failed');
    }});
  </script>
</body>
</html>
"""


def _operational_metric(label: str, value: str) -> str:
    return (
        f'<div class="panel metric"><span class="meta">{escape(label)}</span>'
        f"<strong>{escape(value)}</strong></div>"
    )


def _render_signal_record(signal: SignalRecord) -> str:
    direction = signal.direction.value
    return (
        "<tr>"
        f"<td>{escape(signal.symbol)}</td>"
        f"<td>{escape(signal.timeframe)}</td>"
        f'<td class="{direction.lower().replace("_", "-")}">{escape(direction)}</td>'
        f"<td>{signal.confidence:.2f}</td>"
        f"<td>{escape(signal.model_name)}</td>"
        f"<td>{escape(signal.generated_at.isoformat())}</td>"
        "</tr>"
    )


def _render_alert_record(alert: AlertRecord) -> str:
    return (
        "<tr>"
        f"<td>{escape(alert.channel)}</td>"
        f"<td>{escape(alert.status)}</td>"
        f'<td>{escape(alert.external_id or "-")}</td>'
        f"<td>{escape(alert.created_at.isoformat())}</td>"
        f'<td>{escape(alert.error or "-")}</td>'
        "</tr>"
    )


def _render_instrument_row(instrument: Instrument) -> str:
    return (
        f'<tr class="watchlist-row" data-symbol="{escape(instrument.symbol)}">'
        f"<td>{escape(instrument.symbol)}</td>"
        f"<td>{escape(instrument.name)}</td>"
        f"<td>{escape(instrument.asset_class.value)}</td>"
        f"<td>{escape(instrument.exchange)}</td>"
        f'<td><button type="button" class="secondary remove-instrument" '
        f'data-symbol="{escape(instrument.symbol)}">Remove</button></td>'
        "</tr>"
    )


def _format_money(value: object) -> str:
    return "-" if not isinstance(value, (float, int)) else f"{value:,.2f}"


def _format_percent(value: object) -> str:
    return "-" if not isinstance(value, (float, int)) else f"{value:.2f}%"
