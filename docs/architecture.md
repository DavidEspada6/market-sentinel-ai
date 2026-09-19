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

Adapters will be added release by release.

### Reasoning Layer

The Astra layer is intentionally downstream of quantitative signals. It receives compact structured context only when a signal passes gating rules:

- confidence is above threshold,
- risk policy allows the setup,
- cost budget has capacity,
- the signal is not a duplicate already explained recently.

The target output is structured JSON containing a short thesis, invalidation conditions, risk notes and relevant context. Astra must not override hard risk limits.

### Storage

R1 will introduce SQLite storage by default. The storage interface will allow later replacement with Postgres, DuckDB or managed infrastructure.

### Dashboard

R4 will introduce a web dashboard focused on operational scanning: watchlist, current signals, model state, risk exposure, backtest summary and alert history.

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
- Scaling, imputation and feature selection must be fit only on training windows.
- Reported metrics must distinguish in-sample, validation and out-of-sample periods.

