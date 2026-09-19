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
    .static-report-note {{ background: #fff8e6; border-left: 3px solid var(--amber); padding: 10px 12px;
      color: #72520f; font-size: 13px; margin-bottom: 14px; }}
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
    <div class="static-report-note">Este es un informe estatico. Para usar la UI completa con
      watchlist, escaneo, graficos, riesgo, paper trading y diagnosticos, abre
      <a href="http://127.0.0.1:8765">http://127.0.0.1:8765</a> mediante
      <code>Open-Market-Sentinel.bat</code>.</div>
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
        '<tr><td colspan="6">Watchlist is empty</td></tr>'
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
    .control-heading {{ display: flex; justify-content: space-between; align-items: center;
      gap: 12px; margin-bottom: 12px; }}
    .control-grid {{ display: flex; flex-wrap: wrap; align-items: end; gap: 10px; }}
    .control-field {{ display: grid; gap: 5px; color: var(--muted); font-size: 12px; }}
    .control-field select, .control-field input {{ min-width: 115px; }}
    .operation-status {{ min-height: 20px; color: var(--muted); margin-top: 12px; }}
    .system-grid {{ display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 10px;
      margin-top: 14px; }}
    .system-item {{ border-left: 3px solid var(--line); padding-left: 10px; }}
    .system-item span {{ display: block; color: var(--muted); font-size: 11px; text-transform: uppercase; }}
    .system-item strong {{ display: block; margin-top: 4px; font-size: 15px; }}
    .system-item.ok {{ border-color: var(--green); }}
    .system-item.warn {{ border-color: var(--amber); }}
    .risk-grid {{ display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 10px; }}
    .risk-item {{ border-left: 3px solid var(--blue); padding: 6px 0 6px 10px; }}
    .risk-item span {{ display: block; color: var(--muted); font-size: 11px; text-transform: uppercase; }}
    .risk-item strong {{ display: block; margin-top: 4px; font-size: 16px; }}
    .data-layout {{ display: grid; grid-template-columns: minmax(0, 1.4fr) minmax(260px, 1fr); gap: 16px; }}
    .data-layout h3 {{ font-size: 14px; margin: 0 0 10px; }}
    .diagnostic-grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }}
    .diagnostic-item {{ border: 1px solid var(--line); padding: 10px; }}
    .diagnostic-item span {{ display: block; color: var(--muted); font-size: 11px; text-transform: uppercase; }}
    .diagnostic-item strong {{ display: block; margin-top: 4px; font-size: 15px; }}
    .diagnostic-item small {{ display: block; color: var(--muted); margin-top: 4px; }}
    .trade-table {{ max-height: 250px; overflow: auto; }}
    .trade-table table {{ min-width: 560px; }}
    .simulation-panel {{ border-top: 4px solid var(--blue); }}
    .simulation-heading {{ display: flex; justify-content: space-between; align-items: flex-start;
      gap: 16px; margin-bottom: 12px; }}
    .simulation-heading p {{ margin: 4px 0 0; color: var(--muted); font-size: 13px; max-width: 720px; }}
    .simulation-badge {{ background: #e7efff; color: #1d4ed8; border-radius: 4px;
      padding: 6px 9px; font-size: 11px; font-weight: 800; white-space: nowrap; }}
    .simulation-account-grid {{ display: grid; grid-template-columns: repeat(6, minmax(0, 1fr));
      gap: 10px; margin: 14px 0; }}
    .simulation-account-item {{ border-left: 3px solid var(--blue); padding: 6px 0 6px 10px; }}
    .simulation-account-item.positive {{ border-color: var(--green); }}
    .simulation-account-item.negative {{ border-color: var(--red); }}
    .simulation-account-item span {{ display: block; color: var(--muted); font-size: 11px;
      text-transform: uppercase; }}
    .simulation-account-item strong {{ display: block; margin-top: 4px; font-size: 16px; }}
    .simulation-controls {{ display: flex; flex-wrap: wrap; align-items: end; gap: 10px;
      padding: 12px; background: #f6f9ff; border: 1px solid #dbe6ff; }}
    .simulation-controls .control-field input {{ min-width: 130px; }}
    .simulation-direction {{ display: inline-flex; gap: 4px; }}
    .simulation-direction button {{ min-width: 96px; background: #eef1f3; color: var(--ink); }}
    .simulation-direction button.active-long {{ background: var(--green); color: #fff; }}
    .simulation-direction button.active-short {{ background: var(--red); color: #fff; }}
    .simulation-note {{ color: var(--muted); font-size: 12px; margin: 10px 0 0; }}
    .simulation-positions {{ margin-top: 16px; overflow: auto; }}
    .simulation-positions table {{ min-width: 820px; }}
    .simulation-pnl-positive {{ color: var(--green); font-weight: 700; }}
    .simulation-pnl-negative {{ color: var(--red); font-weight: 700; }}
    .static-report-note {{ background: #fff8e6; border-left: 3px solid var(--amber); padding: 10px 12px;
      color: #72520f; font-size: 13px; margin-bottom: 14px; }}
    table {{ width: 100%; border-collapse: collapse; background: var(--panel); }}
    th, td {{ border-bottom: 1px solid var(--line); padding: 10px 12px; text-align: left; }}
    th {{ color: var(--muted); font-size: 12px; text-transform: uppercase; }}
    .long {{ color: var(--green); font-weight: 700; }}
    .short {{ color: var(--red); font-weight: 700; }}
    .no-trade, .muted {{ color: var(--muted); }}
    .watchlist-row {{ cursor: pointer; transition: background .15s ease; }}
    .watchlist-row:hover {{ background: #eef8f8; }}
    .watchlist-row.selected {{ background: #dff3f3; box-shadow: inset 3px 0 var(--teal); }}
    .watchlist-row.long-row {{ background: #f0fbf3; box-shadow: inset 4px 0 var(--green); }}
    .watchlist-row.short-row {{ background: #fff3f2; box-shadow: inset 4px 0 var(--red); }}
    .watchlist-row.wait-row {{ box-shadow: inset 4px 0 var(--line); }}
    .watchlist-direction {{ display: inline-flex; min-width: 82px; justify-content: center;
      border-radius: 4px; padding: 5px 8px; font-size: 11px; font-weight: 800;
      letter-spacing: .02em; background: #eef1f3; color: var(--muted); }}
    .watchlist-direction.long {{ background: #d9f5e2; color: #126b32; }}
    .watchlist-direction.short {{ background: #ffe0de; color: #a51f15; }}
    .watchlist-direction.wait {{ background: #eef1f3; color: var(--muted); }}
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
    .pill.demo {{ background: #fff8e6; color: #72520f; }}
    .window-buttons {{ display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 14px; }}
    .window-button {{ background: #edf3f4; color: var(--ink); border: 1px solid transparent;
      padding: 7px 9px; font-size: 12px; }}
    .window-button:hover, .window-button.active {{ background: var(--teal); color: #fff; }}
    .chart-toolbar {{ display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-bottom: 12px; }}
    .chart-mode-buttons {{ display: inline-flex; gap: 4px; }}
    .chart-mode-button {{ background: #edf3f4; color: var(--ink); border: 1px solid var(--line);
      padding: 6px 10px; font-size: 12px; }}
    .chart-mode-button:hover, .chart-mode-button.active {{ background: var(--ink); color: #fff; }}
    .chart-summary {{ display: grid; grid-template-columns: repeat(5, minmax(0, 1fr));
      gap: 10px; margin-bottom: 14px; }}
    .chart-stat {{ border-left: 3px solid var(--teal); padding: 6px 0 6px 10px; }}
    .chart-stat span {{ display: block; color: var(--muted); font-size: 11px; text-transform: uppercase; }}
    .chart-stat strong {{ display: block; margin-top: 3px; font-size: 16px; }}
    .trade-levels {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 10px; margin: -2px 0 14px; }}
    .level-card {{ border: 1px solid var(--line); border-left: 5px solid var(--blue);
      background: #f7fbff; padding: 9px 12px; min-width: 0; }}
    .level-card.target {{ border-left-color: var(--green); background: #f3fbf5; }}
    .level-card.stop {{ border-left-color: var(--red); background: #fff6f5; }}
    .level-card span {{ display: block; color: var(--muted); font-size: 11px; font-weight: 700;
      text-transform: uppercase; }}
    .level-card strong {{ display: block; margin-top: 4px; font-size: 19px; white-space: nowrap;
      overflow: hidden; text-overflow: ellipsis; }}
    .chart-wrap {{ width: 100%; min-height: 340px; border: 1px solid var(--line); background: #fbfcfc; }}
    .chart-wrap {{ position: relative; }}
    #market-chart {{ display: block; width: 100%; height: 340px; }}
    .chart-tooltip {{ position: absolute; z-index: 3; pointer-events: none; white-space: pre-line;
      max-width: 230px; padding: 8px 10px; border: 1px solid #183b45; border-radius: 4px;
      background: rgba(24, 32, 38, .96); color: #fff; font-size: 12px; line-height: 1.45;
      box-shadow: 0 4px 12px rgba(24, 32, 38, .18); }}
    .chart-legend {{ display: flex; flex-wrap: wrap; gap: 12px; margin-top: 10px; color: var(--muted);
      font-size: 12px; }}
    .legend-item::before {{ content: ""; display: inline-block; width: 22px; height: 3px;
      vertical-align: middle; margin-right: 5px; background: var(--teal); }}
    .legend-item.forecast::before {{ background: var(--amber); }}
    .legend-item.target::before {{ background: var(--green); }}
    .legend-item.stop::before {{ background: var(--red); }}
    .forecast-note {{ color: var(--muted); font-size: 12px; margin-top: 10px; }}
    .decision-note {{ border-left: 4px solid var(--amber); background: #fff8e6; color: #72520f;
      padding: 10px 12px; margin-bottom: 12px; font-size: 13px; font-weight: 600; }}
    .decision-note.long {{ border-left-color: var(--green); background: #e1f4e8; color: #166534; }}
    .decision-note.short {{ border-left-color: var(--red); background: #fde8e7; color: #991b1b; }}
    .explanation-box {{ border: 1px solid var(--line); border-left: 4px solid var(--amber);
      background: #fffdf7; padding: 12px 14px; margin-bottom: 12px; }}
    .explanation-box.long {{ border-left-color: var(--green); background: #f5fcf6; }}
    .explanation-box.short {{ border-left-color: var(--red); background: #fff7f6; }}
    .explanation-box h3 {{ font-size: 14px; margin: 0 0 5px; }}
    .explanation-box p {{ margin: 0; font-size: 13px; line-height: 1.45; }}
    .explanation-grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 16px; margin-top: 12px; }}
    .explanation-column > span {{ color: var(--muted); font-size: 11px; font-weight: 800;
      text-transform: uppercase; }}
    .explanation-column ul {{ margin: 6px 0 0; padding-left: 18px; font-size: 12px; line-height: 1.5; }}
    .explanation-warnings {{ color: #72520f; margin-top: 10px !important; }}
    .market-empty {{ color: var(--muted); padding: 70px 16px; text-align: center; }}
    @media (max-width: 760px) {{ header {{ align-items: flex-start; flex-direction: column; }}
      main {{ padding: 14px; }} .summary {{ grid-template-columns: 1fr; }}
      .panel {{ overflow-x: auto; }} table {{ min-width: 680px; }}
      .market-heading {{ flex-direction: column; }} .market-badges {{ justify-content: flex-start; }}
      .chart-summary, .trade-levels {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .explanation-grid {{ grid-template-columns: 1fr; }}
      .window-buttons {{ min-width: 620px; }} .system-grid, .risk-grid, .simulation-account-grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .data-layout {{ grid-template-columns: 1fr; }} .diagnostic-grid {{ grid-template-columns: 1fr; }} }}
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
    <section><div class="panel">
      <div class="control-heading"><h2>Centro de control</h2>
        <span class="pill wait" id="real-orders-badge">ORDENES REALES DESACTIVADAS</span></div>
      <div class="control-grid">
        <label class="control-field">Timeframe de escaneo
          <select id="scan-timeframe"><option value="1m">1 minuto</option>
            <option value="5m" selected>5 minutos</option><option value="15m">15 minutos</option>
            <option value="1h">1 hora</option><option value="1d">1 día</option></select>
        </label>
        <label class="control-field">Historial a revisar
          <input id="scan-days" type="number" min="1" max="3650" value="5"></label>
        <button type="button" id="scan-watchlist">Escanear watchlist</button>
        <label class="control-field">Escaneo periódico
          <select id="scan-interval"><option value="0">Desactivado</option>
            <option value="60000">Cada 1 minuto</option><option value="300000">Cada 5 minutos</option>
            <option value="900000">Cada 15 minutos</option><option value="3600000">Cada hora</option></select>
        </label>
        <button type="button" class="secondary" id="scan-periodic">Activar periódico</button>
        <button type="button" class="secondary" id="refresh-live">Actualizar datos</button>
      </div>
      <div class="operation-status" id="operation-status" aria-live="polite">Listo para analizar la watchlist.</div>
      <div class="system-grid">
        <div class="system-item" id="system-health"><span>Servicio</span><strong id="live-service">Cargando</strong></div>
        <div class="system-item"><span>Proveedor</span><strong id="live-provider">-</strong></div>
        <div class="system-item"><span>Watchlist</span><strong id="live-watchlist">-</strong></div>
        <div class="system-item"><span>Último escaneo</span><strong id="live-scan">-</strong></div>
        <div class="system-item"><span>Cuenta paper</span><strong id="live-equity">-</strong></div>
      </div>
    </div></section>
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
      </form>
      <div id="instrument-results" class="search-results" aria-live="polite"></div>
      <div id="watchlist-status" class="status" aria-live="polite"></div>
      <table><thead><tr><th>Symbol</th><th>Name</th><th>Class</th><th>Exchange</th><th>Lectura</th><th></th></tr>
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
      <div class="chart-toolbar">
        <span class="meta">Representación</span>
        <div class="chart-mode-buttons" id="chart-mode-buttons">
          <button type="button" class="chart-mode-button active" data-chart-mode="line">Línea</button>
          <button type="button" class="chart-mode-button" data-chart-mode="candles">Velas OHLC</button>
        </div>
      </div>
      <div class="chart-summary" id="market-summary">
        <div class="chart-stat"><span>Último</span><strong>-</strong></div>
        <div class="chart-stat"><span>Cambio ventana</span><strong>-</strong></div>
        <div class="chart-stat"><span>Dirección</span><strong>-</strong></div>
        <div class="chart-stat"><span>Confianza</span><strong>-</strong></div>
        <div class="chart-stat"><span>Predicción central</span><strong>-</strong></div>
      </div>
      <div class="trade-levels" id="trade-levels">
        <div class="level-card entry"><span>Entrada de referencia</span><strong id="level-entry">-</strong></div>
        <div class="level-card target"><span>Objetivo estimado</span><strong id="level-target">-</strong></div>
        <div class="level-card stop"><span>Stop / invalidación</span><strong id="level-stop">-</strong></div>
      </div>
      <div class="decision-note" id="market-decision" aria-live="polite">
        Selecciona un activo para obtener una lectura direccional.
      </div>
      <div class="explanation-box" id="market-explanation">
        <h3>Por qué el modelo marca esta lectura</h3>
        <p id="explanation-summary">Selecciona un activo para ver los factores cuantitativos que pesan en la decisión.</p>
        <div class="explanation-grid">
          <div class="explanation-column"><span>Indicadores que pesan</span>
            <ul id="explanation-drivers"><li>Aún no hay datos de análisis.</li></ul></div>
          <div class="explanation-column"><span>Entrada, objetivo y stop</span>
            <ul id="explanation-levels"><li>Aún no hay un plan para este activo.</li></ul></div>
        </div>
        <ul class="explanation-warnings" id="explanation-warnings"><li>La explicación aparecerá al cargar datos frescos.</li></ul>
      </div>
      <div class="chart-wrap"><canvas id="market-chart" height="340" aria-label="Gráfico de mercado"></canvas>
        <div id="chart-tooltip" class="chart-tooltip" role="status" hidden></div>
        <div class="market-empty" id="market-empty">No hay un activo seleccionado.</div></div>
      <div class="chart-legend"><span class="legend-item">Histórico</span>
        <span class="legend-item forecast" id="forecast-label">Rango futuro aprox.</span>
        <span class="legend-item target">Objetivo</span><span class="legend-item stop">Stop</span></div>
      <div class="forecast-note" id="market-disclaimer">Las líneas futuras aparecerán al seleccionar un activo.</div>
    </div></section>
    <section><div class="panel">
      <h2>Paper trading y riesgo</h2>
      <div class="risk-grid" id="paper-metrics">
        <div class="risk-item"><span>PnL estimado</span><strong data-metric="estimated_pnl">-</strong></div>
        <div class="risk-item"><span>PnL realizado</span><strong data-metric="realized_pnl">-</strong></div>
        <div class="risk-item"><span>PnL total</span><strong data-metric="total_pnl">-</strong></div>
        <div class="risk-item"><span>VaR 95%</span><strong data-metric="var_95">-</strong></div>
        <div class="risk-item"><span>CVaR 95%</span><strong data-metric="cvar_95">-</strong></div>
        <div class="risk-item"><span>Volatilidad</span><strong data-metric="volatility_pct">-</strong></div>
        <div class="risk-item"><span>Sharpe</span><strong data-metric="sharpe">-</strong></div>
        <div class="risk-item"><span>Sortino</span><strong data-metric="sortino">-</strong></div>
        <div class="risk-item"><span>Max drawdown</span><strong data-metric="max_drawdown_pct">-</strong></div>
        <div class="risk-item"><span>Profit factor</span><strong data-metric="profit_factor">-</strong></div>
        <div class="risk-item"><span>Win rate</span><strong data-metric="win_rate">-</strong></div>
        <div class="risk-item"><span>Expectancy</span><strong data-metric="expectancy">-</strong></div>
        <div class="risk-item"><span>Exposición</span><strong data-metric="exposure">-</strong></div>
        <div class="risk-item"><span>Operaciones</span><strong data-metric="trades">-</strong></div>
        <div class="risk-item"><span>Muestra VaR</span><strong data-metric="sample_size">-</strong></div>
      </div>
      <div class="data-layout" style="margin-top: 18px;">
        <div><h3>Operaciones simuladas</h3><div class="trade-table">
          <table><thead><tr><th>Symbol</th><th>Dirección</th><th>Entrada</th><th>Salida</th><th>PnL</th></tr></thead>
          <tbody id="paper-trades-rows"><tr><td colspan="5" class="muted">Cargando operaciones paper...</td></tr></tbody></table>
        </div></div>
        <div><h3>Cuenta paper</h3><div class="diagnostic-grid">
          <div class="diagnostic-item"><span>Capital inicial</span><strong id="paper-starting-equity">-</strong></div>
          <div class="diagnostic-item"><span>Equity actual</span><strong id="paper-current-equity">-</strong></div>
          <div class="diagnostic-item"><span>Estado</span><strong id="paper-execution-state">Solo simulación</strong></div>
          <div class="diagnostic-item"><span>Actualizada</span><strong id="paper-updated-at">-</strong></div>
        </div></div>
      </div>
    </div></section>
    <section><div class="panel simulation-panel">
      <div class="simulation-heading">
        <div><h2>Modo simulación</h2>
          <p>Opera con saldo virtual usando datos de mercado. El margen es el importe que reservas;
            el apalancamiento amplía la exposición y los costes simulados se descuentan del PnL.</p>
        </div>
        <span class="simulation-badge">SIMULACIÓN · SIN ÓRDENES REALES</span>
      </div>
      <div class="simulation-account-grid">
        <div class="simulation-account-item"><span>Capital inicial</span><strong id="sim-starting-equity">-</strong></div>
        <div class="simulation-account-item"><span>Saldo disponible</span><strong id="sim-cash-balance">-</strong></div>
        <div class="simulation-account-item"><span>Equity</span><strong id="sim-equity">-</strong></div>
        <div class="simulation-account-item"><span>Margen disponible</span><strong id="sim-available-margin">-</strong></div>
        <div class="simulation-account-item"><span>PnL no realizado</span><strong id="sim-unrealized-pnl">-</strong></div>
        <div class="simulation-account-item"><span>PnL realizado</span><strong id="sim-realized-pnl">-</strong></div>
        <div class="simulation-account-item"><span>PnL total</span><strong id="sim-total-pnl">-</strong></div>
        <div class="simulation-account-item"><span>Exposición</span><strong id="sim-exposure">-</strong></div>
        <div class="simulation-account-item"><span>VaR 95%</span><strong id="sim-var95">-</strong></div>
        <div class="simulation-account-item"><span>CVaR 95%</span><strong id="sim-cvar95">-</strong></div>
        <div class="simulation-account-item"><span>Max drawdown</span><strong id="sim-max-drawdown">-</strong></div>
      </div>
      <div class="simulation-controls">
        <label class="control-field">Activo seleccionado
          <input id="sim-symbol" type="text" value="" readonly></label>
        <label class="control-field">Margen a usar
          <input id="sim-margin" type="number" min="1" step="0.01" value="1000"></label>
        <label class="control-field">Apalancamiento
          <select id="sim-leverage"><option value="1">1x</option><option value="2">2x</option>
            <option value="3">3x</option><option value="5" selected>5x</option><option value="10">10x</option></select>
        </label>
        <div class="control-field"><span>Dirección</span>
          <div class="simulation-direction"><button type="button" id="sim-long" class="active-long">LONG</button>
            <button type="button" id="sim-short">SHORT</button></div>
        </div>
        <button type="button" id="sim-open">Abrir posición</button>
        <label class="control-field">Nuevo capital inicial
          <input id="sim-reset-equity" type="number" min="1" step="0.01" value="100000"></label>
        <button type="button" class="secondary" id="sim-reset">Reiniciar simulación</button>
      </div>
      <div class="simulation-note" id="sim-status" aria-live="polite">
        Selecciona un activo y abre una posición simulada. La cuenta se actualiza periódicamente.
      </div>
      <div class="simulation-positions"><h3>Posiciones abiertas</h3>
        <table><thead><tr><th>Activo</th><th>Dirección</th><th>Margen</th><th>Apalancamiento</th>
          <th>Entrada</th><th>Precio actual</th><th>PnL</th><th>Liquidación aprox.</th><th></th></tr></thead>
          <tbody id="sim-positions-rows"><tr><td colspan="9" class="muted">No hay posiciones abiertas.</td></tr></tbody></table>
      </div>
      <div class="simulation-positions"><h3>Historial de simulación</h3>
        <table><thead><tr><th>Activo</th><th>Dirección</th><th>Entrada</th><th>Salida</th><th>PnL</th><th>Cierre</th></tr></thead>
          <tbody id="sim-trades-rows"><tr><td colspan="6" class="muted">Aún no hay operaciones cerradas.</td></tr></tbody></table>
      </div>
    </div></section>
    <section><div class="panel">
      <h2>Salud, drift y contexto</h2>
      <div class="diagnostic-grid">
        <div class="diagnostic-item"><span>Salud de la aplicacion</span><strong id="health-status">Cargando</strong><small id="health-detail">-</small></div>
        <div class="diagnostic-item"><span>Modelo cuantitativo</span><strong id="model-status">Cargando</strong><small id="model-detail">-</small></div>
        <div class="diagnostic-item"><span>Drift de modelo</span><strong id="drift-status">Cargando</strong><small id="drift-detail">-</small></div>
        <div class="diagnostic-item"><span>Uso de Astra</span><strong id="astra-usage">Cargando</strong><small id="astra-cost">-</small></div>
        <div class="diagnostic-item"><span>Ultima ejecucion</span><strong id="run-status">Cargando</strong><small id="run-detail">-</small></div>
      </div>
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
    const chartWrap = document.querySelector('.chart-wrap');
    const chartTooltip = document.getElementById('chart-tooltip');
    const marketEmpty = document.getElementById('market-empty');
    const marketDisclaimer = document.getElementById('market-disclaimer');
    const marketDecision = document.getElementById('market-decision');
    const marketExplanation = document.getElementById('market-explanation');
    const explanationSummary = document.getElementById('explanation-summary');
    const explanationDrivers = document.getElementById('explanation-drivers');
    const explanationLevels = document.getElementById('explanation-levels');
    const explanationWarnings = document.getElementById('explanation-warnings');
    const forecastLabel = document.getElementById('forecast-label');
    const defaultSymbol = "{escape(default_symbol)}";
    let selectedSymbol = defaultSymbol;
    let selectedWindow = '1d';
    let chartMode = 'line';
    let periodicTimer = null;
    let marketRequestId = 0;
    let lastChartPayload = null;
    let chartLayout = null;
    let chartHoverIndex = null;
    const operationStatus = document.getElementById('operation-status');
    const scanTimeframe = document.getElementById('scan-timeframe');
    const scanDays = document.getElementById('scan-days');
    const scanInterval = document.getElementById('scan-interval');
    const periodicButton = document.getElementById('scan-periodic');
    const realOrdersBadge = document.getElementById('real-orders-badge');
    const simulationStatus = document.getElementById('sim-status');
    const simulationSymbol = document.getElementById('sim-symbol');
    const simulationLong = document.getElementById('sim-long');
    const simulationShort = document.getElementById('sim-short');
    let simulationDirection = 'LONG';
    let simulationTimer = null;

    function setOperationStatus(message) {{ operationStatus.textContent = message; }}

    function safeText(value) {{
      return value === null || value === undefined || value === '' ? '-' : String(value);
    }}

    function formatMoneyValue(value) {{
      return typeof value === 'number' ? value.toLocaleString(undefined, {{maximumFractionDigits: 2}}) : '-';
    }}

    function formatMetric(name, value) {{
      if (value === null || value === undefined) return '-';
      if (name.endsWith('_pct') || name === 'win_rate') return `${{Number(value).toFixed(2)}}%`;
      if (name === 'estimated_pnl' || name === 'realized_pnl' || name === 'unrealized_pnl' ||
          name === 'total_pnl' || name === 'var_95' || name === 'cvar_95' || name === 'exposure')
        return formatMoneyValue(Number(value));
      if (typeof value === 'number') return Number.isInteger(value) ? String(value) : Number(value).toFixed(2);
      return String(value);
    }}

    async function fetchJson(url) {{
      const response = await fetch(url);
      return response.ok ? response.json() : null;
    }}

    async function loadOperationalData() {{
      const [statusData, summaryData, accountData, metricsData, healthData, modelData, driftData, astraData, tradesData] =
        await Promise.all([
          fetchJson('/api/v1/status'), fetchJson('/api/v1/operations/summary'),
          fetchJson('/api/v1/paper/account'), fetchJson('/api/v1/paper/metrics'),
          fetchJson('/api/v1/health/details'), fetchJson('/api/v1/model-status'),
          fetchJson('/api/v1/drift?limit=1'),
          fetchJson('/api/v1/astra-usage'), fetchJson('/api/v1/paper/trades?limit=50')
        ]);
      if (statusData) {{
        document.getElementById('live-service').textContent = `${{statusData.release}} · ${{statusData.version}}`;
        document.getElementById('live-provider').textContent = safeText(statusData.provider);
        realOrdersBadge.textContent = statusData.real_orders_enabled ? 'ORDENES REALES ACTIVAS' : 'ORDENES REALES DESACTIVADAS';
        realOrdersBadge.className = statusData.real_orders_enabled ? 'pill short' : 'pill wait';
      }}
      if (summaryData) {{
        document.getElementById('live-watchlist').textContent = safeText(summaryData.watchlist_count);
        const run = summaryData.last_scheduler_run;
        document.getElementById('live-scan').textContent = run ? safeText(run.status) : 'Sin ejecuciones';
        document.getElementById('run-status').textContent = run ? safeText(run.status) : 'Sin ejecuciones';
        document.getElementById('run-detail').textContent = run ?
          `${{run.signal_count}} señales · ${{run.alert_count}} alertas` : '-';
      }}
      if (accountData) {{
        document.getElementById('live-equity').textContent = formatMoneyValue(accountData.equity);
        document.getElementById('paper-starting-equity').textContent = formatMoneyValue(accountData.starting_equity);
        document.getElementById('paper-current-equity').textContent = formatMoneyValue(accountData.equity);
        document.getElementById('paper-execution-state').textContent = accountData.real_execution_enabled ?
          'Revisar configuracion' : 'Solo simulacion';
        document.getElementById('paper-updated-at').textContent = safeText(accountData.updated_at);
      }}
      if (metricsData) {{
        document.querySelectorAll('[data-metric]').forEach((node) => {{
          const name = node.dataset.metric; node.textContent = formatMetric(name, metricsData[name]);
        }});
      }}
      if (healthData) {{
        const okay = healthData.status === 'ok';
        document.getElementById('health-status').textContent = okay ? 'Operativa' : 'Degradada';
        document.getElementById('health-detail').textContent = safeText(healthData.checked_at);
        document.getElementById('system-health').className = `system-item ${{okay ? 'ok' : 'warn'}}`;
      }}
      document.getElementById('drift-status').textContent = driftData && driftData.length ?
        safeText(driftData[0].status || 'Registrado') : 'Sin informes';
      document.getElementById('drift-detail').textContent = driftData && driftData.length ?
        safeText(driftData[0].created_at || driftData[0].timestamp) : 'Aun no hay drift persistido';
      const latestModel = modelData && modelData.length ? modelData[modelData.length - 1] : null;
      document.getElementById('model-status').textContent = latestModel ?
        (latestModel.status === 'trained' ? safeText(latestModel.model) : 'Baseline de respaldo') :
        'Se entrena al escanear';
      document.getElementById('model-detail').textContent = latestModel ?
        (latestModel.status === 'trained' ?
          `${{latestModel.training_samples || 0}} muestras · prec. ${{((latestModel.oos_precision || 0) * 100).toFixed(1)}}% · recall ${{((latestModel.oos_recall || 0) * 100).toFixed(1)}}% · cobertura ${{((latestModel.oos_coverage || 0) * 100).toFixed(1)}}%` :
          safeText(latestModel.reason || 'Aun no hay suficientes velas')) :
        'Necesita historial suficiente y solo usa datos cerrados';
      if (astraData) {{
        document.getElementById('astra-usage').textContent = `${{astraData.requests}} / ${{astraData.max_requests_per_day}} solicitudes`;
        document.getElementById('astra-cost').textContent = `Coste estimado $${{Number(astraData.estimated_cost_usd || 0).toFixed(4)}}`;
      }}
      if (tradesData) {{
        const tradeRows = document.getElementById('paper-trades-rows');
        tradeRows.replaceChildren();
        if (!tradesData.length) {{
          tradeRows.innerHTML = '<tr><td colspan="5" class="muted">Aun no hay operaciones simuladas.</td></tr>';
        }} else {{
          tradesData.slice().reverse().forEach((trade) => {{
            const row = document.createElement('tr');
            [trade.symbol, trade.direction, formatPrice(trade.entry_price), formatPrice(trade.exit_price), formatMoneyValue(trade.pnl)]
              .forEach((value) => {{ const cell = document.createElement('td'); cell.textContent = safeText(value); row.appendChild(cell); }});
            tradeRows.appendChild(row);
          }});
        }}
      }}
    }}

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

    function formatSimulationPnl(value) {{
      if (typeof value !== 'number') return '-';
      return `${{value >= 0 ? '+' : ''}}${{formatMoneyValue(value)}}`;
    }}

    function setSimulationStatus(message) {{ simulationStatus.textContent = message; }}

    function appendSimulationCell(row, value, className = '') {{
      const cell = document.createElement('td');
      cell.textContent = safeText(value);
      if (className) cell.className = className;
      row.appendChild(cell);
    }}

    function renderSimulationAccount(account, trades, metrics) {{
      document.getElementById('sim-starting-equity').textContent = formatMoneyValue(account.starting_equity);
      document.getElementById('sim-cash-balance').textContent = formatMoneyValue(account.cash_balance);
      document.getElementById('sim-equity').textContent = formatMoneyValue(account.equity);
      document.getElementById('sim-available-margin').textContent = formatMoneyValue(account.available_margin);
      document.getElementById('sim-unrealized-pnl').textContent = formatSimulationPnl(account.unrealized_pnl);
      document.getElementById('sim-realized-pnl').textContent = formatSimulationPnl(account.realized_pnl);
      document.getElementById('sim-total-pnl').textContent = formatSimulationPnl(account.total_pnl);
      document.getElementById('sim-exposure').textContent = formatMoneyValue(account.exposure);
      document.getElementById('sim-var95').textContent = formatMoneyValue(metrics && metrics.var_95);
      document.getElementById('sim-cvar95').textContent = formatMoneyValue(metrics && metrics.cvar_95);
      document.getElementById('sim-max-drawdown').textContent = metrics ?
        `${{Number(metrics.max_drawdown_pct || 0).toFixed(2)}}%` : '-';
      const positionsRows = document.getElementById('sim-positions-rows');
      positionsRows.replaceChildren();
      if (!account.positions || !account.positions.length) {{
        positionsRows.innerHTML = '<tr><td colspan="9" class="muted">No hay posiciones abiertas.</td></tr>';
      }} else {{
        account.positions.forEach((position) => {{
          const row = document.createElement('tr');
          appendSimulationCell(row, position.symbol);
          appendSimulationCell(row, position.direction, position.direction === 'LONG' ? 'long' : 'short');
          appendSimulationCell(row, formatMoneyValue(position.margin));
          appendSimulationCell(row, `${{position.leverage}}x`);
          appendSimulationCell(row, formatPrice(position.entry_price));
          appendSimulationCell(row, formatPrice(position.mark_price));
          appendSimulationCell(row, formatSimulationPnl(position.unrealized_pnl),
            position.unrealized_pnl >= 0 ? 'simulation-pnl-positive' : 'simulation-pnl-negative');
          appendSimulationCell(row, formatPrice(position.liquidation_price));
          const actionCell = document.createElement('td');
          const closeButton = document.createElement('button');
          closeButton.type = 'button'; closeButton.className = 'secondary'; closeButton.textContent = 'Cerrar';
          closeButton.addEventListener('click', () => closeSimulationPosition(position));
          actionCell.appendChild(closeButton); row.appendChild(actionCell);
          positionsRows.appendChild(row);
        }});
      }}
      const tradesRows = document.getElementById('sim-trades-rows');
      tradesRows.replaceChildren();
      if (!trades || !trades.length) {{
        tradesRows.innerHTML = '<tr><td colspan="6" class="muted">Aún no hay operaciones cerradas.</td></tr>';
      }} else {{
        trades.slice().reverse().forEach((trade) => {{
          const row = document.createElement('tr');
          appendSimulationCell(row, trade.symbol);
          appendSimulationCell(row, trade.direction, trade.direction === 'LONG' ? 'long' : 'short');
          appendSimulationCell(row, formatPrice(trade.entry_price));
          appendSimulationCell(row, formatPrice(trade.exit_price));
          appendSimulationCell(row, formatSimulationPnl(trade.pnl),
            trade.pnl >= 0 ? 'simulation-pnl-positive' : 'simulation-pnl-negative');
          appendSimulationCell(row, safeText(trade.closed_at));
          tradesRows.appendChild(row);
        }});
      }}
    }}

    async function loadSimulation() {{
      const [account, trades, metrics] = await Promise.all([
        fetchJson('/api/v1/simulation/account'), fetchJson('/api/v1/simulation/trades?limit=50'),
        fetchJson('/api/v1/simulation/metrics')
      ]);
      if (!account) {{
        setSimulationStatus('No se pudo cargar la cuenta de simulación.');
        return;
      }}
      renderSimulationAccount(account, trades || [], metrics);
      const refreshed = account.prices_refreshed && account.prices_refreshed.length;
      setSimulationStatus(refreshed ?
        `Mercado actualizado para: ${{account.prices_refreshed.join(', ')}} · apalancamiento máximo ${{account.max_leverage}}x.` :
        'Sin precios nuevos del proveedor; se conserva el último precio marcado.');
    }}

    async function closeSimulationPosition(position) {{
      const currentPrice = lastChartPayload && lastChartPayload.symbol === position.symbol ?
        lastChartPayload.latest.close : undefined;
      const response = await fetch(`/api/v1/simulation/positions/${{encodeURIComponent(position.position_id)}}/close`, {{
        method: 'POST', headers: {{'Content-Type': 'application/json'}},
        body: JSON.stringify(currentPrice ? {{price: currentPrice}} : {{}})
      }});
      const payload = await response.json().catch(() => ({{}}));
      if (!response.ok) {{ setSimulationStatus(payload.detail || 'No se pudo cerrar la posición.'); return; }}
      setSimulationStatus(`Posición cerrada. PnL: ${{formatSimulationPnl(payload.trade.pnl)}}`);
      await loadSimulation();
      await loadOperationalData();
    }}

    function setSummary(payload) {{
      const levels = payload.levels || {{}};
      const signal = payload.signal || {{}};
      const direction = signal.direction || 'NO_TRADE';
      const directionLabel = direction === 'LONG' ? 'ALCISTA' :
        direction === 'SHORT' ? 'BAJISTA' : 'ESPERAR';
      const center = payload.forecast && payload.forecast.center || [];
      const centralValue = center.length && direction !== 'NO_TRADE' ?
        formatPrice(center[center.length - 1].value) : '-';
      const values = [
        formatPrice(payload.latest && payload.latest.close),
        formatPercent(payload.change_pct),
        directionLabel,
        formatConfidence(signal.confidence),
        centralValue
      ];
      [...marketSummary.querySelectorAll('strong')].forEach((node, index) => {{
        node.textContent = values[index];
      }});
      document.getElementById('level-entry').textContent = formatPrice(levels.entry);
      document.getElementById('level-target').textContent = formatPrice(levels.target);
      document.getElementById('level-stop').textContent = formatPrice(levels.stop);
    }}

    function renderExplanation(payload) {{
      const explanation = payload.explanation || {{}};
      const direction = (payload.signal || {{}}).direction || 'NO_TRADE';
      const directionClass = direction === 'LONG' ? 'long' : direction === 'SHORT' ? 'short' : '';
      marketExplanation.className = 'explanation-box ' + directionClass;
      explanationSummary.textContent = explanation.summary || 'No hay explicación disponible.';
      function renderList(list, values, fallback) {{
        list.replaceChildren();
        const items = Array.isArray(values) && values.length ? values : [fallback];
        items.forEach((value) => {{
          const item = document.createElement('li'); item.textContent = safeText(value); list.appendChild(item);
        }});
      }}
      renderList(explanationDrivers, explanation.drivers, 'Sin indicadores explicativos disponibles.');
      renderList(explanationLevels, explanation.levels, 'Sin niveles de operación propuestos.');
      renderList(explanationWarnings, explanation.warnings, 'Sin advertencias adicionales; revisa siempre el rango de incertidumbre.');
    }}

    function clearMarketState(message) {{
      lastChartPayload = null;
      chartHoverIndex = null;
      chartTooltip.hidden = true;
      chartLayout = null;
      marketTitle.textContent = selectedSymbol ? `${{selectedSymbol}} · Sin datos` : 'Sin datos';
      marketMeta.textContent = message || 'No hay datos frescos para recalcular este horizonte.';
      marketAction.textContent = 'SIN DATOS';
      marketAction.className = 'pill wait';
      marketSource.textContent = 'DATOS NO DISPONIBLES';
      marketSource.className = 'pill wait';
      marketDecision.className = 'decision-note wait';
      marketDecision.textContent = 'No se genera una predicción hasta disponer de velas del horizonte seleccionado.';
      marketDisclaimer.textContent = 'La predicción anterior se ha limpiado para no mezclar horizontes ni mostrar datos obsoletos.';
      marketCanvas.style.display = 'none';
      marketEmpty.style.display = 'block';
      marketEmpty.textContent = 'Sin datos para este intervalo. Prueba Actualizar datos o vuelve a intentarlo durante la sesión.';
      forecastLabel.textContent = 'Sin escenario';
      setSummary({{ latest: {{}}, change_pct: null, signal: {{}}, forecast: {{}}, levels: {{}} }});
      renderExplanation({{
        signal: {{direction: 'NO_TRADE'}},
        explanation: {{
          summary: 'No se puede recalcular este horizonte con datos frescos.',
          drivers: [], levels: [],
          warnings: [message || 'El proveedor no ha devuelto velas para este intervalo.']
        }}
      }});
    }}

    function drawMarketChart(payload, hoverIndex = chartHoverIndex) {{
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
      chartLayout = {{ historical, future, upper, lower, total, left, right, top, bottom,
        width, height, plotWidth, plotHeight, x, y }};
      ctx.clearRect(0, 0, width, height); ctx.fillStyle = '#fbfcfc'; ctx.fillRect(0, 0, width, height);
      ctx.font = '11px Segoe UI, Arial'; ctx.strokeStyle = '#e2e8eb'; ctx.fillStyle = '#5e6a72';
      for (let index = 0; index <= 4; index += 1) {{
        const yy = top + (index / 4) * plotHeight;
        ctx.beginPath(); ctx.moveTo(left, yy); ctx.lineTo(width - right, yy); ctx.stroke();
        const label = maxValue - (index / 4) * (maxValue - minValue);
        ctx.fillText(formatPrice(label), 6, yy + 4);
      }}
      const timeForIndex = (index) => {{
        if (index < historical.length) return historical[index].time;
        const futureIndex = index - (historical.length - 1);
        return future[futureIndex] ? future[futureIndex].time : historical[historical.length - 1].time;
      }};
      const firstTime = new Date(timeForIndex(0)).getTime();
      const lastTime = new Date(timeForIndex(total - 1)).getTime();
      const formatAxisTime = (iso) => {{
        const date = new Date(iso);
        return lastTime - firstTime >= 86_400_000 ?
          date.toLocaleDateString(undefined, {{day: '2-digit', month: 'short'}}) :
          date.toLocaleTimeString(undefined, {{hour: '2-digit', minute: '2-digit'}});
      }};
      const timelineIndexes = [...new Set([0, Math.floor((total - 1) * 0.25),
        Math.floor((total - 1) * 0.5), Math.floor((total - 1) * 0.75), total - 1])];
      ctx.strokeStyle = '#eef1f3'; ctx.fillStyle = '#5e6a72'; ctx.lineWidth = 1;
      ctx.textAlign = 'center';
      timelineIndexes.forEach((index) => {{
        const xx = x(index);
        ctx.beginPath(); ctx.moveTo(xx, top); ctx.lineTo(xx, height - bottom); ctx.stroke();
        ctx.fillText(formatAxisTime(timeForIndex(index)), xx, height - 10);
      }});
      ctx.textAlign = 'left';
      const line = (points, color, dashed = false, startIndex = 0) => {{
        if (!points.length) return;
        ctx.beginPath(); ctx.setLineDash(dashed ? [6, 5] : []); ctx.strokeStyle = color; ctx.lineWidth = 2;
        points.forEach((item, index) => {{
          const xx = x(startIndex + index); const yy = y(item.value);
          if (index === 0) ctx.moveTo(xx, yy); else ctx.lineTo(xx, yy);
        }}); ctx.stroke(); ctx.setLineDash([]);
      }};
      const drawCandles = () => {{
        const slotWidth = plotWidth / Math.max(1, historical.length - 1);
        const bodyWidth = Math.max(2, Math.min(14, slotWidth * 0.62));
        historical.forEach((item, index) => {{
          const xx = x(index);
          const bullish = item.close >= item.open;
          const color = bullish ? '#16803c' : '#b42318';
          ctx.strokeStyle = color; ctx.fillStyle = color; ctx.lineWidth = 1;
          ctx.beginPath(); ctx.moveTo(xx, y(item.high)); ctx.lineTo(xx, y(item.low)); ctx.stroke();
          const top = Math.min(y(item.open), y(item.close));
          const height = Math.max(1, Math.abs(y(item.open) - y(item.close)));
          ctx.fillRect(xx - bodyWidth / 2, top, bodyWidth, height);
        }});
      }};
      if (chartMode === 'candles') drawCandles();
      else line(historical.map((item) => ({{value: item.close}})), '#087f8c');
      if (upper.length && lower.length) {{
        ctx.beginPath(); ctx.fillStyle = 'rgba(183, 121, 31, 0.14)';
        upper.forEach((item, index) => {{ const xx = x(historical.length - 1 + index); const yy = y(item.value);
          if (index === 0) ctx.moveTo(xx, yy); else ctx.lineTo(xx, yy); }});
        [...lower].reverse().forEach((item, index) => {{ const xx = x(historical.length - 1 + lower.length - 1 - index);
          ctx.lineTo(xx, y(item.value)); }}); ctx.closePath(); ctx.fill();
        line(upper, '#b7791f', true, historical.length - 1);
        line(lower, '#b7791f', true, historical.length - 1);
        const direction = payload.signal && payload.signal.direction;
        const centerColor = direction === 'LONG' ? '#16803c' :
          direction === 'SHORT' ? '#b42318' : '#b7791f';
        line(future, centerColor, true, historical.length - 1);
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
      if (typeof hoverIndex === 'number' && hoverIndex >= 0 && hoverIndex < total) {{
        const xx = x(hoverIndex);
        ctx.beginPath(); ctx.setLineDash([3, 3]); ctx.strokeStyle = '#183b45'; ctx.lineWidth = 1;
        ctx.moveTo(xx, top); ctx.lineTo(xx, height - bottom); ctx.stroke(); ctx.setLineDash([]);
        const historicalPoint = hoverIndex < historical.length ? historical[hoverIndex] : null;
        const value = historicalPoint ? historicalPoint.close :
          future[hoverIndex - (historical.length - 1)]?.value;
        if (typeof value === 'number') {{
          ctx.beginPath(); ctx.fillStyle = '#183b45'; ctx.arc(xx, y(value), 4, 0, Math.PI * 2); ctx.fill();
        }}
      }}
    }}

    function formatHoverTime(value) {{
      return new Date(value).toLocaleString(undefined, {{
        year: 'numeric', month: '2-digit', day: '2-digit',
        hour: '2-digit', minute: '2-digit'
      }});
    }}

    function showChartTooltip(event) {{
      if (!chartLayout || !lastChartPayload) return;
      const canvasRect = marketCanvas.getBoundingClientRect();
      const wrapRect = chartWrap.getBoundingClientRect();
      const canvasX = event.clientX - canvasRect.left;
      const canvasY = event.clientY - canvasRect.top;
      if (canvasX < chartLayout.left || canvasX > canvasRect.width - chartLayout.right ||
          canvasY < chartLayout.top || canvasY > chartLayout.height - chartLayout.bottom) {{
        chartHoverIndex = null; chartTooltip.hidden = true; drawMarketChart(lastChartPayload); return;
      }}
      const ratio = (canvasX - chartLayout.left) / chartLayout.plotWidth;
      chartHoverIndex = Math.max(0, Math.min(chartLayout.total - 1,
        Math.round(ratio * (chartLayout.total - 1))));
      drawMarketChart(lastChartPayload, chartHoverIndex);
      const historical = chartLayout.historical;
      const future = chartLayout.future;
      const historicalPoint = chartHoverIndex < historical.length ?
        historical[chartHoverIndex] : null;
      let message;
      if (historicalPoint) {{
        message = `Hora: ${{formatHoverTime(historicalPoint.time)}}\n` +
          `Apertura: ${{formatPrice(historicalPoint.open)}}\n` +
          `Máximo: ${{formatPrice(historicalPoint.high)}}\n` +
          `Mínimo: ${{formatPrice(historicalPoint.low)}}\n` +
          `Cierre: ${{formatPrice(historicalPoint.close)}}`;
      }} else {{
        const futurePoint = future[chartHoverIndex - (historical.length - 1)];
        message = futurePoint ?
          `Escenario: ${{formatHoverTime(futurePoint.time)}}\n` +
          `Predicción central: ${{formatPrice(futurePoint.value)}}\n` +
          `Rango: ${{formatPrice((lastChartPayload.forecast.upper[chartHoverIndex - (historical.length - 1)] || {{}}).value)}} - ` +
          `${{formatPrice((lastChartPayload.forecast.lower[chartHoverIndex - (historical.length - 1)] || {{}}).value)}}` :
          'Sin datos para este punto';
      }}
      chartTooltip.textContent = message;
      chartTooltip.hidden = false;
      const localX = event.clientX - wrapRect.left;
      const localY = event.clientY - wrapRect.top;
      const tooltipWidth = chartTooltip.offsetWidth || 220;
      const tooltipHeight = chartTooltip.offsetHeight || 80;
      const nextLeft = Math.min(localX + 16, wrapRect.width - tooltipWidth - 8);
      const nextTop = Math.max(8, Math.min(localY + 16, wrapRect.height - tooltipHeight - 8));
      chartTooltip.style.left = `${{Math.max(8, nextLeft)}}px`;
      chartTooltip.style.top = `${{nextTop}}px`;
    }}

    function hideChartTooltip() {{
      chartHoverIndex = null;
      chartTooltip.hidden = true;
      if (lastChartPayload) drawMarketChart(lastChartPayload, null);
    }}

    function markSelectedRow(symbol) {{
      document.querySelectorAll('.watchlist-row').forEach((row) => {{
        row.classList.toggle('selected', row.dataset.symbol === symbol);
      }});
    }}

    async function updateWatchlistDirections() {{
      const watchlistRows = [...document.querySelectorAll('.watchlist-row')];
      await Promise.all(watchlistRows.map(async (row) => {{
        const symbol = row.dataset.symbol;
        const badge = row.querySelector('[data-watchlist-direction]');
        if (!symbol || !badge) return;
        try {{
          const response = await fetch(`/api/v1/market/${{encodeURIComponent(symbol)}}?window=1d`);
          if (!response.ok) throw new Error('market data unavailable');
          const payload = await response.json();
          const direction = payload.signal && payload.signal.direction || 'NO_TRADE';
          const label = direction === 'LONG' ? 'ALCISTA' : direction === 'SHORT' ? 'BAJISTA' : 'ESPERAR';
          const cssClass = direction === 'LONG' ? 'long' : direction === 'SHORT' ? 'short' : 'wait';
          badge.textContent = label;
          badge.className = `watchlist-direction ${{cssClass}}`;
          badge.title = `${{payload.signal.model}} · confianza ${{formatConfidence(payload.signal.confidence)}}`;
          row.classList.remove('long-row', 'short-row', 'wait-row');
          row.classList.add(`${{cssClass}}-row`);
        }} catch (error) {{
          badge.textContent = 'SIN DATOS';
          badge.className = 'watchlist-direction wait';
          row.classList.remove('long-row', 'short-row'); row.classList.add('wait-row');
          badge.title = 'No se pudo obtener una señal actual para este producto';
        }}
      }}));
    }}

    async function loadMarket(symbol, windowValue) {{
      if (!symbol) return;
      selectedSymbol = symbol; selectedWindow = windowValue; markSelectedRow(symbol);
      const requestId = ++marketRequestId;
      simulationSymbol.value = symbol;
      document.querySelectorAll('.window-button').forEach((button) => {{
        button.classList.toggle('active', button.dataset.window === windowValue);
      }});
      clearMarketState('Recalculando velas, indicadores y predicción para este horizonte...');
      let response;
      try {{
        response = await fetch(`/api/v1/market/${{encodeURIComponent(symbol)}}?window=${{windowValue}}`);
      }} catch (error) {{
        if (requestId === marketRequestId) clearMarketState('No se pudo conectar con el proveedor de datos.');
        return;
      }}
      if (requestId !== marketRequestId) return;
      if (!response.ok) {{
        const error = await response.json().catch(() => ({{}}));
        clearMarketState(error.detail || 'No hay datos frescos para este intervalo.');
        return;
      }}
      const payload = await response.json();
      if (requestId !== marketRequestId) return;
      lastChartPayload = payload;
      chartHoverIndex = null; chartTooltip.hidden = true;
      marketTitle.textContent = `${{payload.symbol}} · ${{payload.name}}`;
      marketMeta.textContent = `${{payload.window_label}} · ${{payload.candle_count}} velas · ` +
        `${{payload.timeframe}} · ${{payload.currency}} · modelo ${{payload.signal.model}}` +
        (payload.data_notice ? ` · ${{payload.data_notice}}` : '');
      const direction = payload.signal.direction;
      const directionClass = direction === 'LONG' ? 'long' : direction === 'SHORT' ? 'short' : 'wait';
      const directionLabel = direction === 'LONG' ? 'SEÑAL ALCISTA' :
        direction === 'SHORT' ? 'SEÑAL BAJISTA' : 'ESPERAR';
      marketAction.textContent = directionLabel;
      marketAction.className = 'pill ' + directionClass;
      marketDecision.className = 'decision-note ' + directionClass;
      marketDecision.textContent = direction === 'LONG' ?
        'Lectura actual: ALCISTA. El modelo ve un sesgo de subida para este horizonte; revisa entrada, objetivo y stop antes de cualquier operación paper.' :
        direction === 'SHORT' ?
        'Lectura actual: BAJISTA. El modelo ve un sesgo de bajada para este horizonte; revisa entrada, objetivo y stop antes de cualquier operación paper.' :
        'Lectura actual: INDEFINIDA. No hay señal clara de compra o venta; la zona amarilla es solo un rango de incertidumbre.';
      forecastLabel.textContent = direction === 'NO_TRADE' ?
        'Rango de incertidumbre (sin dirección)' : 'Rango futuro aprox.';
      const sourceIsDemo = payload.provider === 'demo';
      const sourceIsFallback = Boolean(payload.data_notice);
      marketSource.textContent = sourceIsDemo ? 'DATOS DEMO' :
        sourceIsFallback ? `ÚLTIMA SESIÓN · ${{payload.provider}}` :
        payload.source === 'provider' ? `DATOS EN VIVO · ${{payload.provider}}` :
        `CACHÉ · ${{payload.provider}}`;
      marketSource.className = 'pill ' + (sourceIsDemo ? 'demo' : sourceIsFallback ? 'wait' : '');
      setSummary(payload); renderExplanation(payload); marketDisclaimer.textContent = payload.disclaimer;
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
    document.querySelectorAll('.chart-mode-button').forEach((button) => {{
      button.addEventListener('click', () => {{
        chartMode = button.dataset.chartMode;
        chartHoverIndex = null; chartTooltip.hidden = true;
        document.querySelectorAll('.chart-mode-button').forEach((item) =>
          item.classList.toggle('active', item.dataset.chartMode === chartMode));
        if (lastChartPayload) drawMarketChart(lastChartPayload);
      }});
    }});
    marketCanvas.addEventListener('mousemove', showChartTooltip);
    marketCanvas.addEventListener('mouseleave', hideChartTooltip);
    window.addEventListener('resize', () => {{
      if (lastChartPayload) drawMarketChart(lastChartPayload);
    }});
    if (defaultSymbol) loadMarket(defaultSymbol, selectedWindow);
    updateWatchlistDirections();
    let scanInFlight = false;
    async function runWatchlistScan() {{
      if (scanInFlight) return;
      scanInFlight = true;
      setStatus('Escaneando watchlist...'); setOperationStatus('Analizando todos los activos de la watchlist...');
      const response = await fetch('/api/v1/watchlist/scan', {{
        method: 'POST', headers: {{'Content-Type': 'application/json'}},
        body: JSON.stringify({{timeframe: scanTimeframe.value, days: Number(scanDays.value)}})
      }});
      if (response.ok) {{
        const payload = await response.json();
        const run = payload.run || {{}};
        const message = `Escaneo terminado: ${{run.signal_count || 0}} señales y ${{run.alert_count || 0}} alertas.`;
        setStatus(message); setOperationStatus(message); await loadOperationalData();
        window.setTimeout(() => window.location.reload(), 350);
      }} else {{
        const error = await response.json().catch(() => ({{}}));
        const message = error.detail || 'El escaneo no se pudo completar.';
        setStatus(message); setOperationStatus(message);
      }}
      scanInFlight = false;
    }}
    function togglePeriodicScan() {{
      if (periodicTimer) {{
        window.clearInterval(periodicTimer); periodicTimer = null;
        periodicButton.textContent = 'Activar periódico'; setOperationStatus('Escaneo periódico detenido.'); return;
      }}
      const milliseconds = Number(scanInterval.value);
      if (!milliseconds) {{ setOperationStatus('Selecciona una frecuencia para activar el escaneo periódico.'); return; }}
      periodicTimer = window.setInterval(runWatchlistScan, milliseconds);
      periodicButton.textContent = 'Detener periódico';
      setOperationStatus(`Escaneo periódico activo cada ${{scanInterval.options[scanInterval.selectedIndex].text}}.`);
    }}
    document.getElementById('scan-watchlist').addEventListener('click', runWatchlistScan);
    periodicButton.addEventListener('click', togglePeriodicScan);
    document.getElementById('refresh-live').addEventListener('click', async () => {{
      setOperationStatus('Actualizando métricas y estado...'); await loadOperationalData();
      setOperationStatus('Datos actualizados.');
    }});
    function selectSimulationDirection(direction) {{
      simulationDirection = direction;
      simulationLong.className = direction === 'LONG' ? 'active-long' : '';
      simulationShort.className = direction === 'SHORT' ? 'active-short' : '';
    }}
    simulationLong.addEventListener('click', () => selectSimulationDirection('LONG'));
    simulationShort.addEventListener('click', () => selectSimulationDirection('SHORT'));
    document.getElementById('sim-open').addEventListener('click', async () => {{
      const symbol = simulationSymbol.value || selectedSymbol;
      if (!symbol) {{ setSimulationStatus('Selecciona un activo antes de abrir una posición.'); return; }}
      const margin = Number(document.getElementById('sim-margin').value);
      const leverage = Number(document.getElementById('sim-leverage').value);
      const currentPrice = lastChartPayload && lastChartPayload.symbol === symbol ?
        lastChartPayload.latest.close : undefined;
      setSimulationStatus('Abriendo posición simulada...');
      const response = await fetch('/api/v1/simulation/positions', {{
        method: 'POST', headers: {{'Content-Type': 'application/json'}},
        body: JSON.stringify({{symbol, direction: simulationDirection, margin, leverage, price: currentPrice}})
      }});
      const payload = await response.json().catch(() => ({{}}));
      if (!response.ok) {{ setSimulationStatus(payload.detail || 'No se pudo abrir la posición.'); return; }}
      setSimulationStatus(`Posición ${{simulationDirection}} abierta en ${{formatPrice(payload.position.entry_price)}}.`);
      await loadSimulation();
    }});
    document.getElementById('sim-reset').addEventListener('click', async () => {{
      const startingEquity = Number(document.getElementById('sim-reset-equity').value);
      if (!startingEquity || !window.confirm('Esto borrará el historial de simulación. ¿Continuar?')) return;
      const response = await fetch('/api/v1/simulation/reset', {{
        method: 'POST', headers: {{'Content-Type': 'application/json'}},
        body: JSON.stringify({{starting_equity: startingEquity}})
      }});
      const payload = await response.json().catch(() => ({{}}));
      if (!response.ok) {{ setSimulationStatus(payload.detail || 'No se pudo reiniciar la simulación.'); return; }}
      setSimulationStatus(`Cuenta reiniciada con ${{formatMoneyValue(startingEquity)}}.`);
      await loadSimulation();
    }});
    loadOperationalData().catch(() => setOperationStatus('No se pudo cargar el estado operativo.'));
    loadSimulation().catch(() => setSimulationStatus('No se pudo cargar la simulación.'));
    simulationTimer = window.setInterval(() => loadSimulation().catch(() => {{}}), 15000);
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
        f'<td><span class="watchlist-direction wait" '
        f'data-watchlist-direction="{escape(instrument.symbol)}">CARGANDO</span></td>'
        f'<td><button type="button" class="secondary remove-instrument" '
        f'data-symbol="{escape(instrument.symbol)}">Remove</button></td>'
        "</tr>"
    )


def _format_money(value: object) -> str:
    return "-" if not isinstance(value, (float, int)) else f"{value:,.2f}"


def _format_percent(value: object) -> str:
    return "-" if not isinstance(value, (float, int)) else f"{value:.2f}%"
