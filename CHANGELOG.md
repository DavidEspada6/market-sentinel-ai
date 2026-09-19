# Changelog

All notable changes to Market Sentinel AI will be documented in this file.

The project follows semantic versioning once v1.0.0 is reached. Pre-1.0 releases map to the staged roadmap.

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
