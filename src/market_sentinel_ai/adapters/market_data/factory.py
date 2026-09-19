from __future__ import annotations

from market_sentinel_ai.adapters.market_data.alpha_vantage import (
    AlphaVantageMarketDataProvider,
)
from market_sentinel_ai.adapters.market_data.demo import DemoMarketDataProvider
from market_sentinel_ai.adapters.market_data.stooq import StooqMarketDataProvider
from market_sentinel_ai.adapters.market_data.yahoo import YahooFinanceMarketDataProvider
from market_sentinel_ai.config import MarketDataSettings
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
