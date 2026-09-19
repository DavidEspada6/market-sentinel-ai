from __future__ import annotations

from typing import Protocol

from market_sentinel_ai.domain.paper import (
    PaperAccountSnapshot,
    PaperTradeRecord,
)


class PaperPortfolioStore(Protocol):
    def load_paper_account(self, account_id: str) -> PaperAccountSnapshot | None:
        """Load the latest account state for recovery."""

    def save_paper_account(self, snapshot: PaperAccountSnapshot) -> None:
        """Persist account state with real execution disabled."""

    def record_paper_trade(self, record: PaperTradeRecord) -> None:
        """Persist one simulated trade."""

    def list_paper_trades(self, account_id: str, limit: int = 500) -> list[PaperTradeRecord]:
        """List simulated trades for an account."""
