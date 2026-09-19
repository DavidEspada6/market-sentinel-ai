from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class ClassificationMetrics:
    observations: int
    coverage: float
    accuracy: float
    precision: float
    recall: float
    f1: float


def binary_classification_metrics(
    actual: Sequence[int],
    predicted: Sequence[int | None],
) -> ClassificationMetrics:
    if len(actual) != len(predicted):
        raise ValueError("actual and predicted must have the same length")
    if not actual:
        return ClassificationMetrics(0, 0.0, 0.0, 0.0, 0.0, 0.0)

    covered = [
        (truth, guess)
        for truth, guess in zip(actual, predicted, strict=True)
        if guess is not None
    ]
    if not covered:
        return ClassificationMetrics(len(actual), 0.0, 0.0, 0.0, 0.0, 0.0)

    true_positive = sum(1 for truth, guess in covered if truth == 1 and guess == 1)
    true_negative = sum(1 for truth, guess in covered if truth == 0 and guess == 0)
    false_positive = sum(1 for truth, guess in covered if truth == 0 and guess == 1)
    false_negative = sum(1 for truth, guess in covered if truth == 1 and guess == 0)

    precision_denominator = true_positive + false_positive
    recall_denominator = true_positive + false_negative
    precision = true_positive / precision_denominator if precision_denominator else 0.0
    recall = true_positive / recall_denominator if recall_denominator else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0

    return ClassificationMetrics(
        observations=len(actual),
        coverage=len(covered) / len(actual),
        accuracy=(true_positive + true_negative) / len(covered),
        precision=precision,
        recall=recall,
        f1=f1,
    )

