# Changelog

All notable changes to Market Sentinel AI will be documented in this file.

The project follows semantic versioning once v1.0.0 is reached. Pre-1.0 releases map to the staged roadmap.

## [2.6.0] - 2026-09-19

### Added

- Added an interactive local market workspace with clickable watchlist assets.
- Added chart filters for 1 minute through 3 years and the available total history.
- Added historical OHLCV charts, approximate ATR/momentum future envelopes, entry, stop and
  target levels, and a visible non-guaranteed forecast disclaimer.
- Added `Open-Market-Sentinel.bat` and `Open-Market-Sentinel.ps1` for simple local startup.
- Added chart API and dashboard contract tests.

### Changed

- Promoted the operational product track to O6 `2.6.0`.
- Renamed the optional broker review to O7 `3.0.0` so it remains outside the non-executing app.

## [2.5.0] - 2026-09-19

### Added

- Added configurable actionable-alert deduplication with persisted `suppressed` alert records.
- Added an operations summary endpoint with watchlist, signal, alert, scheduler and health state.
- Added the continuous watchlist operations test and documented the O5 operating posture.

### Changed

- Promoted the operational product track to O5 `2.5.0`.
- Kept notification channels separate from broker execution; no real orders are supported.

## [2.4.0] - 2026-09-19

### Added

- Added paper risk analytics for estimated, realized and unrealized PnL.
- Added historical VaR and CVaR with confidence, method and sample size fields.
- Added volatility, Sharpe, Sortino, maximum drawdown, profit factor, win rate, expectancy and
  exposure metrics.
- Added `/api/v1/paper/metrics` and dashboard metric panels.
- Added O4 tests for risk calculations and API exposure.

### Changed

- Promoted the operational product track to O4 `2.4.0`.
- Kept unrealized PnL explicitly zero until the paper ledger supports open positions and valuation.

## [2.3.0] - 2026-09-19

### Added

- Added structured trade plans to persisted signals with entry price, stop/invalidation, target,
  reward/risk ratio, validity horizon and exit guidance.
- Added explicit `ENTER_LONG`, `ENTER_SHORT` and `WAIT` plan actions.
- Added O3 tests for actionable and no-trade plan behavior.

### Changed

- Promoted the operational product track to O3 `2.3.0`.
- Kept plans advisory and paper-only; they never create real orders.

## [2.2.0] - 2026-09-19

### Added

- Added a replaceable Yahoo Finance provider-backed instrument search adapter.
- Added local, provider-only and combined search modes to the API and CLI.
- Added provider metadata preservation when adding a search result to the watchlist.
- Added O2 adapter contract tests without network access or credentials.

### Changed

- Promoted the operational product track to O2 `2.2.0`.
- Kept local catalog search available when provider search is unavailable in auto mode.

## [2.1.0] - 2026-09-19

### Added

- Added a curated instrument universe covering equities, ETFs, crypto, commodities, FX and indices.
- Added a persistent SQLite watchlist seeded with featured liquid instruments.
- Added API search, add/remove watchlist and controlled watchlist-scan endpoints.
- Added CLI commands for instrument search, watchlist management and periodic watchlist scans.
- Added dashboard search, add/remove controls and a scan-now action.
- Added O1 coverage for catalog search, persistence, dashboard integration and multi-symbol scans.

### Changed

- Started the operational product track at O1 with version `2.1.0`.
- Kept all scans alert-only and paper-trading-only; real orders remain disabled.

## [2.0.0] - 2026-09-19

### Added

- Added a repository security gate for common leaked tokens, private keys, credential assignments
  and required release documentation.
- Added the `security-check` CLI command and CI security step.
- Added a C7 end-to-end test covering scan, API, dry-run alert, paper persistence, drift, health
  history and SQLite backup without network access or real credentials.
- Added final release and security documentation for the non-executing v2.0.0 posture.

### Changed

- Promoted the package to the stable C7 `2.0.0` release.
- Kept real execution disabled in every status, health and paper account response.

## [1.6.0] - 2026-09-19

### Added

- Added SQLite-backed paper accounts and simulated trade recovery across process restarts.
- Added persistent drift reports and application health history.
- Added SQLite integrity checks and backup support for operational recovery.
- Added paper account, paper trades, drift, health details and health history API endpoints.
- Added health and backup CLI commands and C6 persistence tests.

### Changed

- Updated the completion track status to C6.
- Kept real execution disabled in every persisted paper account and health response.

## [1.5.0] - 2026-09-19

### Added

- Added an RSS/Atom news adapter and compact symbol-specific news context builder.
- Added persistent Astra usage accounting for requests, cache hits, token estimates and daily cost.
- Added input/output token gates, daily cost gates and structured response validation.
- Added an audited \`/api/v1/astra-usage\` endpoint and a \`news-demo\` command.
- Added C5 tests for RSS parsing, cache reuse and budget accounting.

### Changed

- Updated the completion track status to C5.

## [1.4.0] - 2026-09-19

### Added

- Added a public Binance order-book adapter with normalized snapshots and configurable depth,
  while retaining the demo adapter behind the same contract.
- Added order-flow spread, depth, microprice and imbalance-delta features.
- Added causal higher-timeframe feature alignment that waits for component candles to close.
- Added a regime-aware ensemble that selects model weights for low, normal and high volatility.
- Added \`order-book-demo\` and updated \`ensemble-demo\` to exercise the C4 path.

### Changed

- Updated the completion track status to C4.

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
