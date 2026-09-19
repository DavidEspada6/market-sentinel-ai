from __future__ import annotations

from dataclasses import dataclass
from html import escape

from market_sentinel_ai.domain.instruments import Instrument
from market_sentinel_ai.domain.operations import AlertRecord, SignalRecord
from market_sentinel_ai.domain.prediction import Signal
from market_sentinel_ai.ports.backtesting import BacktestReport


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
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Market Sentinel AI</title>
  <style>
    :root {{ color-scheme: light; --bg: #f5f7f8; --panel: #fff; --ink: #182026;
      --muted: #5e6a72; --line: #d9e0e4; --teal: #087f8c; --red: #b42318; --green: #16803c; }}
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
    @media (max-width: 760px) {{ header {{ align-items: flex-start; flex-direction: column; }}
      main {{ padding: 14px; }} .summary {{ grid-template-columns: 1fr; }}
      .panel {{ overflow-x: auto; }} table {{ min-width: 680px; }} }}
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

    function setStatus(message) {{ status.textContent = message; }}

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
      button.addEventListener('click', async () => {{
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
        "<tr>"
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
