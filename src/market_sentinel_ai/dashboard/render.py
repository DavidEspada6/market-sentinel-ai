from __future__ import annotations

from dataclasses import dataclass
from html import escape

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
    .bar-row {{ display: grid; grid-template-columns: 110px 1fr 54px; gap: 10px; align-items: center; }}
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

