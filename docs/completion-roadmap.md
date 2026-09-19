# Completion Roadmap

The original R0-R7 history established the architecture and thin vertical slices, but its
v1.0.0 tag did not contain every operational integration described by the product brief. The
published tags remain immutable. This completion track closes the remaining scope through
reviewable releases and ends at v2.0.0.

| Release | Version | Deliverable |
| --- | --- | --- |
| C1 | 1.1.0 | Real historical/intraday providers, ingestion quality and provenance |
| C2 | 1.2.0 | Boosting models, model artifacts, purged walk-forward evaluation and robust backtests |
| C3 | 1.3.0 | Local API, operational dashboard, scheduling, persistent signals and alerts |
| C4 | 1.4.0 | Real order-book data, aligned multi-timeframe features, regime-aware ensemble |
| C5 | 1.5.0 | News context and audited GPT-6 Astra reasoning with hard cost limits |
| C6 | 1.6.0 | Persistent paper portfolio, drift monitoring, health and recovery (current) |
| C7 | 2.0.0 | Integrated packaging, security checks, end-to-end tests and final documentation |

Every release must pass lint and tests, update documentation and changelog, and be published as
a clean commit, semantic tag and GitHub Release. Real-money execution remains outside this plan.
