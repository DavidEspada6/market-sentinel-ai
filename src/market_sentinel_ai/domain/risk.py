from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RiskLimits:
    max_position_pct: float
    max_daily_loss_pct: float
    fee_bps: float
    slippage_bps: float
    spread_bps: float = 0.0

    def __post_init__(self) -> None:
        for field_name, value in (
            ("max_position_pct", self.max_position_pct),
            ("max_daily_loss_pct", self.max_daily_loss_pct),
            ("fee_bps", self.fee_bps),
            ("slippage_bps", self.slippage_bps),
            ("spread_bps", self.spread_bps),
        ):
            if value < 0:
                raise ValueError(f"{field_name} cannot be negative")
