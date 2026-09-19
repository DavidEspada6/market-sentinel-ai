from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from market_sentinel_ai.domain.market import Candle
from market_sentinel_ai.domain.prediction import Direction, Prediction
from market_sentinel_ai.ml.datasets import TrainingExample
from market_sentinel_ai.ports.features import FeatureRow


class LogisticDirectionalModel:
    def __init__(
        self,
        horizon_minutes: int,
        learning_rate: float = 0.05,
        epochs: int = 200,
        l2: float = 0.001,
        long_threshold: float = 0.55,
        short_threshold: float = 0.45,
    ) -> None:
        self.horizon_minutes = horizon_minutes
        self.learning_rate = learning_rate
        self.epochs = epochs
        self.l2 = l2
        self.long_threshold = long_threshold
        self.short_threshold = short_threshold
        self.feature_names: tuple[str, ...] = ()
        self.means: dict[str, float] = {}
        self.scales: dict[str, float] = {}
        self.weights: dict[str, float] = {}
        self.bias = 0.0

    @property
    def name(self) -> str:
        return "logistic-directional"

    def fit(self, examples: Sequence[TrainingExample]) -> None:
        if not examples:
            raise ValueError("examples cannot be empty")

        self.feature_names = tuple(sorted(examples[0].features))
        self.means = {
            name: sum(example.features[name] for example in examples) / len(examples)
            for name in self.feature_names
        }
        self.scales = {
            name: _standard_deviation([example.features[name] for example in examples]) or 1.0
            for name in self.feature_names
        }
        self.weights = {name: 0.0 for name in self.feature_names}
        self.bias = 0.0

        for _ in range(self.epochs):
            gradient = {name: 0.0 for name in self.feature_names}
            bias_gradient = 0.0
            for example in examples:
                values = self._normalize(example.features)
                probability = _sigmoid(
                    self.bias
                    + sum(self.weights[name] * values[name] for name in self.feature_names)
                )
                error = probability - example.label
                bias_gradient += error
                for name in self.feature_names:
                    gradient[name] += error * values[name] + self.l2 * self.weights[name]

            scale = 1 / len(examples)
            self.bias -= self.learning_rate * bias_gradient * scale
            for name in self.feature_names:
                self.weights[name] -= self.learning_rate * gradient[name] * scale

    def predict(self, features: Sequence[FeatureRow]) -> Prediction:
        if not self.feature_names:
            raise ValueError("model must be fit before prediction")
        if not features:
            raise ValueError("features cannot be empty")

        latest = features[-1]
        values = self._normalize(latest.values)
        probability_long = _sigmoid(
            self.bias + sum(self.weights[name] * values[name] for name in self.feature_names)
        )
        if probability_long >= self.long_threshold:
            direction = Direction.LONG
            probability = probability_long
        elif probability_long <= self.short_threshold:
            direction = Direction.SHORT
            probability = 1 - probability_long
        else:
            direction = Direction.NO_TRADE
            probability = max(probability_long, 1 - probability_long)

        return Prediction(
            symbol=latest.symbol,
            horizon_minutes=self.horizon_minutes,
            direction=direction,
            probability=probability,
            model_name=self.name,
            generated_at=datetime.now(tz=UTC),
            metadata={"probability_long": probability_long},
        )

    def _normalize(self, values: dict[str, float]) -> dict[str, float]:
        return {
            name: (values[name] - self.means[name]) / self.scales[name]
            for name in self.feature_names
        }


def _sigmoid(value: float) -> float:
    if value < -60:
        return 0.0
    if value > 60:
        return 1.0
    return 1 / (1 + math.exp(-value))


def _standard_deviation(values: Sequence[float]) -> float:
    if len(values) < 2:
        return 0.0
    average = sum(values) / len(values)
    variance = sum((value - average) ** 2 for value in values) / len(values)
    return math.sqrt(variance)


@dataclass(frozen=True)
class _AdaptiveExample:
    features: tuple[float, ...]
    label: int
    realized_return_bps: float


class AdaptiveDirectionalModel:
    """Cost-aware local classifier for the live signal loop.

    The model is deliberately small and retrainable. Each row only contains features
    available at that candle; its label is created from a later close. Training examples
    therefore cannot use the future close as an input. The service adds a purge gap when
    calculating the walk-forward report because the forward label can overlap the next fold.
    """

    def __init__(
        self,
        horizon_minutes: int,
        horizon_candles: int = 3,
        min_training_examples: int = 120,
        min_direction_probability: float = 0.52,
    ) -> None:
        if horizon_minutes <= 0 or horizon_candles <= 0:
            raise ValueError("model horizons must be positive")
        if min_training_examples < 30:
            raise ValueError("min_training_examples must be at least 30")
        self.horizon_minutes = horizon_minutes
        self.horizon_candles = horizon_candles
        self.min_training_examples = min_training_examples
        self.min_direction_probability = min_direction_probability
        self._classifier: object | None = None
        self._feature_names: tuple[str, ...] = ()
        self._return_means: dict[int, float] = {}
        self._status: dict[str, str | float | int | bool] = {
            "status": "not_trained",
            "model": self.name,
        }

    @property
    def name(self) -> str:
        return "adaptive-logistic"

    @property
    def status(self) -> dict[str, str | float | int | bool]:
        return dict(self._status)

    def fit(
        self,
        candles: Sequence[Candle],
        features: Sequence[FeatureRow],
        round_trip_cost_bps: float,
    ) -> None:
        if len(candles) != len(features):
            raise ValueError("candles and features must have the same length")
        examples, feature_names, threshold = _build_adaptive_examples(
            candles,
            features,
            self.horizon_candles,
            round_trip_cost_bps,
        )
        if len(examples) < self.min_training_examples:
            raise ValueError(
                f"at least {self.min_training_examples} labelled candles are required; "
                f"received {len(examples)}"
            )

        self._feature_names = feature_names
        self._classifier = _fit_sklearn_classifier(
            [example.features for example in examples],
            [example.label for example in examples],
        )
        self._return_means = {
            label: _mean(
                example.realized_return_bps
                for example in examples
                if example.label == label
            )
            for label in (-1, 0, 1)
        }
        oos = _walk_forward_summary(
            examples,
            horizon_candles=self.horizon_candles,
            round_trip_cost_bps=round_trip_cost_bps,
        )
        self._status = {
            "status": "trained",
            "model": self.name,
            "training_samples": len(examples),
            "classes": len({example.label for example in examples}),
            "label_threshold_bps": threshold,
            "horizon_candles": self.horizon_candles,
            "oos_folds": oos["oos_folds"],
            "oos_directional_accuracy": oos["oos_directional_accuracy"],
            "oos_precision": oos["oos_precision"],
            "oos_recall": oos["oos_recall"],
            "oos_coverage": oos["oos_coverage"],
            "oos_net_pnl_bps": oos["oos_net_pnl_bps"],
            "real_orders_enabled": False,
        }

    def predict(self, features: Sequence[FeatureRow]) -> Prediction:
        if self._classifier is None or not self._feature_names:
            raise ValueError("model must be fit before prediction")
        if not features:
            raise ValueError("features cannot be empty")

        latest = features[-1]
        values = [latest.values[name] for name in self._feature_names]
        probabilities = _classifier_probabilities(self._classifier, values)
        probability_long = probabilities.get(1, 0.0)
        probability_short = probabilities.get(-1, 0.0)
        probability_flat = probabilities.get(0, 0.0)
        strongest_direction, strongest_probability = max(
            ((Direction.LONG, probability_long), (Direction.SHORT, probability_short)),
            key=lambda item: item[1],
        )
        expected_return_bps = sum(
            probabilities.get(label, 0.0) * self._return_means.get(label, 0.0)
            for label in (-1, 0, 1)
        )
        if (
            probability_flat >= strongest_probability
            or strongest_probability < self.min_direction_probability
            or abs(expected_return_bps) < float(self._status.get("label_threshold_bps", 0.0))
        ):
            direction = Direction.NO_TRADE
            probability = probability_flat
        else:
            direction = strongest_direction
            probability = strongest_probability

        return Prediction(
            symbol=latest.symbol,
            horizon_minutes=self.horizon_minutes,
            direction=direction,
            probability=max(0.0, min(1.0, probability)),
            model_name=self.name,
            generated_at=datetime.now(tz=UTC),
            expected_return_bps=expected_return_bps,
            metadata={
                "probability_long": probability_long,
                "probability_short": probability_short,
                "probability_no_trade": probability_flat,
                **self._status,
            },
        )


def _build_adaptive_examples(
    candles: Sequence[Candle],
    features: Sequence[FeatureRow],
    horizon_candles: int,
    round_trip_cost_bps: float,
) -> tuple[list[_AdaptiveExample], tuple[str, ...], float]:
    if round_trip_cost_bps < 0:
        raise ValueError("round_trip_cost_bps cannot be negative")
    if len(candles) <= horizon_candles:
        return [], (), max(2.0, round_trip_cost_bps)
    feature_names = tuple(sorted(features[0].values))
    threshold = max(2.0, round_trip_cost_bps)
    examples: list[_AdaptiveExample] = []
    for index in range(len(candles) - horizon_candles):
        entry = candles[index].close
        exit_price = candles[index + horizon_candles].close
        realized_return_bps = ((exit_price - entry) / entry) * 10_000
        label = (
            1
            if realized_return_bps >= threshold
            else -1
            if realized_return_bps <= -threshold
            else 0
        )
        examples.append(
            _AdaptiveExample(
                features=tuple(features[index].values[name] for name in feature_names),
                label=label,
                realized_return_bps=realized_return_bps,
            )
        )
    return examples, feature_names, threshold


def _fit_sklearn_classifier(features: list[tuple[float, ...]], labels: list[int]) -> object:
    try:
        from sklearn.linear_model import LogisticRegression
        from sklearn.pipeline import make_pipeline
        from sklearn.preprocessing import StandardScaler
    except ImportError as exc:
        raise RuntimeError(
            "the supervised model requires the optional 'ml' dependencies; "
            "install the application with [ml]"
        ) from exc
    if len(set(labels)) < 2:
        raise ValueError("supervised training needs at least two directional classes")
    return make_pipeline(
        StandardScaler(),
        LogisticRegression(
            class_weight="balanced",
            max_iter=500,
            random_state=42,
            solver="lbfgs",
        ),
    ).fit(features, labels)


def _classifier_probabilities(classifier: object, values: list[float]) -> dict[int, float]:
    probabilities = classifier.predict_proba([values])
    classes = classifier.classes_
    return {
        int(label): float(probability)
        for label, probability in zip(classes, probabilities[0], strict=True)
    }


def _walk_forward_summary(
    examples: Sequence[_AdaptiveExample],
    *,
    horizon_candles: int,
    round_trip_cost_bps: float,
) -> dict[str, float | int]:
    train_size = max(60, len(examples) // 2)
    test_size = max(20, len(examples) // 6)
    train_end = train_size
    correct = 0
    actionable = 0
    directional_observations = 0
    observations = 0
    net_pnl_bps = 0.0
    folds = 0
    while train_end + horizon_candles + test_size <= len(examples):
        test_start = train_end + horizon_candles
        test_end = test_start + test_size
        training = examples[:train_end]
        classifier = _fit_sklearn_classifier(
            [example.features for example in training],
            [example.label for example in training],
        )
        for example in examples[test_start:test_end]:
            prediction = _classifier_probabilities(classifier, list(example.features))
            predicted = max(prediction, key=prediction.get)
            observations += 1
            directional_observations += int(example.label != 0)
            if predicted != 0:
                actionable += 1
                correct += int(predicted == example.label)
                net_pnl_bps += (
                    example.realized_return_bps
                    if predicted == 1
                    else -example.realized_return_bps
                ) - round_trip_cost_bps
        folds += 1
        train_end = test_end
    return {
        "oos_folds": folds,
        "oos_directional_accuracy": correct / actionable if actionable else 0.0,
        "oos_precision": correct / actionable if actionable else 0.0,
        "oos_recall": correct / directional_observations if directional_observations else 0.0,
        "oos_coverage": actionable / observations if observations else 0.0,
        "oos_net_pnl_bps": net_pnl_bps,
    }


def _mean(values: object) -> float:
    items = list(values)
    return sum(items) / len(items) if items else 0.0

