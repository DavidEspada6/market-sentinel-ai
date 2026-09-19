from __future__ import annotations

import json
import time
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from market_sentinel_ai.adapters.market_data.http import (
    HttpTransport,
    MarketDataProviderError,
    download,
)
from market_sentinel_ai.domain.market import Candle, Timeframe

_INTERVALS: dict[Timeframe, str] = {
    Timeframe.ONE_MINUTE: "1min",
    Timeframe.FIVE_MINUTES: "5min",
    Timeframe.FIFTEEN_MINUTES: "15min",
    Timeframe.ONE_HOUR: "60min",
}


class AlphaVantageMarketDataProvider:
    """Historical and polled intraday OHLCV data from Alpha Vantage."""

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = "https://www.alphavantage.co/query",
        poll_seconds: int = 60,
        transport: HttpTransport = download,
    ) -> None:
        if not api_key:
            raise ValueError("Alpha Vantage requires MARKET_DATA_API_KEY")
        if poll_seconds <= 0:
            raise ValueError("poll_seconds must be positive")
        self.api_key = api_key
        self.base_url = base_url
        self.poll_seconds = poll_seconds
        self.transport = transport

    @property
    def provider_name(self) -> str:
        return "alpha_vantage"

    def historical_candles(
        self,
        symbol: str,
        timeframe: Timeframe,
        start: datetime,
        end: datetime,
    ) -> Iterable[Candle]:
        start_utc = _as_utc(start)
        end_utc = _as_utc(end)
        params: dict[str, str] = {
            "symbol": symbol.upper(),
            "apikey": self.api_key,
            "datatype": "json",
            "outputsize": "full",
        }
        if timeframe is Timeframe.ONE_DAY:
            params["function"] = "TIME_SERIES_DAILY"
            series_key = "Time Series (Daily)"
        else:
            try:
                interval = _INTERVALS[timeframe]
            except KeyError as exc:
                raise ValueError(f"unsupported Alpha Vantage timeframe: {timeframe}") from exc
            params.update({"function": "TIME_SERIES_INTRADAY", "interval": interval})
            series_key = f"Time Series ({interval})"

        payload = json.loads(self.transport(f"{self.base_url}?{urlencode(params)}"))
        _raise_provider_error(payload)
        series = payload.get(series_key)
        if not isinstance(series, dict):
            raise MarketDataProviderError(f"Alpha Vantage response lacks {series_key}")
        timezone = _response_timezone(payload)

        candles: list[Candle] = []
        for timestamp, values in series.items():
            timestamp_format = "%Y-%m-%d" if timeframe is Timeframe.ONE_DAY else "%Y-%m-%d %H:%M:%S"
            opened_at = datetime.strptime(timestamp, timestamp_format).replace(tzinfo=timezone)
            opened_at = opened_at.astimezone(UTC)
            if not start_utc <= opened_at < end_utc:
                continue
            candles.append(
                Candle(
                    symbol=symbol.upper(),
                    timeframe=timeframe,
                    opened_at=opened_at,
                    open=float(values["1. open"]),
                    high=float(values["2. high"]),
                    low=float(values["3. low"]),
                    close=float(values["4. close"]),
                    volume=float(values["5. volume"]),
                )
            )
        return sorted(candles, key=lambda candle: candle.opened_at)

    def stream_candles(self, symbol: str, timeframe: Timeframe) -> Iterable[Candle]:
        latest: datetime | None = None
        while True:
            end = datetime.now(tz=UTC) + timedelta(minutes=1)
            start = end - timedelta(days=5)
            candles = list(self.historical_candles(symbol, timeframe, start, end))
            for candle in candles:
                if latest is None or candle.opened_at > latest:
                    latest = candle.opened_at
                    yield candle
            time.sleep(self.poll_seconds)


def _raise_provider_error(payload: object) -> None:
    if not isinstance(payload, dict):
        raise MarketDataProviderError("Alpha Vantage returned an invalid JSON object")
    for key in ("Error Message", "Note", "Information"):
        message = payload.get(key)
        if message:
            raise MarketDataProviderError(str(message))


def _response_timezone(payload: dict[str, object]):
    metadata = payload.get("Meta Data")
    timezone_name = "UTC"
    if isinstance(metadata, dict):
        timezone_name = str(metadata.get("6. Time Zone") or metadata.get("5. Time Zone") or "UTC")
    if timezone_name.upper() in {"UTC", "GMT"}:
        return UTC
    aliases = {"US/Eastern": "America/New_York"}
    try:
        return ZoneInfo(aliases.get(timezone_name, timezone_name))
    except ZoneInfoNotFoundError as exc:
        raise MarketDataProviderError(
            f"timezone data is unavailable for Alpha Vantage timezone {timezone_name!r}"
        ) from exc


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamps must be timezone-aware")
    return value.astimezone(UTC)
