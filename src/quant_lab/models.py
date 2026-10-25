"""Simple CPU baselines. LightGBM is an optional extra, not a required GPU path."""

from __future__ import annotations

from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


def candidate_params(kind: str) -> tuple[float | int, ...]:
    if kind == "ridge":
        return (0.1, 10.0)
    if kind == "lightgbm":
        return (7, 15)
    if kind == "factor":
        return (0,)
    raise ValueError(f"Unknown model {kind!r}: use ridge, lightgbm or factor")


def build_model(kind: str, param: float | int, *, seed: int = 42):
    """Construct a new estimator for each train split, preventing fitted-state reuse."""
    if kind == "ridge":
        return make_pipeline(StandardScaler(), Ridge(alpha=float(param)))
    if kind == "lightgbm":
        try:
            from lightgbm import LGBMRegressor
        except ImportError as exc:
            raise RuntimeError("LightGBM needs: python -m pip install -e '.[ml]'") from exc
        return LGBMRegressor(
            n_estimators=120, learning_rate=0.035,
            max_depth=5, num_leaves=int(param), min_child_samples=10,
            random_state=seed, n_jobs=2, verbosity=-1,
            deterministic=True, force_col_wise=True,
        )
    raise ValueError(f"No fitted model for {kind!r}")
