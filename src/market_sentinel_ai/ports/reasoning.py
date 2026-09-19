from __future__ import annotations

from typing import Protocol

from market_sentinel_ai.domain.prediction import Signal
from market_sentinel_ai.domain.reasoning import ReasoningResult


class ReasoningProvider(Protocol):
    def explain_signal(self, signal: Signal, context: dict[str, object]) -> ReasoningResult:
        """Return structured context and reasoning for an already-gated signal."""

