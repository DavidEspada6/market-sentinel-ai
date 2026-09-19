from __future__ import annotations

import random
from collections.abc import Iterable

from market_sentinel_ai.domain.market import Candle
from market_sentinel_ai.domain.order_flow import OrderBookLevel, OrderBookSnapshot


class DemoOrderBookProvider:
    def snapshots_from_candles(self, candles: Iterable[Candle]) -> Iterable[OrderBookSnapshot]:
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
                for level in range(5)
            )
            asks = tuple(
                OrderBookLevel(
                    price=round(ask_base * (1 + level * 0.00005), 6),
                    size=round((1_000 + rng.randint(0, 3_000)) * ask_bias, 3),
                )
                for level in range(5)
            )
            yield OrderBookSnapshot(
                symbol=candle.symbol,
                captured_at=candle.opened_at,
                bids=bids,
                asks=asks,
            )

