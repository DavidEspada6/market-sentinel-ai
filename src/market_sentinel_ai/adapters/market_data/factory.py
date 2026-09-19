from __future__ import annotations

from market_sentinel_ai.adapters.market_data.alpha_vantage import (
    AlphaVantageMarketDataProvider,
)
from market_sentinel_ai.adapters.market_data.binance_order_book import BinanceOrderBookProvider
from market_sentinel_ai.adapters.market_data.demo import DemoMarketDataProvider
from market_sentinel_ai.adapters.market_data.stooq import StooqMarketDataProvider
from market_sentinel_ai.adapters.market_data.yahoo import YahooFinanceMarketDataProvider
from market_sentinel_ai.config import MarketDataSettings, OrderBookSettings
from market_sentinel_ai.ports.market_data import MarketDataProvider


def build_market_data_provider(settings: MarketDataSettings) -> MarketDataProvider:
    provider = settings.provider.strip().lower().replace("-", "_")
    if provider == "demo":
        return DemoMarketDataProvider()
    if provider == "stooq":
        return StooqMarketDataProvider(
            base_url=settings.base_url or "https://stooq.com/q/d/l/",
            poll_seconds=settings.poll_seconds,
        )
    if provider in {"yahoo", "yahoo_finance"}:
        return YahooFinanceMarketDataProvider(
            base_url=(
                settings.base_url
                or "https://query1.finance.yahoo.com/v8/finance/chart"
            ),
            poll_seconds=settings.poll_seconds,
        )
    if provider in {"alpha_vantage", "alphavantage"}:
        return AlphaVantageMarketDataProvider(
            settings.api_key,
            base_url=settings.base_url or "https://www.alphavantage.co/query",
            poll_seconds=settings.poll_seconds,
        )
    raise ValueError(
        f"unknown MARKET_DATA_PROVIDER {settings.provider!r}; "
        "use demo, yahoo, stooq or alpha_vantage"
    )


def build_order_book_provider(settings: OrderBookSettings) -> object:
    provider = settings.provider.strip().lower().replace("-", "_")
    if provider == "demo":
        from market_sentinel_ai.adapters.market_data.demo_order_book import DemoOrderBookProvider

        return DemoOrderBookProvider()
    if provider == "binance":
        return BinanceOrderBookProvider(
            base_url=settings.base_url or "https://api.binance.com/api/v3/depth",
            depth=settings.depth,
        )
    raise ValueError("unknown MARKET_ORDER_BOOK_PROVIDER; use demo or binance")
