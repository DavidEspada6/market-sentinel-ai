# Local API And Operations

C3 provides a local FastAPI service. Start it with:

\`\`\`powershell
python -m pip install -e ".[dev,ml,api]"
python -m market_sentinel_ai serve --host 127.0.0.1 --port 8000
\`\`\`

The default binding is local-only. The service does not place real orders.

## Endpoints

- \`GET /health\` returns service status, release and the hard
  \`real_orders_enabled=false\` guard.
- \`GET /api/v1/status\` returns provider and alert-mode configuration.
- \`GET /api/v1/signals\` lists persisted signals with optional \`symbol\`, \`timeframe\` and
  \`limit\`.
- \`GET /api/v1/alerts\` lists persisted alert deliveries.
- \`GET /api/v1/runs\` lists scheduler runs.
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

Alerts stay in dry-run mode by default. A configured webhook is used only when
\`ALERTS_DRY_RUN=false\` and \`ALERT_WEBHOOK_URL\` is present. No broker or order-execution adapter
exists in this completion track.
