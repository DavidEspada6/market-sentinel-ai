from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from market_sentinel_ai.domain.prediction import Direction
from market_sentinel_ai.ml.datasets import TrainingExample
from market_sentinel_ai.ml.metrics import ClassificationMetrics, binary_classification_metrics
from market_sentinel_ai.ports.features import FeatureRow


@dataclass(frozen=True)
class WalkForwardFold:
    train_start: int
    train_end: int
    test_start: int
    test_end: int


@dataclass(frozen=True)
class WalkForwardReport:
    folds: tuple[ClassificationMetrics, ...]

    @property
    def average_accuracy(self) -> float:
        return _average(metric.accuracy for metric in self.folds)

    @property
    def average_precision(self) -> float:
        return _average(metric.precision for metric in self.folds)

    @property
    def average_recall(self) -> float:
        return _average(metric.recall for metric in self.folds)

    @property
    def average_coverage(self) -> float:
        return _average(metric.coverage for metric in self.folds)


@dataclass(frozen=True)
class WalkForwardSplit:
    train_size: int
    test_size: int
    step_size: int | None = None

    def split(self, examples: Sequence[TrainingExample]) -> list[WalkForwardFold]:
        if self.train_size <= 0 or self.test_size <= 0:
            raise ValueError("train_size and test_size must be positive")
        step = self.step_size or self.test_size
        if step <= 0:
            raise ValueError("step_size must be positive")

        folds: list[WalkForwardFold] = []
        train_start = 0
        while True:
            train_end = train_start + self.train_size
            test_start = train_end
            test_end = test_start + self.test_size
            if test_end > len(examples):
                break
            folds.append(WalkForwardFold(train_start, train_end, test_start, test_end))
            train_start += step
        return folds


class WalkForwardEvaluator:
    def __init__(
        self,
        model_factory: Callable[[], object],
        splitter: WalkForwardSplit,
    ) -> None:
        self.model_factory = model_factory
        self.splitter = splitter

    def evaluate(self, examples: Sequence[TrainingExample]) -> WalkForwardReport:
        fold_metrics: list[ClassificationMetrics] = []
        for fold in self.splitter.split(examples):
            model = self.model_factory()
            fit = model.fit
            predict = model.predict
            fit(examples[fold.train_start : fold.train_end])

            actual: list[int] = []
            predicted: list[int | None] = []
            for example in examples[fold.test_start : fold.test_end]:
                prediction = predict(
                    [
                        FeatureRow(
                            symbol=example.symbol,
                            timestamp_iso=example.timestamp_iso,
                            values=example.features,
                        )
                    ]
                )
                actual.append(example.label)
                predicted.append(_label_from_direction(prediction.direction))
            fold_metrics.append(binary_classification_metrics(actual, predicted))

        return WalkForwardReport(tuple(fold_metrics))


def _label_from_direction(direction: Direction) -> int | None:
    if direction is Direction.LONG:
        return 1
    if direction is Direction.SHORT:
        return 0
    return None


def _average(values: object) -> float:
    items = list(values)
    return sum(items) / len(items) if items else 0.0

