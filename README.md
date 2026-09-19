# Market Sentinel AI

Market Sentinel AI is a predictive market analysis and alerting application. Its core loop is quantitative, cheap and deterministic: market data ingestion, feature engineering, supervised models, walk-forward backtesting, risk controls and alerting. GPT-6 Astra is reserved for contextual reasoning when a signal is important enough to justify the extra cost.

Market Sentinel AI v2.5.0 is the operational alerting and paper-trading market analysis application. It includes deterministic demo data, replaceable Yahoo Finance, Stooq and Alpha Vantage market-data adapters, provider-backed Yahoo instrument search, a public Binance order-book adapter, RSS/Atom news context, quality-gated SQLite ingestion, causal OHLCV/volatility features, causal multitimeframe alignment, trainable XGBoost and LightGBM models, purged walk-forward evaluation, cost-aware backtesting, persistent operational signals with entry/stop/target plans, paper risk analytics for estimated/realized PnL, VaR/CVaR, volatility, Sharpe, Sortino and drawdown, a local API and dashboard, scheduled scans with alert deduplication, a curated multi-asset universe, searchable persistent watchlists with provider metadata, dry-run/webhook alerts, order-flow features, regime-aware ensembles, gated and budget-audited GPT-6 Astra contextual reasoning, persistent paper accounts and trades, drift and health history, recovery backups, operational logs, a repository security gate and end-to-end release tests. It does not place live trades.

## Safety Position

- No real-money trading in early releases.
- No real orders are sent by this application until a later release explicitly adds broker execution and review gates.
- Secrets must live in environment variables or a local `.env` file. Real credentials must never be committed.
- Predictions are probabilistic decision support, not financial advice.

## Release Roadmap

The v1 plan has eight releases:

| Release | Scope |
| --- | --- |
| R0 | Bootstrap, architecture, environment, repo hygiene |
| R1 | Historical and live-ish market data adapters, storage |
| R2 | Feature engine, baseline model, leakage-aware backtester |
| R3 | Supervised ML, walk-forward evaluation, out-of-sample reports |
| R4 | Signals, alert engine, web dashboard |
| R5 | Order-flow/order-book, ensemble, multi-timeframe modeling |
| R6 | GPT-6 Astra contextual reasoning, news, caching and cost control |
| R7 | Paper trading, model drift, observability, hardening, v1.0.0 |

Full details are in [docs/releases.md](docs/releases.md).
The honest completion track for the operational application is in [docs/completion-roadmap.md](docs/completion-roadmap.md).

## Local Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .[dev]
python -m pip install -e ".[dev,ml]"  # C2 boosting models
python -m pip install -e ".[dev,ml,api]"  # C3 API and dashboard
Copy-Item .env.example .env
python -m unittest discover -s tests
python -m market_sentinel_ai
python -m market_sentinel_ai demo-ingest --symbol SPY --timeframe 5m --days 3
python -m market_sentinel_ai ingest --provider yahoo --symbol SPY --timeframe 1d --days 365
python -m market_sentinel_ai ingest --provider alpha_vantage --symbol SPY --timeframe 5m --days 5
python -m market_sentinel_ai ingestion-runs --limit 10
python -m market_sentinel_ai list-candles --symbol SPY --timeframe 5m --days 3
python -m market_sentinel_ai backtest-demo --symbol SPY --timeframe 5m --days 10
python -m market_sentinel_ai walk-forward-demo --symbol SPY --timeframe 5m --days 30
python -m market_sentinel_ai boosting-demo --backend xgboost --symbol SPY --timeframe 5m --days 5
python -m market_sentinel_ai walk-forward-demo --model lightgbm --symbol SPY --timeframe 5m --days 30
python -m market_sentinel_ai signals-demo --symbol SPY --timeframe 5m --days 10
python -m market_sentinel_ai dashboard-demo --symbol SPY --timeframe 5m --days 30 --output reports/dashboard.html
python -m market_sentinel_ai ensemble-demo --symbol SPY --timeframe 5m --days 20
python -m market_sentinel_ai order-book-demo --provider demo --symbol BTCUSDT --depth 5
python -m market_sentinel_ai astra-context-demo --symbol SPY --timeframe 5m --days 10
python -m market_sentinel_ai news-demo --provider demo --symbol SPY
python -m market_sentinel_ai health
python -m market_sentinel_ai security-check
python -m market_sentinel_ai instruments --query NVIDIA
python -m market_sentinel_ai watchlist
python -m market_sentinel_ai watchlist --add MSFT
python -m market_sentinel_ai watchlist-scan --once --timeframe 5m --days 5
python -m market_sentinel_ai backup --output backups/market_sentinel.sqlite3
python -m market_sentinel_ai paper-demo --symbol SPY --timeframe 5m --days 10
python -m market_sentinel_ai drift-demo --symbol SPY --timeframe 5m --days 20
python -m market_sentinel_ai scan --symbol SPY --timeframe 5m --days 5
python -m market_sentinel_ai schedule --symbols SPY,QQQ --timeframe 5m --once
python -m market_sentinel_ai serve --host 127.0.0.1 --port 8000
```

Yahoo Finance and Stooq need no API key. Stooq may require browser verification in some regions, so Yahoo is the primary no-key adapter. Alpha Vantage uses `MARKET_DATA_API_KEY`; select it with `MARKET_DATA_PROVIDER=alpha_vantage`. Provider URLs and polling intervals can be overridden without changing application code. Optional ML, API and OpenAI dependencies remain behind extras.

## Current Architecture

```text
Market data providers
        |
        v
 Storage and event bus
        |
        v
 Feature engine
        |
        v
 Quantitative models and regime detector
        |
        v
 Signal and risk engine
        |
        +--> Alerts and dashboard
        |
        +--> GPT-6 Astra reasoning layer, only for selected signals
```

Read [docs/architecture.md](docs/architecture.md) for the module boundaries and [docs/risk.md](docs/risk.md) for trading-safety rules.
Read [docs/market-data.md](docs/market-data.md) for provider setup, limits and ingestion quality.
Read [docs/models.md](docs/models.md) for training, purging, artifacts and evaluation metrics.
Read [docs/astra.md](docs/astra.md) for the R6 GPT-6 Astra integration rules.
Read [docs/api.md](docs/api.md) for the local API, dashboard and scheduler.
Read [docs/order-flow.md](docs/order-flow.md) for order-book, multitimeframe and regime-aware
modeling.
Read [docs/news-context.md](docs/news-context.md) for RSS/Atom context and Astra budget rules.
Read [docs/paper-operations.md](docs/paper-operations.md) for paper persistence and recovery.
Read [docs/operations.md](docs/operations.md) for the v1 operating boundaries.
Read [docs/final-release.md](docs/final-release.md) for the v2.0.0 release gate and [SECURITY.md](SECURITY.md) for secret handling.
Read [docs/operational-roadmap.md](docs/operational-roadmap.md) for the remaining releases toward
full continuous analysis and risk analytics.

## Why Astra Is Not the Continuous Predictor

Official OpenAI documentation describes GPT-6 Astra as a high-capability reasoning model with Responses API support, structured outputs and a large context window. It is powerful, but expensive relative to local numeric models. This app therefore uses Astra as a selective reasoning layer: explain a high-conviction setup, summarize relevant context, check for contradictory news or macro context, and return structured reasoning that can be audited.

The continuous market loop remains local and measurable.
