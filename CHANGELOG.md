# Changelog

All notable changes to Market Sentinel AI will be documented in this file.

The project follows semantic versioning once v1.0.0 is reached. Pre-1.0 releases map to the staged roadmap.

## [1.3.0] - 2026-09-19

### Added

- Added a local FastAPI application with health, status, signal, alert, scheduler-run and scan
  endpoints.
- Added an operational HTML dashboard backed by persisted SQLite signals and alert history.
- Added a scan service that ingests market data, generates risk-gated baseline signals, persists
  them and records dry-run or configured webhook alerts.
- Added a scheduler that supports one-shot scans and a long-running polling loop for watchlists.
- Added C3 integration tests and API dependencies to CI.

## [1.2.0] - 2026-09-19

### Added

- Added trainable XGBoost and LightGBM directional models.
- Added native model artifacts with JSON manifests, library versions, feature schemas and SHA-256 checksums.
- Added causal volatility, ATR, RSI, EMA, momentum, range and calendar features.
- Added purged, expanding walk-forward evaluation with out-of-sample trading metrics.
- Added separate fees, spread and slippage accounting with PnL, equity, return, Sharpe, Sortino and drawdown outputs.
- Added `boosting-demo` and selectable boosting backends for `walk-forward-demo`.
- Added tests that train, reload and checksum both native model formats.

### Changed

- Updated the completion track status to C2.
- Updated the CLI backtest and signal cost gates to use round-trip costs.

## [1.1.0] - 2026-09-19

### Added

- Added Yahoo Finance and Stooq no-key adapters plus an Alpha Vantage historical/intraday adapter.
- Added a provider factory configured entirely through environment variables.
- Added an ingestion service with quality gates and persistent provenance records.
- Added data-quality reporting for duplicates, ordering, intraday gaps and staleness.
- Added generic `ingest` and `ingestion-runs` CLI commands.
- Added mocked provider contract tests that do not require network access or credentials.

### Changed

- Strengthened candle validation for timezone-aware timestamps and valid positive OHLC prices.
- Added Ruff linting to CI.
- Documented the completion track from v1.1.0 to the final v2.0.0 release.

## [1.0.0] - 2026-09-19

### Added

- Added paper trading ledger with simulated round-trip trades and cost handling.
- Added feature drift detector.
- Added JSONL operational event logger.
- Added CLI commands for paper trading and drift demos.
- Added v1 operations documentation.
- Added tests for paper trading, drift and event logging.

## [0.7.0] - 2026-09-19

### Added

- Added GPT-6 Astra reasoning provider using Responses API structured-output shape.
- Added reasoning cache and gated reasoning gateway.
- Added static news/context provider interface.
- Added Astra context demo CLI command with no-key fallback behavior.
- Added Astra documentation and tests for schema, cache and no-key fallback.

## [0.6.0] - 2026-09-19

### Added

- Added order-book domain objects and deterministic demo order-book snapshots.
- Added order-flow feature engine for spread, imbalance and depth.
- Added multi-timeframe candle aggregation.
- Added weighted ensemble model abstraction.
- Added volatility regime detector.
- Added CLI command for ensemble/regime/order-flow demo.
- Added tests for R5 order-flow, multi-timeframe aggregation, ensemble and regime behavior.

## [0.5.0] - 2026-09-19

### Added

- Added signal engine that gates model predictions into LONG/SHORT/NO TRADE alerts.
- Added dry-run and JSONL alert channels.
- Added generated local HTML dashboard with backtest metrics, walk-forward snapshot and current signals.
- Added CLI commands for signal and dashboard demos.
- Added tests for signal gating, alert delivery and dashboard rendering.

## [0.4.0] - 2026-09-19

### Added

- Added supervised directional dataset builder with future-label shifting.
- Added lightweight logistic directional model for dependency-free CI and local experimentation.
- Added optional XGBoost/LightGBM adapter placeholders behind explicit ML extras.
- Added walk-forward splitter and evaluator with coverage, accuracy, precision, recall and F1 metrics.
- Added CLI command for demo walk-forward evaluation.
- Added tests for labels, model fitting and walk-forward reports.

## [0.3.0] - 2026-09-19

### Added

- Added OHLCV feature engine with rolling return, volatility, wick/body and volume features.
- Added deterministic momentum baseline model producing LONG/SHORT/NO TRADE predictions.
- Added simple one-candle-ahead backtester that enters on the next candle and includes fees/slippage.
- Added CLI command for demo backtests.
- Added tests for features, baseline model and backtest metrics.

## [0.2.0] - 2026-09-19

### Added

- Added deterministic demo market data provider for local historical candles and live-like streams.
- Added SQLite candle repository with idempotent upsert and range queries.
- Added candle sequence quality validation.
- Added CLI commands for demo ingestion and candle inspection.
- Added tests for demo data and storage behavior.

## [0.1.0] - 2026-09-19

### Added

- Created R0 bootstrap release.
- Added package structure and clean domain contracts for data, features, models, reasoning, alerts and risk.
- Added environment-based settings with safe defaults and no committed secrets.
- Added release roadmap, architecture notes, risk rules, README and changelog.
- Added unit tests for configuration, release plan and core signal behavior.
- Added GitHub Actions CI workflow for tests.
