from __future__ import annotations

import csv
import io
import time
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

from market_sentinel_ai.adapters.market_data.http import (
    HttpTransport,
    MarketDataProviderError,
    download,
)
from market_sentinel_ai.domain.market import Candle, Timeframe


class StooqMarketDataProvider:
    """Free daily OHLCV data from Stooq's CSV endpoint."""

    def __init__(
        self,
        *,
        base_url: str = "https://stooq.com/q/d/l/",
        poll_seconds: int = 900,
        transport: HttpTransport = download,
    ) -> None:
        if poll_seconds <= 0:
            raise ValueError("poll_seconds must be positive")
        self.base_url = base_url
        self.poll_seconds = poll_seconds
        self.transport = transport

    @property
    def provider_name(self) -> str:
        return "stooq"

    def historical_candles(
        self,
        symbol: str,
        timeframe: Timeframe,
        start: datetime,
        end: datetime,
    ) -> Iterable[Candle]:
        if timeframe is not Timeframe.ONE_DAY:
            raise ValueError("Stooq supports the 1d timeframe in this adapter")
        start_utc = _as_utc(start)
        end_utc = _as_utc(end)
        query = urlencode(
            {
                "s": _stooq_symbol(symbol),
                "d1": start_utc.strftime("%Y%m%d"),
                "d2": end_utc.strftime("%Y%m%d"),
                "i": "d",
            }
        )
        payload = self.transport(f"{self.base_url}?{query}").decode("utf-8-sig")
        if payload.lstrip().lower().startswith("<!doctype html"):
            raise MarketDataProviderError(
                "Stooq returned a browser-verification page instead of CSV data"
            )
        reader = csv.DictReader(io.StringIO(payload))
        candles: list[Candle] = []
        for row in reader:
            if not row.get("Date") or row.get("Open") in {None, "", "N/D"}:
                continue
            opened_at = datetime.strptime(row["Date"], "%Y-%m-%d").replace(tzinfo=UTC)
            if not start_utc <= opened_at < end_utc:
                continue
            candles.append(
                Candle(
                    symbol=symbol.upper(),
                    timeframe=timeframe,
                    opened_at=opened_at,
                    open=float(row["Open"]),
                    high=float(row["High"]),
                    low=float(row["Low"]),
                    close=float(row["Close"]),
                    volume=float(row.get("Volume") or 0.0),
                )
            )
        return sorted(candles, key=lambda candle: candle.opened_at)

    def stream_candles(self, symbol: str, timeframe: Timeframe) -> Iterable[Candle]:
        latest: datetime | None = None
        while True:
            end = datetime.now(tz=UTC) + timedelta(days=1)
            start = end - timedelta(days=10)
            candles = list(self.historical_candles(symbol, timeframe, start, end))
            for candle in candles:
                if latest is None or candle.opened_at > latest:
                    latest = candle.opened_at
                    yield candle
            time.sleep(self.poll_seconds)


def _stooq_symbol(symbol: str) -> str:
    normalized = symbol.strip().lower()
    return normalized if "." in normalized else f"{normalized}.us"


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamps must be timezone-aware")
    return value.astimezone(UTC)
