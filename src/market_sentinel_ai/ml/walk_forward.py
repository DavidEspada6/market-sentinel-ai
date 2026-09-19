from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from market_sentinel_ai.backtesting import build_backtest_report
from market_sentinel_ai.domain.prediction import Direction
from market_sentinel_ai.ml.datasets import TrainingExample
from market_sentinel_ai.ml.metrics import ClassificationMetrics, binary_classification_metrics
from market_sentinel_ai.ports.backtesting import BacktestReport
from market_sentinel_ai.ports.features import FeatureRow


@dataclass(frozen=True)
class WalkForwardFold:
    train_start: int
    train_end: int
    test_start: int
    test_end: int


@dataclass(frozen=True)
class WalkForwardFoldResult:
    fold: WalkForwardFold
    classification: ClassificationMetrics
    backtest: BacktestReport


@dataclass(frozen=True)
class WalkForwardReport:
    fold_results: tuple[WalkForwardFoldResult, ...]

    @property
    def folds(self) -> tuple[ClassificationMetrics, ...]:
        """Backward-compatible classification view of each out-of-sample fold."""
        return tuple(result.classification for result in self.fold_results)

    @property
    def backtests(self) -> tuple[BacktestReport, ...]:
        return tuple(result.backtest for result in self.fold_results)

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

    @property
    def average_net_pnl_bps(self) -> float:
        return _average(report.net_pnl_bps for report in self.backtests)

    @property
    def average_sharpe(self) -> float | None:
        values = [report.sharpe for report in self.backtests if report.sharpe is not None]
        return _average(values) if values else None


@dataclass(frozen=True)
class WalkForwardSplit:
    train_size: int
    test_size: int
    step_size: int | None = None
    purge_size: int = 0
    expanding: bool = True

    def split(self, examples: Sequence[TrainingExample]) -> list[WalkForwardFold]:
        if self.train_size <= 0 or self.test_size <= 0:
            raise ValueError("train_size and test_size must be positive")
        step = self.step_size or self.test_size
        if step <= 0:
            raise ValueError("step_size must be positive")
        if self.purge_size < 0:
            raise ValueError("purge_size cannot be negative")

        folds: list[WalkForwardFold] = []
        fold_number = 0
        while True:
            train_start = 0 if self.expanding else fold_number * step
            train_end = train_start + self.train_size
            if self.expanding:
                train_end += fold_number * step
            test_start = train_end + self.purge_size
            test_end = test_start + self.test_size
            if test_end > len(examples):
                break
            folds.append(WalkForwardFold(train_start, train_end, test_start, test_end))
            fold_number += 1
        return folds


class WalkForwardEvaluator:
    def __init__(
        self,
        model_factory: Callable[[], object],
        splitter: WalkForwardSplit,
        *,
        fee_bps: float = 0.0,
        slippage_bps: float = 0.0,
        spread_bps: float = 0.0,
        initial_equity: float = 100_000.0,
        position_fraction: float = 1.0,
    ) -> None:
        self.model_factory = model_factory
        self.splitter = splitter
        self.fee_bps = fee_bps
        self.slippage_bps = slippage_bps
        self.spread_bps = spread_bps
        self.initial_equity = initial_equity
        self.position_fraction = position_fraction

    def evaluate(self, examples: Sequence[TrainingExample]) -> WalkForwardReport:
        results: list[WalkForwardFoldResult] = []
        for fold in self.splitter.split(examples):
            model = self.model_factory()
            model.fit(examples[fold.train_start : fold.train_end])
            actual: list[int] = []
            predicted: list[int | None] = []
            gross_returns_bps: list[float] = []
            net_returns_bps: list[float] = []
            round_trip_cost_bps = self.fee_bps * 2 + self.slippage_bps * 2 + self.spread_bps
            for example in examples[fold.test_start : fold.test_end]:
                prediction = model.predict(
                    [
                        FeatureRow(
                            symbol=example.symbol,
                            timestamp_iso=example.timestamp_iso,
                            values=example.features,
                        )
                    ]
                )
                label = _label_from_direction(prediction.direction)
                actual.append(example.label)
                predicted.append(label)
                if prediction.direction is Direction.LONG:
                    gross_return = example.realized_return_bps
                elif prediction.direction is Direction.SHORT:
                    gross_return = -example.realized_return_bps
                else:
                    continue
                gross_returns_bps.append(gross_return)
                net_returns_bps.append(gross_return - round_trip_cost_bps)
            results.append(
                WalkForwardFoldResult(
                    fold=fold,
                    classification=binary_classification_metrics(actual, predicted),
                    backtest=build_backtest_report(
                        net_returns_bps,
                        gross_returns_bps=gross_returns_bps,
                        initial_equity=self.initial_equity,
                        position_fraction=self.position_fraction,
                    ),
                )
            )
        return WalkForwardReport(tuple(results))


def _label_from_direction(direction: Direction) -> int | None:
    if direction is Direction.LONG:
        return 1
    if direction is Direction.SHORT:
        return 0
    return None


def _average(values: Sequence[float] | object) -> float:
    items = list(values)
    return sum(items) / len(items) if items else 0.0
