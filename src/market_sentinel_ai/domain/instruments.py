from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum


class AssetClass(StrEnum):
    EQUITY = "equity"
    ETF = "etf"
    CRYPTO = "crypto"
    COMMODITY = "commodity"
    FX = "fx"
    INDEX = "index"


@dataclass(frozen=True)
class Instrument:
    symbol: str
    name: str
    asset_class: AssetClass
    exchange: str
    currency: str
    provider_symbol: str | None = None
    featured: bool = False

    def __post_init__(self) -> None:
        normalized = normalize_symbol(self.symbol)
        object.__setattr__(self, "symbol", normalized)
        if not self.name.strip():
            raise ValueError("instrument name cannot be empty")

    @property
    def market_symbol(self) -> str:
        return self.provider_symbol or self.symbol

    def to_dict(self) -> dict[str, object]:
        return {
            "symbol": self.symbol,
            "name": self.name,
            "asset_class": self.asset_class.value,
            "exchange": self.exchange,
            "currency": self.currency,
            "provider_symbol": self.market_symbol,
            "featured": self.featured,
        }


_SYMBOL_PATTERN = re.compile(r"^[A-Za-z0-9._=^/-]{1,24}$")


def normalize_symbol(symbol: str) -> str:
    normalized = symbol.strip().upper()
    if not normalized or not _SYMBOL_PATTERN.fullmatch(normalized):
        raise ValueError(
            "symbol must contain only letters, numbers, '.', '_', '=', '^', '/' or '-'"
        )
    return normalized


def custom_instrument(symbol: str) -> Instrument:
    normalized = normalize_symbol(symbol)
    return Instrument(
        symbol=normalized,
        name=f"Custom instrument {normalized}",
        asset_class=AssetClass.EQUITY,
        exchange="unknown",
        currency="USD",
    )


DEFAULT_INSTRUMENTS: tuple[Instrument, ...] = (
    Instrument("SPY", "SPDR S&P 500 ETF", AssetClass.ETF, "NYSE Arca", "USD", featured=True),
    Instrument("QQQ", "Invesco QQQ Trust", AssetClass.ETF, "NASDAQ", "USD", featured=True),
    Instrument("DIA", "SPDR Dow Jones Industrial Average ETF", AssetClass.ETF, "NYSE Arca", "USD"),
    Instrument("IWM", "iShares Russell 2000 ETF", AssetClass.ETF, "NYSE Arca", "USD"),
    Instrument("VTI", "Vanguard Total Stock Market ETF", AssetClass.ETF, "NYSE Arca", "USD"),
    Instrument("TLT", "iShares 20+ Year Treasury Bond ETF", AssetClass.ETF, "NASDAQ", "USD"),
    Instrument("GLD", "SPDR Gold Shares", AssetClass.ETF, "NYSE Arca", "USD", featured=True),
    Instrument("SLV", "iShares Silver Trust", AssetClass.ETF, "NYSE Arca", "USD"),
    Instrument("AAPL", "Apple", AssetClass.EQUITY, "NASDAQ", "USD", featured=True),
    Instrument("MSFT", "Microsoft", AssetClass.EQUITY, "NASDAQ", "USD", featured=True),
    Instrument("NVDA", "NVIDIA", AssetClass.EQUITY, "NASDAQ", "USD", featured=True),
    Instrument("AMZN", "Amazon", AssetClass.EQUITY, "NASDAQ", "USD", featured=True),
    Instrument("GOOGL", "Alphabet Class A", AssetClass.EQUITY, "NASDAQ", "USD", featured=True),
    Instrument("META", "Meta Platforms", AssetClass.EQUITY, "NASDAQ", "USD"),
    Instrument("TSLA", "Tesla", AssetClass.EQUITY, "NASDAQ", "USD", featured=True),
    Instrument("BRK-B", "Berkshire Hathaway Class B", AssetClass.EQUITY, "NYSE", "USD"),
    Instrument("JPM", "JPMorgan Chase", AssetClass.EQUITY, "NYSE", "USD"),
    Instrument("AMD", "Advanced Micro Devices", AssetClass.EQUITY, "NASDAQ", "USD"),
    Instrument("BTC-USD", "Bitcoin / US Dollar", AssetClass.CRYPTO, "Yahoo", "USD", featured=True),
    Instrument("ETH-USD", "Ether / US Dollar", AssetClass.CRYPTO, "Yahoo", "USD", featured=True),
    Instrument("GC=F", "Gold Futures", AssetClass.COMMODITY, "COMEX", "USD", featured=True),
    Instrument("CL=F", "Crude Oil Futures", AssetClass.COMMODITY, "NYMEX", "USD"),
    Instrument("EURUSD=X", "Euro / US Dollar", AssetClass.FX, "Yahoo", "USD", featured=True),
    Instrument("^GSPC", "S&P 500 Index", AssetClass.INDEX, "CBOE", "USD", featured=True),
    Instrument("^IXIC", "NASDAQ Composite Index", AssetClass.INDEX, "NASDAQ", "USD"),
)


def find_instrument(symbol: str) -> Instrument | None:
    normalized = normalize_symbol(symbol)
    return next((item for item in DEFAULT_INSTRUMENTS if item.symbol == normalized), None)


def search_instruments(
    query: str = "",
    asset_class: AssetClass | None = None,
    limit: int = 50,
) -> list[Instrument]:
    if limit <= 0:
        raise ValueError("limit must be positive")
    needle = query.strip().lower()
    matches = [
        item
        for item in DEFAULT_INSTRUMENTS
        if (not asset_class or item.asset_class == asset_class)
        and (
            not needle
            or needle in item.symbol.lower()
            or needle in item.name.lower()
            or needle in item.asset_class.value
        )
    ]
    return sorted(matches, key=lambda item: (not item.featured, item.symbol))[:limit]


def featured_instruments() -> tuple[Instrument, ...]:
    return tuple(item for item in DEFAULT_INSTRUMENTS if item.featured)
