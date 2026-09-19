from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from market_sentinel_ai.ports.features import FeatureRow


@dataclass(frozen=True)
class DriftReport:
    drifted: bool
    scores: dict[str, float]
    threshold: float


class FeatureDriftDetector:
    def __init__(self, threshold: float = 2.5) -> None:
        self.threshold = threshold

    def compare(
        self,
        reference: Sequence[FeatureRow],
        current: Sequence[FeatureRow],
    ) -> DriftReport:
        if not reference or not current:
            return DriftReport(drifted=False, scores={}, threshold=self.threshold)

        feature_names = sorted(set(reference[0].values) & set(current[0].values))
        scores: dict[str, float] = {}
        for name in feature_names:
            reference_values = [row.values[name] for row in reference]
            current_values = [row.values[name] for row in current]
            reference_mean = sum(reference_values) / len(reference_values)
            current_mean = sum(current_values) / len(current_values)
            reference_std = _std(reference_values) or 1.0
            scores[name] = abs(current_mean - reference_mean) / reference_std

        return DriftReport(
            drifted=any(score >= self.threshold for score in scores.values()),
            scores=scores,
            threshold=self.threshold,
        )


def _std(values: Sequence[float]) -> float:
    if len(values) < 2:
        return 0.0
    average = sum(values) / len(values)
    return math.sqrt(sum((value - average) ** 2 for value in values) / len(values))
