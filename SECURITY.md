# Security And Trading Boundaries

Market Sentinel AI is designed for alerting and paper trading. Version 2.0.0 does not
connect to a broker account and does not submit, amend or cancel real orders.

## Secret handling

- Copy `.env.example` to a local `.env` file and keep the local file untracked.
- Store API keys and webhook credentials in environment variables or the local `.env` file.
- Never place tokens, private keys, broker credentials or production database exports in Git.
- Run `python -m market_sentinel_ai security-check` before creating a release.

The security check intentionally skips local secret files and generated runtime directories.
It still scans source, documentation and configuration examples for common token formats,
private keys and non-empty credential assignments.

## Operational boundaries

- `real_orders_enabled` is always `false` in status, health and paper account responses.
- Alerts are dry-run by default. A webhook is notification-only and is not an order endpoint.
- Market data providers, news feeds and Astra context are replaceable adapters with explicit
  budgets and no implicit credential fallback.
- Backtests and paper results are decision-support output, not financial advice.

Report suspected credential exposure by rotating the credential first, then removing it from
the repository history and opening a private issue with the relevant commit and release.
