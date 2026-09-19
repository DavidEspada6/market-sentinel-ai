from __future__ import annotations

from collections.abc import Sequence

from market_sentinel_ai.domain.order_flow import OrderBookSnapshot
from market_sentinel_ai.ports.features import FeatureRow


class OrderFlowFeatureEngine:
    def transform(self, snapshots: Sequence[OrderBookSnapshot]) -> list[FeatureRow]:
        rows: list[FeatureRow] = []
        previous_imbalance = 0.0
        for snapshot in snapshots:
            bid_depth = sum(level.size for level in snapshot.bids)
            ask_depth = sum(level.size for level in snapshot.asks)
            total_depth = bid_depth + ask_depth
            microprice = (
                (snapshot.best_ask * bid_depth + snapshot.best_bid * ask_depth) / total_depth
                if total_depth
                else snapshot.mid_price
            )
            rows.append(
                FeatureRow(
                    symbol=snapshot.symbol,
                    timestamp_iso=snapshot.captured_at.isoformat(),
                    values={
                        "book_spread_bps": snapshot.spread_bps,
                        "book_imbalance": snapshot.imbalance,
                        "book_imbalance_delta": snapshot.imbalance - previous_imbalance,
                        "bid_depth": bid_depth,
                        "ask_depth": ask_depth,
                        "mid_price": snapshot.mid_price,
                        "microprice": microprice,
                        "microprice_distance_bps": (
                            (microprice - snapshot.mid_price) / snapshot.mid_price
                        )
                        * 10_000,
                    },
                )
            )
            previous_imbalance = snapshot.imbalance
        return rows
