from __future__ import annotations

from dataclasses import dataclass

from market_sentinel_ai.domain.prediction import Direction, Prediction, Signal


@dataclass(frozen=True)
class SignalEngine:
    min_probability: float
    min_expected_return_bps: float

    def from_prediction(self, prediction: Prediction) -> Signal:
        expected = prediction.expected_return_bps
        risk_notes = (
            "Alert-only mode; no real order execution.",
            "Position sizing must be checked against risk policy.",
        )

        if prediction.direction is Direction.NO_TRADE:
            return Signal(
                prediction=prediction,
                confidence=prediction.probability,
                rationale="Model does not see enough edge for a directional alert.",
                risk_notes=risk_notes,
            )

        if prediction.probability < self.min_probability:
            return Signal(
                prediction=_as_no_trade(prediction),
                confidence=prediction.probability,
                rationale="Probability is below the alert threshold.",
                risk_notes=risk_notes,
            )

        if expected is not None and abs(expected) < self.min_expected_return_bps:
            return Signal(
                prediction=_as_no_trade(prediction),
                confidence=prediction.probability,
                rationale="Expected return is below the alert threshold after costs.",
                risk_notes=risk_notes,
            )

        return Signal(
            prediction=prediction,
            confidence=prediction.probability,
            rationale="Directional setup passed probability and expected-return gates.",
            risk_notes=risk_notes,
        )


def _as_no_trade(prediction: Prediction) -> Prediction:
    return Prediction(
        symbol=prediction.symbol,
        horizon_minutes=prediction.horizon_minutes,
        direction=Direction.NO_TRADE,
        probability=prediction.probability,
        model_name=prediction.model_name,
        generated_at=prediction.generated_at,
        expected_return_bps=prediction.expected_return_bps,
        metadata=prediction.metadata,
    )

