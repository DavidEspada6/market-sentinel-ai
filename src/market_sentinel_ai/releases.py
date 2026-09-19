from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Release:
    code: str
    version: str
    title: str
    objective: str


RELEASE_PLAN: tuple[Release, ...] = (
    Release(
        code="R0",
        version="0.1.0",
        title="Bootstrap, Architecture And Environment",
        objective="Create the repo foundation, contracts, safe configuration, docs, tests and CI.",
    ),
    Release(
        code="R1",
        version="0.2.0",
        title="Historical, Realtime And Storage",
        objective="Add market data adapters, live-like streams, normalized storage and data QA.",
    ),
    Release(
        code="R2",
        version="0.3.0",
        title="Feature Engine, Baseline Model And Backtester",
        objective="Generate OHLCV features, baseline predictions and leakage-aware backtests.",
    ),
    Release(
        code="R3",
        version="0.4.0",
        title="Supervised ML And Walk-Forward Evaluation",
        objective=(
            "Train XGBoost/LightGBM models and evaluate out-of-sample using walk-forward folds."
        ),
    ),
    Release(
        code="R4",
        version="0.5.0",
        title="Signals, Alerts And Dashboard",
        objective="Ship signal generation, alert delivery and local web dashboard.",
    ),
    Release(
        code="R5",
        version="0.6.0",
        title="Order Flow, Ensemble And Multi-Timeframe Modeling",
        objective=(
            "Add order-flow inputs, ensemble logic, multi-timeframe features and regime detection."
        ),
    ),
    Release(
        code="R6",
        version="0.7.0",
        title="GPT-6 Astra Context Layer",
        objective=(
            "Integrate Astra through gated structured reasoning, news context, "
            "caching and cost limits."
        ),
    ),
    Release(
        code="R7",
        version="1.0.0",
        title="Paper Trading, Drift, Observability And v1 Hardening",
        objective=(
            "Add paper trading, model drift monitoring, observability and v1 production hardening."
        ),
    ),
)

COMPLETION_PLAN: tuple[Release, ...] = (
    Release(
        code="C1",
        version="1.1.0",
        title="Real Market Data Foundation",
        objective="Add replaceable real-data adapters, ingestion QA and provenance.",
    ),
    Release(
        code="C2",
        version="1.2.0",
        title="Quantitative Research Pipeline",
        objective="Complete boosting models, artifacts, purged walk-forward tests and backtests.",
    ),
    Release(
        code="C3",
        version="1.3.0",
        title="Operational Signals Application",
        objective=(
            "Ship the local API, dashboard, scheduler, persistent signals and alert channels."
        ),
    ),
    Release(
        code="C4",
        version="1.4.0",
        title="Order Flow And Ensemble",
        objective="Add real order-book adapters, aligned multi-timeframe features and ensembles.",
    ),
    Release(
        code="C5",
        version="1.5.0",
        title="Astra And News Context",
        objective="Complete news ingestion and audited, budgeted GPT-6 Astra reasoning.",
    ),
    Release(
        code="C6",
        version="1.6.0",
        title="Persistent Paper Operations",
        objective="Persist paper positions, drift state, health metrics and operational recovery.",
    ),
    Release(
        code="C7",
        version="2.0.0",
        title="Final Integrated Alerting And Paper Trading Release",
        objective=(
            "Integrate, harden, package and document the complete non-executing application "
            "with repeatable security and end-to-end release gates."
        ),
    ),
)

FOLLOW_ON_PLAN: tuple[Release, ...] = (
    Release(
        code="O1",
        version="2.1.0",
        title="Known Asset Universe And Periodic Scanning",
        objective=(
            "Scan a curated universe of liquid, well-known instruments, persist a watchlist "
            "and run controlled periodic scans through the configured provider."
        ),
    ),
    Release(
        code="O2",
        version="2.2.0",
        title="Provider Search And Watchlist UX",
        objective=(
            "Add provider-backed symbol search, instrument metadata and a complete watchlist "
            "workflow for adding user-selected products."
        ),
    ),
    Release(
        code="O3",
        version="2.3.0",
        title="Entry And Exit Signal Lifecycle",
        objective=(
            "Track signal state, entry zones, invalidation, take-profit and exit conditions "
            "with deduplicated alerts."
        ),
    ),
    Release(
        code="O4",
        version="2.4.0",
        title="Portfolio Risk And Performance Analytics",
        objective=(
            "Add estimated and realized PnL, VaR, CVaR, volatility, exposure, drawdown, "
            "Sharpe, Sortino, expectancy and calibration metrics."
        ),
    ),
    Release(
        code="O5",
        version="2.5.0",
        title="Operational Product Release",
        objective=(
            "Harden scheduling, dashboards, notifications, data quality, observability and "
            "deployment for continuous alerting and paper operations."
        ),
    ),
    Release(
        code="O6",
        version="3.0.0",
        title="Optional Broker Integration Review",
        objective=(
            "Only if explicitly requested: add a separately gated broker adapter after a "
            "security review, paper track record and manual approval workflow."
        ),
    ),
)

CURRENT_RELEASE = FOLLOW_ON_PLAN[0]
