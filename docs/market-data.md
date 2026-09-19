# Market Data

Market-data providers implement the same port and return normalized, timezone-aware OHLCV
candles. Select a provider with `MARKET_DATA_PROVIDER` or the CLI `--provider` option.

## Yahoo Finance

`yahoo` is the primary no-key provider. It supports 1m, 5m, 15m, 1h and 1d candles through the
public chart endpoint. Yahoo limits how far back fine-grained intraday intervals can be requested;
provider errors are surfaced and recorded as failed ingestion runs.

## Alpha Vantage

`alpha_vantage` supports daily and intraday candles and requires `MARKET_DATA_API_KEY`. Free plans
have request limits. Rate-limit and provider messages are raised explicitly and recorded without
storing partial batches.

## Stooq

`stooq` supports daily CSV data without a key. Some regions receive a browser-verification page;
the adapter detects that response and fails clearly rather than treating HTML as an empty dataset.

## Quality And Provenance

Every ingestion requires at least one candle and rejects duplicate or out-of-order timestamps.
The report also records intraday gaps and staleness. Completed and failed runs are retained in
SQLite with provider, symbol, timeframe, interval, counts and error details.
