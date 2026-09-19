# Market Sentinel AI

Market Sentinel AI is a predictive market analysis and alerting application. Its core loop is quantitative, cheap and deterministic: market data ingestion, feature engineering, supervised models, walk-forward backtesting, risk controls and alerting. GPT-6 Astra is reserved for contextual reasoning when a signal is important enough to justify the extra cost.

This repository is being built in releases. R5 is the current local release: architecture, contracts, safe configuration, tests, CI, deterministic demo data, SQLite storage, OHLCV/order-flow features, baseline/backtesting, supervised walk-forward evaluation, signal generation, dry-run alerts, a generated web dashboard, regime detection and a weighted ensemble. It intentionally does not place live trades.

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

## Local Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .[dev]
Copy-Item .env.example .env
python -m unittest discover -s tests
python -m market_sentinel_ai
python -m market_sentinel_ai demo-ingest --symbol SPY --timeframe 5m --days 3
python -m market_sentinel_ai list-candles --symbol SPY --timeframe 5m --days 3
python -m market_sentinel_ai backtest-demo --symbol SPY --timeframe 5m --days 10
python -m market_sentinel_ai walk-forward-demo --symbol SPY --timeframe 5m --days 30
python -m market_sentinel_ai signals-demo --symbol SPY --timeframe 5m --days 10
python -m market_sentinel_ai dashboard-demo --symbol SPY --timeframe 5m --days 30 --output reports/dashboard.html
python -m market_sentinel_ai ensemble-demo --symbol SPY --timeframe 5m --days 20
```

The project currently has no required runtime dependencies. Optional extras will be introduced behind stable interfaces as releases need API, ML and OpenAI functionality.

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

## Why Astra Is Not the Continuous Predictor

Official OpenAI documentation describes GPT-6 Astra as a high-capability reasoning model with Responses API support, structured outputs and a large context window. It is powerful, but expensive relative to local numeric models. This app therefore uses Astra as a selective reasoning layer: explain a high-conviction setup, summarize relevant context, check for contradictory news or macro context, and return structured reasoning that can be audited.

The continuous market loop remains local and measurable.
