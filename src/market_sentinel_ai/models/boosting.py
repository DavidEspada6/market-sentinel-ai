from __future__ import annotations


class OptionalDependencyMissingError(RuntimeError):
    pass


class XGBoostDirectionalModel:
    def __init__(self) -> None:
        try:
            import xgboost  # noqa: F401
        except ImportError as exc:
            raise OptionalDependencyMissingError(
                "Install market-sentinel-ai[ml] to use XGBoostDirectionalModel."
            ) from exc


class LightGBMDirectionalModel:
    def __init__(self) -> None:
        try:
            import lightgbm  # noqa: F401
        except ImportError as exc:
            raise OptionalDependencyMissingError(
                "Install market-sentinel-ai[ml] to use LightGBMDirectionalModel."
            ) from exc

