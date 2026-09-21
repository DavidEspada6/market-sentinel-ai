from __future__ import annotations

import os
from dataclasses import dataclass


def _env_str(name: str, default: str) -> str:
    value = os.getenv(name)
    return default if value is None or value == "" else value


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return float(value)


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return int(value)


def _env_csv(name: str) -> tuple[str, ...]:
    value = os.getenv(name, "")
    return tuple(item.strip() for item in value.split(",") if item.strip())


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


@dataclass(frozen=True)
class OpenAISettings:
    api_key: str
    model: str
    reasoning_effort: str
    max_context_requests_per_day: int
    min_signal_confidence: float
    max_input_tokens_per_request: int
    max_output_tokens_per_request: int
    max_daily_cost_usd: float
    input_cost_per_million: float
    output_cost_per_million: float
    usage_path: str

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)


@dataclass(frozen=True)
class MarketDataSettings:
    provider: str
    api_key: str
    base_url: str
    poll_seconds: int

    @property
    def has_credentials(self) -> bool:
        return bool(self.api_key)


@dataclass(frozen=True)
class InstrumentSearchSettings:
    provider: str
    base_url: str


@dataclass(frozen=True)
class OrderBookSettings:
    provider: str
    base_url: str
    depth: int
    poll_seconds: int


@dataclass(frozen=True)
class NewsSettings:
    provider: str
    feed_urls: tuple[str, ...]
    poll_seconds: int
    max_items: int


@dataclass(frozen=True)
class AlertSettings:
    dry_run: bool
    dedupe_minutes: int
    email_from: str
    email_to: str
    webhook_url: str


@dataclass(frozen=True)
class RiskSettings:
    max_position_pct: float
    max_daily_loss_pct: float
    default_fee_bps: float
    default_slippage_bps: float
    default_spread_bps: float


@dataclass(frozen=True)
class Settings:
    environment: str
    database_url: str
    openai: OpenAISettings
    market_data: MarketDataSettings
    instrument_search: InstrumentSearchSettings
    order_book: OrderBookSettings
    news: NewsSettings
    alerts: AlertSettings
    risk: RiskSettings

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            environment=_env_str("MARKET_SENTINEL_ENV", "local"),
            database_url=_env_str(
                "MARKET_SENTINEL_DB_URL",
                "sqlite:///./data/market_sentinel.sqlite3",
            ),
            openai=OpenAISettings(
                api_key=_env_str("OPENAI_API_KEY", ""),
                model=_env_str("OPENAI_MODEL", "gpt-6-astra"),
                reasoning_effort=_env_str("OPENAI_REASONING_EFFORT", "low"),
                max_context_requests_per_day=_env_int("ASTRA_MAX_CONTEXT_REQUESTS_PER_DAY", 25),
                min_signal_confidence=_env_float("ASTRA_MIN_SIGNAL_CONFIDENCE", 0.72),
                max_input_tokens_per_request=_env_int("ASTRA_MAX_INPUT_TOKENS_PER_REQUEST", 4000),
                max_output_tokens_per_request=_env_int(
                    "ASTRA_MAX_OUTPUT_TOKENS_PER_REQUEST", 800
                ),
                max_daily_cost_usd=_env_float("ASTRA_MAX_DAILY_COST_USD", 2.0),
                input_cost_per_million=_env_float("ASTRA_INPUT_COST_PER_MILLION", 10.0),
                output_cost_per_million=_env_float("ASTRA_OUTPUT_COST_PER_MILLION", 50.0),
                usage_path=_env_str("ASTRA_USAGE_PATH", "logs/astra-usage.jsonl"),
            ),
            market_data=MarketDataSettings(
                provider=_env_str("MARKET_DATA_PROVIDER", "yahoo"),
                api_key=_env_str("MARKET_DATA_API_KEY", ""),
                base_url=_env_str("MARKET_DATA_BASE_URL", ""),
                poll_seconds=_env_int("MARKET_DATA_POLL_SECONDS", 60),
            ),
            instrument_search=InstrumentSearchSettings(
                provider=_env_str("INSTRUMENT_SEARCH_PROVIDER", "yahoo"),
                base_url=_env_str(
                    "INSTRUMENT_SEARCH_BASE_URL",
                    "https://query1.finance.yahoo.com/v1/finance/search",
                ),
            ),
            order_book=OrderBookSettings(
                provider=_env_str("MARKET_ORDER_BOOK_PROVIDER", "demo"),
                base_url=_env_str("MARKET_ORDER_BOOK_BASE_URL", ""),
                depth=_env_int("MARKET_ORDER_BOOK_DEPTH", 20),
                poll_seconds=_env_int("MARKET_ORDER_BOOK_POLL_SECONDS", 10),
            ),
            news=NewsSettings(
                provider=_env_str("MARKET_NEWS_PROVIDER", "google_rss"),
                feed_urls=_env_csv("MARKET_NEWS_FEED_URLS"),
                poll_seconds=_env_int("MARKET_NEWS_POLL_SECONDS", 300),
                max_items=_env_int("MARKET_NEWS_MAX_ITEMS", 5),
            ),
            alerts=AlertSettings(
                dry_run=_env_bool("ALERTS_DRY_RUN", True),
                dedupe_minutes=_env_int("ALERT_DEDUPE_MINUTES", 30),
                email_from=_env_str("ALERT_EMAIL_FROM", ""),
                email_to=_env_str("ALERT_EMAIL_TO", ""),
                webhook_url=_env_str("ALERT_WEBHOOK_URL", ""),
            ),
            risk=RiskSettings(
                max_position_pct=_env_float("RISK_MAX_POSITION_PCT", 0.02),
                max_daily_loss_pct=_env_float("RISK_MAX_DAILY_LOSS_PCT", 0.03),
                default_fee_bps=_env_float("RISK_DEFAULT_FEE_BPS", 1.0),
                default_slippage_bps=_env_float("RISK_DEFAULT_SLIPPAGE_BPS", 2.0),
                default_spread_bps=_env_float("RISK_DEFAULT_SPREAD_BPS", 1.0),
            ),
        )
