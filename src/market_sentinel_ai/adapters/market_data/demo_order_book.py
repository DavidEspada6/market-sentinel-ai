from __future__ import annotations

import random
from collections.abc import Iterable
from datetime import UTC, datetime

from market_sentinel_ai.domain.market import Candle, Timeframe
from market_sentinel_ai.domain.order_flow import OrderBookLevel, OrderBookSnapshot


class DemoOrderBookProvider:
    @property
    def provider_name(self) -> str:
        return "demo-order-book"

    def snapshot(self, symbol: str, depth: int | None = None) -> OrderBookSnapshot:
        level_count = 5 if depth is None else depth
        if level_count <= 0:
            raise ValueError("depth must be positive")
        candle = Candle(
            symbol=symbol.upper(),
            timeframe=Timeframe.ONE_MINUTE,
            opened_at=datetime.now(tz=UTC),
            open=100.0,
            high=100.1,
            low=99.9,
            close=100.0,
            volume=100_000.0,
        )
        return next(iter(self.snapshots_from_candles([candle], depth=level_count)))

    def snapshots_from_candles(
        self,
        candles: Iterable[Candle],
        *,
        depth: int = 5,
    ) -> Iterable[OrderBookSnapshot]:
        if depth <= 0:
            raise ValueError("depth must be positive")
        for candle in candles:
            rng = random.Random(f"book:{candle.symbol}:{candle.opened_at.isoformat()}")
            half_spread = rng.uniform(0.5, 4.0) / 10_000
            bid_base = candle.close * (1 - half_spread)
            ask_base = candle.close * (1 + half_spread)
            bid_bias = rng.uniform(0.8, 1.3)
            ask_bias = rng.uniform(0.8, 1.3)
            bids = tuple(
                OrderBookLevel(
                    price=round(bid_base * (1 - level * 0.00005), 6),
                    size=round((1_000 + rng.randint(0, 3_000)) * bid_bias, 3),
                )
                for level in range(depth)
            )
            asks = tuple(
                OrderBookLevel(
                    price=round(ask_base * (1 + level * 0.00005), 6),
                    size=round((1_000 + rng.randint(0, 3_000)) * ask_bias, 3),
                )
                for level in range(depth)
            )
            yield OrderBookSnapshot(
                symbol=candle.symbol,
                captured_at=candle.opened_at,
                bids=bids,
                asks=asks,
            )
