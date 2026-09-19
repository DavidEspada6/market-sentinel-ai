# Local API And Operations

C3 provides a local FastAPI service. Start it with:

\`\`\`powershell
python -m pip install -e ".[dev,ml,api]"
python -m market_sentinel_ai serve --host 127.0.0.1 --port 8765
\`\`\`

The default binding is local-only. The service does not place real orders.

## Endpoints

- \`GET /health\` returns service status, release and the hard
  \`real_orders_enabled=false\` guard.
- \`GET /api/v1/status\` returns provider and alert-mode configuration.
- \`GET /api/v1/signals\` lists persisted signals with optional \`symbol\`, \`timeframe\` and
  \`limit\`.
- \`GET /api/v1/alerts\` lists persisted alert deliveries.
- GET /api/v1/runs lists scheduler runs.
- GET /api/v1/operations/summary returns watchlist, signal, alert, scheduler and health counts.
- GET /api/v1/instruments searches the curated instrument universe with optional \`q\`,
  \`asset_class\`, \`limit\` and \`source\` filters. Source can be \`local\`, \`provider\` or
  \`auto\`.
- GET /api/v1/watchlist lists the persistent watchlist.
- POST /api/v1/watchlist adds a known or custom provider symbol.
- DELETE /api/v1/watchlist/{symbol} disables a watchlist entry.
- GET /api/v1/market/{symbol}?window=1d returns historical candles, signal context, risk levels
  and an approximate ATR/momentum future envelope. Supported windows are `1m`, `5m`, `30m`,
  `1h`, `6h`, `12h`, `1d`, `1w`, `1mo`, `3mo`, `6mo`, `1y`, `3y` and `total`.
- POST /api/v1/watchlist/scan scans every enabled watchlist instrument once and persists the
  scheduler run and resulting signals.
- GET /api/v1/astra-usage lists today's request, cache, token and estimated-cost counters.
- GET /api/v1/paper/account returns the recovered paper equity state.
- GET /api/v1/paper/trades lists persisted simulated trades.
- GET /api/v1/paper/metrics returns estimated, realized and unrealized PnL, historical VaR/CVaR,
  volatility, Sharpe, Sortino, drawdown, profit factor, win rate, expectancy and exposure.
- GET /api/v1/simulation/account returns the local simulation balance, equity, available/used
  margin, exposure, open positions and mark-to-market PnL. It refreshes positions from the
  configured market-data provider when prices are available.
- POST /api/v1/simulation/reset starts a new simulation account with `starting_equity`; it is
  refused while positions are open.
- POST /api/v1/simulation/positions opens a LONG or SHORT simulated position. Its JSON body accepts
  `symbol`, `direction`, `margin`, `leverage` from 1x to 10x and an optional current `price`.
- POST /api/v1/simulation/positions/{position_id}/close closes a local position at an optional
  supplied price or the latest provider price.
- GET /api/v1/simulation/trades lists closed simulation trades; GET /api/v1/simulation/metrics
  returns realized/unrealized/total PnL, VaR/CVaR, exposure, drawdown and performance metrics.
- GET /api/v1/drift lists persisted feature-drift reports.
- GET /api/v1/health/details runs and persists a database/application health check.
- GET /api/v1/health/history lists previous health checks.
- \`POST /api/v1/scan\` ingests the configured market data, produces a risk-gated signal and
  persists the result. The JSON body accepts \`symbol\`, \`timeframe\` and positive \`days\`.
- \`GET /\` serves the operational dashboard.

## Scheduler

Run one controlled scan:

\`\`\`powershell
python -m market_sentinel_ai schedule --symbols SPY,QQQ --timeframe 5m --once
\`\`\`

Run the polling loop:

\`\`\`powershell
python -m market_sentinel_ai schedule --symbols SPY,QQQ --timeframe 5m --interval-seconds 60
\`\`\`

Scan the persisted watchlist once or continuously:

\`\`\`powershell
python -m market_sentinel_ai watchlist-scan --once --timeframe 5m --days 5
python -m market_sentinel_ai watchlist-scan --timeframe 5m --interval-seconds 300
\`\`\`

Alerts stay in dry-run mode by default. A configured webhook is used only when
\`ALERTS_DRY_RUN=false\` and \`ALERT_WEBHOOK_URL\` is present. No broker or order-execution adapter
exists in this completion track.

For the visual workspace, see [docs/ui.md](ui.md).
