from __future__ import annotations

from collections.abc import Sequence

from market_sentinel_ai.domain.order_flow import OrderBookSnapshot
from market_sentinel_ai.ports.features import FeatureRow


class OrderFlowFeatureEngine:
    def transform(self, snapshots: Sequence[OrderBookSnapshot]) -> list[FeatureRow]:
        return [
            FeatureRow(
                symbol=snapshot.symbol,
                timestamp_iso=snapshot.captured_at.isoformat(),
                values={
                    "book_spread_bps": snapshot.spread_bps,
                    "book_imbalance": snapshot.imbalance,
                    "bid_depth": sum(level.size for level in snapshot.bids),
                    "ask_depth": sum(level.size for level in snapshot.asks),
                    "mid_price": snapshot.mid_price,
                },
            )
            for snapshot in snapshots
        ]

