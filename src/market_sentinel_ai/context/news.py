from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class NewsItem:
    title: str
    source: str
    published_at: datetime
    url: str | None = None
    summary: str | None = None


class StaticNewsProvider:
    def __init__(self, items: Sequence[NewsItem] = ()) -> None:
        self.items = tuple(items)

    def latest_for_symbol(self, symbol: str, limit: int = 5) -> tuple[NewsItem, ...]:
        symbol_upper = symbol.upper()
        matches = [
            item
            for item in self.items
            if symbol_upper in item.title.upper() or symbol_upper in (item.summary or "").upper()
        ]
        return tuple(sorted(matches, key=lambda item: item.published_at, reverse=True)[:limit])

