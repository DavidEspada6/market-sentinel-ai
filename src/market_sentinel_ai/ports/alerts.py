from __future__ import annotations

from typing import Protocol

from market_sentinel_ai.domain.prediction import Signal


class AlertChannel(Protocol):
    def send(self, signal: Signal) -> str:
        """Send a signal alert and return an external or internal alert id."""

