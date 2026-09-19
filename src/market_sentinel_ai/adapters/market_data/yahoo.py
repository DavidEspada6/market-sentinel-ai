from __future__ import annotations

import json
import time
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from urllib.parse import quote, urlencode

from market_sentinel_ai.adapters.market_data.http import (
    HttpTransport,
    MarketDataProviderError,
    download,
)
from market_sentinel_ai.domain.market import Candle, Timeframe

_INTERVALS: dict[Timeframe, str] = {
    Timeframe.ONE_MINUTE: "1m",
    Timeframe.FIVE_MINUTES: "5m",
    Timeframe.FIFTEEN_MINUTES: "15m",
    Timeframe.ONE_HOUR: "60m",
    Timeframe.ONE_DAY: "1d",
}


class YahooFinanceMarketDataProvider:
    """OHLCV adapter for Yahoo Finance's public chart endpoint."""

    def __init__(
        self,
        *,
        base_url: str = "https://query1.finance.yahoo.com/v8/finance/chart",
        poll_seconds: int = 60,
        transport: HttpTransport = download,
    ) -> None:
        if poll_seconds <= 0:
            raise ValueError("poll_seconds must be positive")
        self.base_url = base_url.rstrip("/")
        self.poll_seconds = poll_seconds
        self.transport = transport

    @property
    def provider_name(self) -> str:
        return "yahoo"

    def historical_candles(
        self,
        symbol: str,
        timeframe: Timeframe,
        start: datetime,
        end: datetime,
    ) -> Iterable[Candle]:
        start_utc = _as_utc(start)
        end_utc = _as_utc(end)
        query = urlencode(
            {
                "period1": int(start_utc.timestamp()),
                "period2": int(end_utc.timestamp()),
                "interval": _INTERVALS[timeframe],
                "events": "history",
                "includePrePost": "false",
            }
        )
        url = f"{self.base_url}/{quote(symbol.upper(), safe='^-=')}?{query}"
        payload = json.loads(self.transport(url))
        chart = payload.get("chart") if isinstance(payload, dict) else None
        error = chart.get("error") if isinstance(chart, dict) else None
        if error:
            raise MarketDataProviderError(str(error))
        results = chart.get("result") if isinstance(chart, dict) else None
        if not results:
            raise MarketDataProviderError("Yahoo Finance returned no chart result")
        result = results[0]
        timestamps = result.get("timestamp") or []
        indicators = result.get("indicators") or {}
        quotes = indicators.get("quote") or []
        if not quotes:
            raise MarketDataProviderError("Yahoo Finance returned no OHLCV quote data")
        quote_values = quotes[0]

        candles: list[Candle] = []
        for index, timestamp in enumerate(timestamps):
            values = {
                name: _at(quote_values.get(name), index)
                for name in ("open", "high", "low", "close", "volume")
            }
            if any(values[name] is None for name in ("open", "high", "low", "close")):
                continue
            opened_at = datetime.fromtimestamp(timestamp, tz=UTC)
            if not start_utc <= opened_at < end_utc:
                continue
            candles.append(
                Candle(
                    symbol=symbol.upper(),
                    timeframe=timeframe,
                    opened_at=opened_at,
                    open=float(values["open"]),
                    high=float(values["high"]),
                    low=float(values["low"]),
                    close=float(values["close"]),
                    volume=float(values["volume"] or 0.0),
                )
            )
        return sorted(candles, key=lambda candle: candle.opened_at)

    def stream_candles(self, symbol: str, timeframe: Timeframe) -> Iterable[Candle]:
        latest: datetime | None = None
        while True:
            end = datetime.now(tz=UTC) + timedelta(minutes=1)
            lookback = timedelta(days=7 if timeframe is Timeframe.ONE_MINUTE else 60)
            candles = list(self.historical_candles(symbol, timeframe, end - lookback, end))
            for candle in candles:
                if latest is None or candle.opened_at > latest:
                    latest = candle.opened_at
                    yield candle
            time.sleep(self.poll_seconds)


def _at(values: object, index: int) -> object | None:
    if not isinstance(values, list) or index >= len(values):
        return None
    return values[index]


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamps must be timezone-aware")
    return value.astimezone(UTC)
