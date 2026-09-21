from __future__ import annotations

import xml.etree.ElementTree as ET
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from urllib.parse import urlencode

from market_sentinel_ai.adapters.market_data.http import HttpTransport, download


@dataclass(frozen=True)
class NewsItem:
    title: str
    source: str
    published_at: datetime
    url: str | None = None
    summary: str | None = None

    def to_dict(self) -> dict[str, str | None]:
        return {
            "title": self.title,
            "source": self.source,
            "published_at": self.published_at.isoformat(),
            "url": self.url,
            "summary": self.summary,
        }


class RssNewsProvider:
    """Small RSS/Atom adapter that keeps news vendors replaceable."""

    def __init__(
        self,
        feed_urls: Sequence[str],
        *,
        transport: HttpTransport = download,
    ) -> None:
        if not feed_urls:
            raise ValueError("feed_urls cannot be empty")
        self.feed_urls = tuple(feed_urls)
        self.transport = transport

    def latest_for_symbol(self, symbol: str, limit: int = 5) -> tuple[NewsItem, ...]:
        if limit <= 0:
            raise ValueError("limit must be positive")
        items: list[NewsItem] = []
        for feed_url in self.feed_urls:
            items.extend(_parse_feed(self.transport(feed_url), feed_url))
        symbol_upper = symbol.upper()
        matches = [
            item
            for item in items
            if symbol_upper in item.title.upper() or symbol_upper in (item.summary or "").upper()
        ]
        unique = {item.url or f"{item.source}:{item.title}": item for item in matches}
        return tuple(
            sorted(unique.values(), key=lambda item: item.published_at, reverse=True)[:limit]
        )


class GoogleNewsRssProvider:
    """Credential-free live headline adapter, replaceable through the context port."""

    def __init__(
        self,
        *,
        base_url: str = "https://news.google.com/rss/search",
        transport: HttpTransport = download,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.transport = transport

    def latest_for_symbol(self, symbol: str, limit: int = 5) -> tuple[NewsItem, ...]:
        if limit <= 0:
            raise ValueError("limit must be positive")
        query = f'"{symbol.upper()}" stock OR shares OR market'
        params = {"q": query, "hl": "en-US", "gl": "US", "ceid": "US:en"}
        url = f"{self.base_url}?{urlencode(params)}"
        items = _parse_feed(self.transport(url), "google-news")
        unique = {item.url or item.title: item for item in items}
        return tuple(
            sorted(unique.values(), key=lambda item: item.published_at, reverse=True)[:limit]
        )


class NewsContextBuilder:
    def __init__(self, provider: object) -> None:
        self.provider = provider

    def for_symbol(self, symbol: str, limit: int = 5) -> dict[str, object]:
        items = self.provider.latest_for_symbol(symbol, limit)
        sentiment_score = _sentiment_score(items)
        return {
            "symbol": symbol.upper(),
            "news": [item.to_dict() for item in items],
            "news_count": len(items),
            "sources": [f"news:{item.source}" for item in items],
            "sentiment_score": sentiment_score,
            "sentiment_label": _sentiment_label(sentiment_score),
        }


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


def _parse_feed(payload: bytes, source: str) -> list[NewsItem]:
    root = ET.fromstring(payload)
    items: list[NewsItem] = []
    for element in root.iter():
        name = _local_name(element.tag)
        if name not in {"item", "entry"}:
            continue
        fields = {_local_name(child.tag): (child.text or "").strip() for child in element}
        title = fields.get("title", "")
        if not title:
            continue
        link = fields.get("link") or None
        if link is None:
            for child in element:
                if _local_name(child.tag) == "link" and child.attrib.get("href"):
                    link = child.attrib["href"]
                    break
        published = fields.get("pubDate") or fields.get("published") or fields.get("updated")
        items.append(
            NewsItem(
                title=title,
                source=source,
                published_at=_parse_datetime(published),
                url=link,
                summary=fields.get("description") or fields.get("summary") or None,
            )
        )
    return items


_POSITIVE_TERMS = {
    "beat", "beats", "bullish", "buy", "growth", "improves", "profit", "profits",
    "record", "raise", "raises", "rebound", "rises", "soars", "strong", "upgrade",
}
_NEGATIVE_TERMS = {
    "bearish", "cuts", "decline", "downgrade", "fraud", "falls", "loss", "losses",
    "miss", "misses", "probe", "recall", "recession", "slump", "warning", "weak",
}


def _sentiment_score(items: Sequence[NewsItem]) -> float:
    if not items:
        return 0.0
    scores: list[float] = []
    for item in items:
        words = set((item.title + " " + (item.summary or "")).lower().split())
        positive = len(words & _POSITIVE_TERMS)
        negative = len(words & _NEGATIVE_TERMS)
        scores.append(max(-1.0, min(1.0, (positive - negative) / 2)))
    return round(sum(scores) / len(scores), 3)


def _sentiment_label(score: float) -> str:
    if score >= 0.2:
        return "positive"
    if score <= -0.2:
        return "negative"
    return "neutral"


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _parse_datetime(value: str | None) -> datetime:
    if value:
        try:
            parsed = parsedate_to_datetime(value)
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
        except (TypeError, ValueError):
            try:
                parsed = datetime.fromisoformat(value)
                return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
            except ValueError:
                pass
    return datetime.now(tz=UTC)
