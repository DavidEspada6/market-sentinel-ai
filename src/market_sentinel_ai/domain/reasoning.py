from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ReasoningResult:
    signal_id: str
    generated_at: datetime
    thesis: str
    invalidation: str
    risk_notes: tuple[str, ...]
    context_sources: tuple[str, ...]
    raw_cost_tokens_estimate: int | None = None

