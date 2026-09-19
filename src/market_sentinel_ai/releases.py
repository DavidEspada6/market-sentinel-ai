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
        objective="Train XGBoost/LightGBM models and evaluate out-of-sample using walk-forward folds.",
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
        objective="Add order-flow inputs, ensemble logic, multi-timeframe features and regime detection.",
    ),
    Release(
        code="R6",
        version="0.7.0",
        title="GPT-6 Astra Context Layer",
        objective="Integrate Astra through gated structured reasoning, news context, caching and cost limits.",
    ),
    Release(
        code="R7",
        version="1.0.0",
        title="Paper Trading, Drift, Observability And v1 Hardening",
        objective="Add paper trading, model drift monitoring, observability and v1 production hardening.",
    ),
)

CURRENT_RELEASE = RELEASE_PLAN[1]
