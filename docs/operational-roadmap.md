# Operational Product Roadmap

The C1-C7 completion track delivered the non-executing quantitative application. The following
releases make it a practical daily analysis tool while keeping paper trading as the boundary.

| Release | Version | Status | Deliverable |
| --- | --- | --- | --- |
| O1 | 2.1.0 | Complete | Curated universe, persistent watchlist and periodic multi-symbol scans |
| O2 | 2.2.0 | Complete | Provider-backed symbol search, metadata and richer watchlist UX |
| O3 | 2.3.0 | Complete | Entry zones, invalidation, take-profit and exit signal lifecycle |
| O4 | 2.4.0 | Complete | Estimated/realized PnL, VaR, CVaR, exposure, drawdown and calibration |
| O5 | 2.5.0 | Complete | Production operations, notifications, data quality and continuous observability |
| O6 | 2.6.0 | Complete | Interactive color dashboard, chart windows, future scenarios and visual risk levels |
| O7 | 2.7.1 | Current | Complete UI control center for scanning, paper metrics and diagnostics |
| O8 | 3.0.0 | Optional | Broker integration only after explicit approval and a separate security review |

## What "operational" means

At O7 the app continuously scans configured instruments, persists every decision, alerts on new
actionable changes, shows paper performance and risk metrics, and exposes scanning, diagnostics,
paper history and context usage directly in the visual workspace. It still does not submit real
orders.

O8 is not required for a useful operational application. It is deliberately separate because
real execution adds authentication, broker-specific behavior, reconciliation, order state,
manual approval and incident-response requirements that should not be mixed into the analysis
track.

## Essential additions

- Data quality and market-calendar checks before trusting a scan.
- A clear `NO TRADE` state when costs, uncertainty or drift invalidate a setup.
- Entry range, stop/invalidation, target range, time horizon and confidence for every actionable
  signal.
- Realized and unrealized PnL separated from model-estimated PnL.
- VaR and CVaR reported with method, horizon, confidence level and sample size.
- Alert deduplication, stale-data warnings, backups and a kill switch for notifications.
- Out-of-sample and paper results before any consideration of broker connectivity.
