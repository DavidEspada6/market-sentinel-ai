# Risk And Safety Rules

Market Sentinel AI must treat every prediction as uncertain.

## Non-Negotiable Rules

- Early releases are alert-only and paper-trading-only.
- The application must never commit API keys, tokens, webhook secrets or broker credentials.
- GPT-6 Astra may explain context, but it cannot bypass risk policy.
- Alerts must include direction, confidence, invalidation idea and risk notes where available.
- A high-confidence model output is not permission to trade.

## Metrics Required Before Trusting A Signal

- Precision and recall for directional decisions.
- Expectancy after fees, spread and slippage.
- PnL distribution, not only average PnL.
- Profit Factor.
- Sharpe and Sortino.
- Max Drawdown.
- Number of trades and trade frequency.
- Performance by market regime.
- Out-of-sample performance by walk-forward fold.

## Position Sizing Defaults

R0 stores conservative defaults only:

- max position size: 2% of account equity,
- max daily loss: 3%,
- default fee: 1 basis point,
- default slippage: 2 basis points.

These are simulation defaults, not trading recommendations.

