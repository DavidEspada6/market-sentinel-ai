from __future__ import annotations

import json
from urllib.parse import urlencode

from market_sentinel_ai.adapters.market_data.http import (
    HttpTransport,
    MarketDataProviderError,
    download,
)
from market_sentinel_ai.domain.instruments import AssetClass, Instrument, normalize_symbol


class YahooInstrumentSearchProvider:
    """Replaceable adapter for Yahoo Finance's public instrument search endpoint."""

    def __init__(
        self,
        *,
        base_url: str = "https://query1.finance.yahoo.com/v1/finance/search",
        transport: HttpTransport = download,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.transport = transport

    @property
    def provider_name(self) -> str:
        return "yahoo-search"

    def search(self, query: str, limit: int = 20) -> list[Instrument]:
        if not query.strip():
            raise ValueError("search query cannot be empty")
        if limit <= 0 or limit > 100:
            raise ValueError("search limit must be between 1 and 100")
        params = {"q": query.strip(), "quotesCount": limit, "newsCount": 0}
        url = f"{self.base_url}?{urlencode(params)}"
        try:
            payload = json.loads(self.transport(url))
        except (ValueError, TypeError) as exc:
            raise MarketDataProviderError("Yahoo instrument search returned invalid JSON") from exc
        quotes = payload.get("quotes") if isinstance(payload, dict) else None
        if not isinstance(quotes, list):
            raise MarketDataProviderError("Yahoo instrument search returned no quote list")

        instruments: list[Instrument] = []
        for quote in quotes:
            if not isinstance(quote, dict) or not quote.get("symbol"):
                continue
            try:
                symbol = normalize_symbol(str(quote["symbol"]))
                instruments.append(
                    Instrument(
                        symbol=symbol,
                        name=str(quote.get("longname") or quote.get("shortname") or symbol),
                        asset_class=_asset_class(str(quote.get("quoteType", "EQUITY"))),
                        exchange=str(
                            quote.get("fullExchangeName") or quote.get("exchange") or "unknown"
                        ),
                        currency=str(quote.get("currency") or "USD"),
                        provider_symbol=symbol,
                    )
                )
            except (KeyError, TypeError, ValueError):
                continue
        return instruments[:limit]


def _asset_class(quote_type: str) -> AssetClass:
    return {
        "EQUITY": AssetClass.EQUITY,
        "ETF": AssetClass.ETF,
        "CRYPTOCURRENCY": AssetClass.CRYPTO,
        "FUTURE": AssetClass.COMMODITY,
        "CURRENCY": AssetClass.FX,
        "INDEX": AssetClass.INDEX,
    }.get(quote_type.upper(), AssetClass.EQUITY)
