# Paper Operations And Recovery

C6 persists the default paper account and simulated trades in SQLite. Restarting the process
recovers the last equity and trade history; the storage layer always writes
real_execution_enabled=false.

Run a paper simulation:

```powershell
python -m market_sentinel_ai paper-demo --symbol SPY --timeframe 5m --days 1
```

Run a database integrity check and make a backup:

```powershell
python -m market_sentinel_ai health
python -m market_sentinel_ai backup --output backups/market_sentinel.sqlite3
```

Drift and health results are persisted and available through the API. Backups are SQLite copies;
restore them only while the application is stopped and after checking the file path.

## Interactive simulation

The dashboard's **Modo simulación** uses a separate `simulation` account. Set the starting capital,
select the asset, choose the margin and leverage, then open a `LONG` or `SHORT` position. The
application marks open positions with provider prices approximately every 15 seconds while the UI
is open and updates cash balance, equity, margin, exposure and unrealized PnL. Closing a position
records a simulated trade with fees, spread and slippage from the risk configuration.

The simulator is deliberately bounded to 1x-10x leverage, refuses margin above the available
equity and exposes an approximate liquidation price for each position. If a refreshed market price
reaches that threshold, the simulator closes the position automatically as a simulated liquidation.
Resetting the account clears its simulation history and requires all positions to be closed first.
It never submits broker orders and always reports `real_orders_enabled=false`.
