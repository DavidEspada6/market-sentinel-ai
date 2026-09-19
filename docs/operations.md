# Operations

The original v1.0.0 was a prototype baseline. The completion track ended at v2.0.0; O1 adds a
curated multi-asset universe, persistent watchlists and controlled periodic scans while
preserving alert-only and paper-trading boundaries.

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
- RSS/Atom news context behind a replaceable provider.
- Persistent Astra usage records and hard request, token and daily-cost budgets.
- Persistent paper accounts and simulated trades with restart recovery.
- SQLite integrity checks, health history and backup support.
- Repository security check and final end-to-end release test.
- Curated instrument universe and persistent watchlist.
- Search, add/remove and multi-symbol watchlist scanning from the local API and dashboard.

## Not Supported In v2.0.0

- Real-money order execution.
- Broker account trading.
- Autonomous position management.
- Live order execution.
- Automatic broker recovery or account trading.

## Production Checklist

- Select a real market data adapter and verify its ingestion quality history.
- Keep secrets in environment variables only.
- Review backtests out of sample.
- Review paper trading logs before any broker work.
- Monitor drift before trusting stale models.
- Keep Astra budget limits low until signal quality is proven.
- Run `python -m market_sentinel_ai security-check` before publishing or deploying.
