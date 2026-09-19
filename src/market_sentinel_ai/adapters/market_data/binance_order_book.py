from __future__ import annotations

import json
from datetime import UTC, datetime
from urllib.parse import urlencode

from market_sentinel_ai.adapters.market_data.http import (
    HttpTransport,
    MarketDataProviderError,
    download,
)
from market_sentinel_ai.domain.order_flow import OrderBookLevel, OrderBookSnapshot


class BinanceOrderBookProvider:
    """Public Binance depth adapter; no account credentials are required."""

    def __init__(
        self,
        *,
        base_url: str = "https://api.binance.com/api/v3/depth",
        depth: int = 20,
        transport: HttpTransport = download,
    ) -> None:
        if depth <= 0 or depth > 5000:
            raise ValueError("depth must be between 1 and 5000")
        self.base_url = base_url
        self.depth = depth
        self.transport = transport

    @property
    def provider_name(self) -> str:
        return "binance"

    def snapshot(self, symbol: str, depth: int | None = None) -> OrderBookSnapshot:
        requested_depth = self.depth if depth is None else depth
        if requested_depth <= 0 or requested_depth > 5000:
            raise ValueError("depth must be between 1 and 5000")
        url = f"{self.base_url}?{urlencode({'symbol': symbol.upper(), 'limit': requested_depth})}"
        try:
            payload = json.loads(self.transport(url))
        except (ValueError, TypeError) as exc:
            raise MarketDataProviderError("Binance returned invalid JSON") from exc
        if not isinstance(payload, dict) or "bids" not in payload or "asks" not in payload:
            raise MarketDataProviderError(f"Binance order-book error: {payload}")
        try:
            bids = tuple(_level(item) for item in payload["bids"])
            asks = tuple(_level(item) for item in payload["asks"])
        except (KeyError, TypeError, ValueError) as exc:
            raise MarketDataProviderError("Binance returned malformed order-book levels") from exc
        if not bids or not asks:
            raise MarketDataProviderError("Binance returned an empty order book")
        return OrderBookSnapshot(
            symbol=symbol.upper(),
            captured_at=datetime.now(tz=UTC),
            bids=bids,
            asks=asks,
        )


def _level(value: object) -> OrderBookLevel:
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError("order-book level must contain price and size")
    return OrderBookLevel(price=float(value[0]), size=float(value[1]))
