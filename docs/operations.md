# Operations

R7 completes v1.0.0 for alerting and paper trading.

## Supported Mode

- Demo/local market data.
- Historical backtesting.
- Walk-forward evaluation.
- Dry-run alerts.
- Generated dashboard.
- GPT-6 Astra context layer with cost gates.
- Paper trading ledger.
- Drift checks.
- JSONL operational events.

## Not Supported In v1

- Real-money order execution.
- Broker account trading.
- Autonomous position management.

## Production Checklist

- Use a real market data adapter behind the existing interfaces.
- Keep secrets in environment variables only.
- Review backtests out of sample.
- Review paper trading logs before any broker work.
- Monitor drift before trusting stale models.
- Keep Astra budget limits low until signal quality is proven.

