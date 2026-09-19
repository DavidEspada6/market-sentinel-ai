# Release Plan

The plan has eight releases for a complete v1. Each release should end with tests, documentation updates, a clean commit, a semantic tag and a GitHub Release.

## R0 - Bootstrap, Architecture And Environment

Version: `0.1.0`

- Create repository structure.
- Define domain contracts and module boundaries.
- Add safe configuration and `.env.example`.
- Add README, architecture documentation, risk documentation and changelog.
- Add baseline tests and CI.

Exit criteria:

- `python -m unittest discover -s tests` passes.
- The repository has a clean commit and tag.

## R1 - Historical, Realtime And Storage

Version: `0.2.0`

- Add historical OHLCV ingestion.
- Add demo/live-like streaming adapter.
- Add storage repository, initially SQLite.
- Add data quality checks and normalized schemas.
- Add CLI commands for fetching and inspecting data.

Exit criteria:

- Repeatable ingestion from fixture/demo data.
- Storage tests cover idempotency and schema behavior.

## R2 - Feature Engine, Baseline Model And Backtester

Version: `0.3.0`

- Add OHLCV, volatility and indicator features.
- Add multi-timeframe aggregation.
- Add naive baseline models.
- Add backtesting with fees, spread and slippage.
- Add metrics: expectancy, PnL, Profit Factor, Sharpe, Sortino and Max Drawdown.

Exit criteria:

- Leakage-aware backtest tests.
- Baseline model produces LONG/SHORT/NO TRADE predictions.

## R3 - Supervised ML And Walk-Forward Evaluation

Version: `0.4.0`

- Add XGBoost/LightGBM adapters.
- Add train/evaluate pipelines.
- Add walk-forward splitting.
- Add out-of-sample reports.
- Add classification and trading metrics.

Exit criteria:

- Training can run on stored sample data.
- Reports clearly separate train/validation/test windows.

## R4 - Signals, Alerts And Dashboard

Version: `0.5.0`

- Add signal engine and alert gating.
- Add email/webhook adapters in dry-run mode.
- Add dashboard with watchlist, signals, model health and backtest summaries.
- Add alert history persistence.

Exit criteria:

- Dashboard runs locally.
- Alerts are testable without real credentials.

## R5 - Order Flow, Ensemble And Multi-Timeframe Modeling

Version: `0.6.0`

- Add order-book/order-flow interfaces and sample adapter.
- Add ensemble model abstraction.
- Add multi-timeframe feature joins.
- Add regime detector.

Exit criteria:

- Ensemble combines baseline and ML predictions reproducibly.
- Regime state is visible in signals and dashboard.

## R6 - GPT-6 Astra Context Layer

Version: `0.7.0`

- Add OpenAI Responses API adapter.
- Add structured output schema.
- Add news/context ingestion interface.
- Add cache and daily budget controls.
- Call Astra only when signal gates pass.

Exit criteria:

- No OpenAI key is needed for tests.
- Astra calls are cached, audited and cost-limited.

## R7 - Paper Trading, Drift, Observability And v1 Hardening

Version: `1.0.0`

- Add paper trading ledger.
- Add drift detection and model monitoring.
- Add observability and operational logs.
- Add hardening pass, documentation and release packaging.

Exit criteria:

- The app is usable end to end for alerts and paper trading.
- No real-money execution is enabled.
- CI passes and v1.0.0 GitHub Release is published.

