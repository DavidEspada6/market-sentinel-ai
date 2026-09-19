# Operational Product Roadmap

The C1-C7 completion track delivered the non-executing quantitative application. The following
releases make it a practical daily analysis tool while keeping paper trading as the boundary.

| Release | Version | Status | Deliverable |
| --- | --- | --- | --- |
| O1 | 2.1.0 | Complete | Curated universe, persistent watchlist and periodic multi-symbol scans |
| O2 | 2.2.0 | Current | Provider-backed symbol search, metadata and richer watchlist UX |
| O3 | 2.3.0 | Planned | Entry zones, invalidation, take-profit and exit signal lifecycle |
| O4 | 2.4.0 | Planned | Estimated/realized PnL, VaR, CVaR, exposure, drawdown and calibration |
| O5 | 2.5.0 | Planned | Production operations, notifications, data quality and continuous observability |
| O6 | 3.0.0 | Optional | Broker integration only after explicit approval and a separate security review |

## What "operational" means

At O5 the app will continuously scan configured instruments, persist every decision, alert on
new actionable changes, show paper performance and risk metrics, and recover cleanly after a
restart. It will still not submit real orders.

O6 is not required for a useful operational application. It is deliberately separate because
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
