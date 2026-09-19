# Architecture

Market Sentinel AI is split into ports and adapters so every expensive, unreliable or vendor-specific part can be replaced without rewriting the trading logic.

## Design Principles

- The continuous market loop is quantitative and deterministic.
- GPT-6 Astra is used only when context and reasoning add value.
- Every prediction must be evaluated out of sample before it can produce alerts.
- Backtests must include fees, spread and slippage.
- Data, feature generation and labels must be time-aware to avoid leakage.
- The application starts with alerting and paper trading, not live execution.

## Modules

### Configuration

`market_sentinel_ai.config` reads settings from environment variables. No secret has a default real value. R0 avoids loading a `.env` file automatically so CI and production behavior remain explicit.

### Domain

`market_sentinel_ai.domain` defines the shared language:

- candles and timeframes,
- predictions and trade direction,
- signals and confidence,
- risk limits,
- alerts and reasoning results.

### Ports

`market_sentinel_ai.ports` defines interfaces for:

- market data providers,
- feature engines,
- predictive models,
- backtesters,
- reasoning providers,
- alert channels,
- repositories.

Concrete adapters currently cover deterministic demo data, Yahoo Finance and Stooq OHLCV, and
Alpha Vantage daily/intraday OHLCV. Provider selection is isolated behind a factory and
environment settings.

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

### Dashboard

The current generated dashboard is a static snapshot. C3 turns it into a local operational web
application focused on watchlists, current signals, model state, risk exposure, backtest summaries
and alert history.

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
