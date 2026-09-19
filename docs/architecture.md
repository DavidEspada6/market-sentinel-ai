# Architecture

Market Sentinel AI is split into ports and adapters so every expensive, unreliable or vendor-specific part can be replaced without rewriting the trading logic.

## Design Principles

- The continuous market loop is quantitative and deterministic.
- GPT-6 Astra is used only when context and reasoning add value.
- Every prediction must be evaluated out of sample before it can produce alerts.
- Backtests must include fees, spread and slippage.
- Data, feature generation and labels must be time-aware to avoid leakage.
- The application starts with alerting, paper trading and local simulation, not live execution.

## Modules

### Configuration

`market_sentinel_ai.config` reads settings from environment variables. No secret has a default real value. The Python package keeps `.env` loading explicit for CI and production; the Windows launcher loads the local `.env` for the desktop workflow.

### Domain

`market_sentinel_ai.domain` defines the shared language:

- candles and timeframes,
- predictions and trade direction,
- signals and confidence,
- risk limits,
- alerts and reasoning results.
- paper accounts, open simulation positions and closed paper trades.

### Ports

`market_sentinel_ai.ports` defines interfaces for:

- market data providers,
- feature engines,
- predictive models,
- backtesters,
- reasoning providers,
- alert channels,
- repositories.

Concrete adapters currently cover deterministic demo data, Yahoo Finance and Stooq OHLCV,
Alpha Vantage daily/intraday OHLCV and public Binance order-book depth. Provider selection is
isolated behind factories and environment settings.

### Reasoning Layer

The Astra layer is intentionally downstream of quantitative signals. It receives compact structured context only when a signal passes gating rules:

- confidence is above threshold,
- risk policy allows the setup,
- cost budget has capacity,
- the signal is not a duplicate already explained recently.

The target output is structured JSON containing a short thesis, invalidation conditions, risk notes and relevant context. Astra must not override hard risk limits.

### Ingestion And Storage

SQLite stores normalized candles and immutable ingestion-run records. Every batch is checked for
empty input, duplicate timestamps and ordering before storage. Quality reports also expose
intraday gaps and staleness. The storage boundary allows later replacement with Postgres,
DuckDB or managed infrastructure.

### Operational Application

The C3 application exposes a local FastAPI service and HTML dashboard focused on current signals,
alert history and scheduler health. SQLite persists candles, ingestion runs, signals, alerts and
scheduler runs. The scheduler can run once for a controlled check or poll a watchlist until
stopped.

### Order Flow And Multi-Timeframe Features

Order-book snapshots are normalized into spread, depth, imbalance, microprice and pressure-change
features. Higher-timeframe OHLCV features are joined to a base timeframe only after the higher
timeframe's final component candle has closed. Regime-aware ensembles select weights using the
latest volatility regime and record that regime in prediction metadata.

## Data Flow

```text
Historical/live market data
        |
        v
Normalized candles and order-book events
        |
        v
Feature engine with time-aware windows
        |
        v
Model predictions and regime detection
        |
        v
Risk-aware signal generation
        |
        +--> Alerts
        +--> Dashboard
        +--> Astra reasoning when gated
        +--> Paper trading ledger
```

The operational prediction path first tries the adaptive local supervised model. Its examples
are built from past candle features and later closing prices, then evaluated with a purged
walk-forward report. A scan uses the latest fitted model only when it has enough provider
history; otherwise it records a `momentum-baseline` fallback and the reason in model status.
No model in this path can place a live order.

## Anti-Leakage Rules

- Features at time `t` may only use information available at or before `t`.
- Labels must be shifted forward and never merged back into feature windows.
- Model selection must be performed inside walk-forward folds.
- Training examples whose forward label can overlap a test window are removed by `purge_size`.
- Scaling, imputation and feature selection must be fit only on training windows.
- Reported metrics must distinguish in-sample, validation and out-of-sample periods.

## Model Artifacts

XGBoost and LightGBM artifacts use each library's native format plus a JSON manifest. The
manifest records the feature schema, hyperparameters, training timestamp, library version,
return calibration summary and a SHA-256 checksum. Loading validates the checksum before the
model can produce a prediction. Python pickle is not used for model persistence.
