from __future__ import annotations

from typing import Protocol

from market_sentinel_ai.domain.order_flow import OrderBookSnapshot


class OrderBookProvider(Protocol):
    @property
    def provider_name(self) -> str:
        """Stable provider identifier used in provenance and operations."""

    def snapshot(self, symbol: str, depth: int | None = None) -> OrderBookSnapshot:
        """Return the latest normalized order-book snapshot."""
