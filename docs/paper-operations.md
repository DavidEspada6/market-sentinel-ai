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
