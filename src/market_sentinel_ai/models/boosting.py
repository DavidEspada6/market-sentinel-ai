from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Sequence
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from typing import Any, ClassVar

from market_sentinel_ai.domain.prediction import Direction, Prediction
from market_sentinel_ai.ml.datasets import TrainingExample
from market_sentinel_ai.ports.features import FeatureRow


class OptionalDependencyMissingError(RuntimeError):
    pass


class ModelArtifactError(RuntimeError):
    pass


class _BoostingDirectionalModel:
    backend: ClassVar[str]
    artifact_filename: ClassVar[str]

    def __init__(
        self,
        horizon_minutes: int = 5,
        *,
        n_estimators: int = 100,
        max_depth: int = 3,
        learning_rate: float = 0.05,
        long_threshold: float = 0.55,
        short_threshold: float = 0.45,
        random_seed: int = 42,
    ) -> None:
        if horizon_minutes <= 0:
            raise ValueError("horizon_minutes must be positive")
        if n_estimators <= 0 or max_depth <= 0 or learning_rate <= 0:
            raise ValueError("boosting hyperparameters must be positive")
        if not 0 < short_threshold < long_threshold < 1:
            raise ValueError("thresholds must satisfy 0 < short < long < 1")
        self.horizon_minutes = horizon_minutes
        self.n_estimators = n_estimators
        self.max_depth = max_depth
        self.learning_rate = learning_rate
        self.long_threshold = long_threshold
        self.short_threshold = short_threshold
        self.random_seed = random_seed
        self.feature_names: tuple[str, ...] = ()
        self.mean_positive_return_bps = 0.0
        self.mean_negative_return_bps = 0.0
        self.trained_at: datetime | None = None
        self._model: Any | None = None
        self._loaded_native_booster = False

    @property
    def name(self) -> str:
        return f"{self.backend}-directional"

    def fit(self, examples: Sequence[TrainingExample]) -> None:
        if len(examples) < 2:
            raise ValueError("at least two training examples are required")
        labels = {example.label for example in examples}
        if labels != {0, 1}:
            raise ValueError("training data must contain both direction labels")
        self.feature_names = tuple(sorted(examples[0].features))
        if not self.feature_names:
            raise ValueError("training examples must contain features")
        matrix = [self._vector(example.features) for example in examples]
        targets = [example.label for example in examples]
        positive_returns = [
            example.realized_return_bps for example in examples if example.label == 1
        ]
        negative_returns = [
            example.realized_return_bps for example in examples if example.label == 0
        ]
        self.mean_positive_return_bps = sum(positive_returns) / len(positive_returns)
        self.mean_negative_return_bps = sum(negative_returns) / len(negative_returns)
        self._model = self._new_estimator()
        self._model.fit(matrix, targets)
        self._loaded_native_booster = False
        self.trained_at = datetime.now(tz=UTC)

    def predict(self, features: Sequence[FeatureRow]) -> Prediction:
        if self._model is None or not self.feature_names:
            raise ValueError("model must be fit or loaded before prediction")
        if not features:
            raise ValueError("features cannot be empty")
        latest = features[-1]
        probability_long = self._predict_probability(self._vector(latest.values))
        expected_market_return_bps = (
            probability_long * self.mean_positive_return_bps
            + (1 - probability_long) * self.mean_negative_return_bps
        )
        if probability_long >= self.long_threshold:
            direction = Direction.LONG
            probability = probability_long
            expected_strategy_return_bps = expected_market_return_bps
        elif probability_long <= self.short_threshold:
            direction = Direction.SHORT
            probability = 1 - probability_long
            expected_strategy_return_bps = -expected_market_return_bps
        else:
            direction = Direction.NO_TRADE
            probability = max(probability_long, 1 - probability_long)
            expected_strategy_return_bps = abs(expected_market_return_bps)
        return Prediction(
            symbol=latest.symbol,
            horizon_minutes=self.horizon_minutes,
            direction=direction,
            probability=probability,
            model_name=self.name,
            generated_at=datetime.now(tz=UTC),
            expected_return_bps=expected_strategy_return_bps,
            metadata={
                "probability_long": probability_long,
                "expected_market_return_bps": expected_market_return_bps,
                "feature_count": len(self.feature_names),
            },
        )

    def save(self, directory: str | Path) -> Path:
        if self._model is None or self.trained_at is None:
            raise ValueError("model must be fit before it can be saved")
        artifact_dir = Path(directory)
        artifact_dir.mkdir(parents=True, exist_ok=True)
        model_path = artifact_dir / self.artifact_filename
        self._save_native_model(model_path)
        manifest_path = artifact_dir / "manifest.json"
        manifest_path.write_text(
            json.dumps(self._manifest(model_path), indent=2, sort_keys=True),
            encoding="utf-8",
        )
        return manifest_path

    @classmethod
    def load(cls, directory: str | Path) -> _BoostingDirectionalModel:
        artifact_dir = Path(directory)
        manifest_path = artifact_dir / "manifest.json"
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ModelArtifactError("model manifest is missing or invalid") from exc
        if manifest.get("artifact_version") != 1 or manifest.get("backend") != cls.backend:
            raise ModelArtifactError("model artifact type or version does not match")
        instance = cls(**manifest["hyperparameters"])
        instance.feature_names = tuple(manifest["feature_names"])
        instance.mean_positive_return_bps = float(manifest["mean_positive_return_bps"])
        instance.mean_negative_return_bps = float(manifest["mean_negative_return_bps"])
        instance.trained_at = datetime.fromisoformat(manifest["trained_at"])
        model_path = artifact_dir / manifest["model_file"]
        if _sha256(model_path) != manifest["model_sha256"]:
            raise ModelArtifactError("native model checksum does not match the manifest")
        instance._load_native_model(model_path)
        return instance

    def _manifest(self, model_path: Path) -> dict[str, object]:
        package_name = "xgboost" if self.backend == "xgboost" else "lightgbm"
        return {
            "artifact_version": 1,
            "backend": self.backend,
            "model_name": self.name,
            "model_file": model_path.name,
            "model_sha256": _sha256(model_path),
            "library_version": version(package_name),
            "trained_at": self.trained_at.isoformat() if self.trained_at else None,
            "feature_names": list(self.feature_names),
            "mean_positive_return_bps": self.mean_positive_return_bps,
            "mean_negative_return_bps": self.mean_negative_return_bps,
            "hyperparameters": {
                "horizon_minutes": self.horizon_minutes,
                "n_estimators": self.n_estimators,
                "max_depth": self.max_depth,
                "learning_rate": self.learning_rate,
                "long_threshold": self.long_threshold,
                "short_threshold": self.short_threshold,
                "random_seed": self.random_seed,
            },
        }

    def _vector(self, values: dict[str, float]) -> list[float]:
        if set(values) != set(self.feature_names):
            missing = sorted(set(self.feature_names) - set(values))
            extra = sorted(set(values) - set(self.feature_names))
            raise ValueError(f"feature schema mismatch; missing={missing}, extra={extra}")
        vector = [float(values[name]) for name in self.feature_names]
        if not all(math.isfinite(value) for value in vector):
            raise ValueError("features must contain only finite numeric values")
        return vector

    def _predict_probability(self, vector: list[float]) -> float:
        if self.backend == "lightgbm" and self._loaded_native_booster:
            prediction = self._model.predict([vector])
            return float(prediction[0])
        probabilities = self._model.predict_proba([vector])
        return float(probabilities[0][1])

    def _new_estimator(self) -> Any:
        raise NotImplementedError

    def _save_native_model(self, path: Path) -> None:
        raise NotImplementedError

    def _load_native_model(self, path: Path) -> None:
        raise NotImplementedError


class XGBoostDirectionalModel(_BoostingDirectionalModel):
    backend = "xgboost"
    artifact_filename = "model.json"

    def _new_estimator(self) -> Any:
        try:
            from xgboost import XGBClassifier
        except ImportError as exc:
            raise OptionalDependencyMissingError(
                "Install market-sentinel-ai[ml] to use XGBoostDirectionalModel."
            ) from exc
        return XGBClassifier(
            n_estimators=self.n_estimators,
            max_depth=self.max_depth,
            learning_rate=self.learning_rate,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=self.random_seed,
            n_jobs=1,
            eval_metric="logloss",
        )

    def _save_native_model(self, path: Path) -> None:
        self._model.save_model(path)

    def _load_native_model(self, path: Path) -> None:
        self._model = self._new_estimator()
        self._model.load_model(path)
        self._loaded_native_booster = False


class LightGBMDirectionalModel(_BoostingDirectionalModel):
    backend = "lightgbm"
    artifact_filename = "model.txt"

    def _new_estimator(self) -> Any:
        try:
            from lightgbm import LGBMClassifier
        except ImportError as exc:
            raise OptionalDependencyMissingError(
                "Install market-sentinel-ai[ml] to use LightGBMDirectionalModel."
            ) from exc
        return LGBMClassifier(
            n_estimators=self.n_estimators,
            max_depth=self.max_depth,
            learning_rate=self.learning_rate,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=self.random_seed,
            n_jobs=1,
            verbosity=-1,
            deterministic=True,
            force_col_wise=True,
        )

    def _save_native_model(self, path: Path) -> None:
        self._model.booster_.save_model(path)

    def _load_native_model(self, path: Path) -> None:
        try:
            from lightgbm import Booster
        except ImportError as exc:
            raise OptionalDependencyMissingError(
                "Install market-sentinel-ai[ml] to load a LightGBM artifact."
            ) from exc
        self._model = Booster(model_file=str(path))
        self._loaded_native_booster = True


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
