from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from market_sentinel_ai.domain.market import Candle, Timeframe
from market_sentinel_ai.domain.prediction import Direction, Signal
from market_sentinel_ai.ports.features import FeatureRow


@dataclass(frozen=True)
class TradePlan:
    action: str
    entry_price: float | None
    stop_loss_price: float | None
    take_profit_price: float | None
    risk_bps: float | None
    reward_bps: float | None
    reward_risk_ratio: float | None
    valid_until_iso: str
    exit_guidance: str

    def to_metadata(self) -> dict[str, str | float | int | bool]:
        return {
            "plan_action": self.action,
            "entry_price": self.entry_price or 0.0,
            "stop_loss_price": self.stop_loss_price or 0.0,
            "take_profit_price": self.take_profit_price or 0.0,
            "plan_risk_bps": self.risk_bps or 0.0,
            "plan_reward_bps": self.reward_bps or 0.0,
            "reward_risk_ratio": self.reward_risk_ratio or 0.0,
            "plan_valid_until": self.valid_until_iso,
            "exit_guidance": self.exit_guidance,
        }


def build_trade_plan(
    signal: Signal,
    candle: Candle,
    feature: FeatureRow,
    timeframe: Timeframe,
    round_trip_cost_bps: float,
) -> TradePlan:
    if round_trip_cost_bps < 0:
        raise ValueError("round_trip_cost_bps cannot be negative")
    valid_until = signal.prediction.generated_at + timedelta(
        minutes=signal.prediction.horizon_minutes
    )
    if not signal.is_actionable or signal.prediction.direction is Direction.NO_TRADE:
        return TradePlan(
            action="WAIT",
            entry_price=None,
            stop_loss_price=None,
            take_profit_price=None,
            risk_bps=None,
            reward_bps=None,
            reward_risk_ratio=None,
            valid_until_iso=valid_until.isoformat(),
            exit_guidance=(
                "Do not open a new position. Reassess an existing paper position on the next "
                "confirmed signal or risk-limit breach."
            ),
        )

    atr_bps = max(float(feature.values.get("atr_bps", 0.0)), 1.0)
    risk_bps = max(atr_bps * 1.5, round_trip_cost_bps * 1.5, 5.0)
    model_move_bps = abs(signal.prediction.expected_return_bps or 0.0)
    reward_bps = max(risk_bps * 1.5, model_move_bps)
    entry = candle.close
    direction = signal.prediction.direction
    if direction is Direction.LONG:
        stop = entry * (1 - risk_bps / 10_000)
        target = entry * (1 + reward_bps / 10_000)
        action = "ENTER_LONG"
    else:
        stop = entry * (1 + risk_bps / 10_000)
        target = entry * (1 - reward_bps / 10_000)
        action = "ENTER_SHORT"
    return TradePlan(
        action=action,
        entry_price=entry,
        stop_loss_price=stop,
        take_profit_price=target,
        risk_bps=risk_bps,
        reward_bps=reward_bps,
        reward_risk_ratio=reward_bps / risk_bps,
        valid_until_iso=valid_until.isoformat(),
        exit_guidance=(
            "Exit at the target or stop, or when the plan validity expires; do not widen the "
            "stop after entry."
        ),
    )
