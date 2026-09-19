# v2.0.0 Final Release

Market Sentinel AI v2.0.0 is the complete non-executing application described by the
completion roadmap. It continuously supports a cheap quantitative loop and uses GPT-6 Astra
only as a gated contextual reasoning layer for selected signals.

## End-to-end flow

1. Ingest demo or provider-backed OHLCV data through a replaceable market-data adapter.
2. Store candles and provenance in SQLite with quality checks.
3. Build causal OHLCV, volatility, order-flow and multi-timeframe features.
4. Produce baseline, boosting or regime-aware ensemble predictions.
5. Evaluate strategies with purged walk-forward splits and fees, spread and slippage.
6. Convert predictions into LONG, SHORT or NO TRADE signals using probability and risk gates.
7. Persist signals, dry-run/webhook alerts, paper trades, drift reports and health history.
8. Request Astra context only when confidence and daily token/cost budgets allow it.
9. Expose the state through the local API, dashboard, CLI and recovery backup command.

## Release gate

The repository gate is:

```powershell
ruff check src tests
python -m unittest discover -s tests
python -m market_sentinel_ai security-check
python -m pip wheel . --no-deps --no-build-isolation --wheel-dir dist
```

The CI workflow runs the same lint, test, security and wheel checks on pushes and pull
requests. `tests/test_c7_final.py` exercises the integrated scan, API, paper, drift, health and
backup path without network access or real credentials.

## Production posture

The supported deployment is a local or privately hosted alerting and paper-trading service.
Keep `.env` outside version control, use a real market-data adapter only after checking its
quality history, keep Astra budgets bounded, review out-of-sample metrics, monitor drift and
maintain SQLite backups. Broker execution is intentionally outside v2.0.0.

See [SECURITY.md](../SECURITY.md), [paper operations](paper-operations.md), [risk rules](risk.md),
and [Astra controls](astra.md) before operating the service.
