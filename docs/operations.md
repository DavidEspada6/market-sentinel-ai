# Operations

The original v1.0.0 is a prototype baseline. The completion track is active; v1.4.0 adds public
order-book depth, causal multitimeframe features and regime-aware ensembles while preserving
alert-only and paper-trading boundaries.

## Supported Mode

- Demo/local market data.
- Yahoo Finance historical/intraday data without credentials.
- Stooq daily historical data without credentials, subject to its browser-verification policy.
- Alpha Vantage daily and intraday data with an API key.
- Persistent ingestion history and quality reports.
- XGBoost and LightGBM training with native, checksum-verified artifacts.
- Purged walk-forward reports with trading costs included.
- Historical backtesting.
- Walk-forward evaluation.
- Dry-run alerts.
- Generated dashboard.
- GPT-6 Astra context layer with cost gates.
- Paper trading ledger.
- Drift checks.
- JSONL operational events.
- Local FastAPI service with health, status, scan, signal, alert and scheduler-run endpoints.
- SQLite-backed operational dashboard.
- One-shot and polling scheduler commands.
- Public Binance depth adapter with configurable endpoint and depth.
- Causal multitimeframe feature alignment.
- Regime-aware ensemble predictions with regime metadata.

## Not Supported In v1

- Real-money order execution.
- Broker account trading.
- Autonomous position management.
- Live order execution.

## Production Checklist

- Select a real market data adapter and verify its ingestion quality history.
- Keep secrets in environment variables only.
- Review backtests out of sample.
- Review paper trading logs before any broker work.
- Monitor drift before trusting stale models.
- Keep Astra budget limits low until signal quality is proven.
