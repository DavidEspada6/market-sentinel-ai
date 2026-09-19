from __future__ import annotations

from typing import Protocol

from market_sentinel_ai.domain.instruments import Instrument


class InstrumentSearchProvider(Protocol):
    @property
    def provider_name(self) -> str:
        """Stable provider identifier used in operations and diagnostics."""

    def search(self, query: str, limit: int = 20) -> list[Instrument]:
        """Search provider instruments by symbol or human-readable name."""
