"""Purged expanding-window cross-validation and out-of-sample predictions."""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd

from .features import BASE_FEATURES
from .models import build_model, candidate_params


def _rank_corr(actual: pd.Series, predicted: pd.Series) -> float:
    x = actual.rank().to_numpy(dtype=float)
    y = predicted.rank().to_numpy(dtype=float)
    if len(x) < 3 or np.std(x) == 0 or np.std(y) == 0:
        return float("nan")
    return float(np.corrcoef(x, y)[0, 1])


def average_rank_ic(frame: pd.DataFrame, *, prediction: str) -> float:
    scores = [
        _rank_corr(g["target"], g[prediction])
        for _, g in frame.groupby("date", sort=True)
    ]
    good = [s for s in scores if np.isfinite(s)]
    return float(np.mean(good)) if good else float("nan")


@dataclass(frozen=True)
class WalkForwardConfig:
    min_train: int = 60
    validation_days: int = 20
    test_days: int = 15
    seed: int = 42

    def __post_init__(self):
        if min(self.min_train, self.validation_days, self.test_days) < 1:
            raise ValueError("All temporal windows must be >=1")
        if self.min_train < 15:
            raise ValueError("min_train must be >=15 to reduce tiny-sample failures")


def walk_forward(
    panel: pd.DataFrame,
    *,
    model_kind: str = "ridge",
    cfg: WalkForwardConfig = WalkForwardConfig(),
    feature_cols: tuple[str, ...] = BASE_FEATURES,
) -> tuple[pd.DataFrame, list[dict]]:
    """Choose hyperparameters on past-only validation and predict future test windows.

    For a test beginning on session index T, observations at T-1 have label
    open(T)/open(T+1), unknown at the decision close(T). Therefore the final
    calibration pool ends on T-2 (inclusive).

    Validation begins on index V: training used to tune parameters ends at
    V-2. Both gaps are enforced in this implementation.
    """
    if "target" in feature_cols or not feature_cols:
        raise ValueError("Only causal features can be used")
    if not set(feature_cols).issubset(panel.columns):
        raise ValueError("Feature columns missing")
    if panel[list(feature_cols)].isna().any().any():
        raise ValueError("Missing feature values: fix via past-only transforms before training")
    dates = sorted(pd.to_datetime(panel["date"].unique()))
    first_test = cfg.min_train + cfg.validation_days + 2
    if len(dates) <= first_test:
        raise ValueError(
            f"Need > {first_test} usable decision dates, found {len(dates)}. "
            "Increase data or reduce train/validation windows."
        )
    panels = []
    folds = []
    for test_start in range(first_test, len(dates), cfg.test_days):
        test_dates = dates[test_start: test_start + cfg.test_days]
        val_start = test_start - 1 - cfg.validation_days
        # The latest training label available on close of val_start is val_start-2.
        train_dates = dates[:val_start-1]
        val_dates = dates[val_start:test_start-1]
        deploy_dates = dates[:test_start-1]
        train = panel[panel["date"].isin(train_dates)]
        val = panel[panel["date"].isin(val_dates)]
        deploy = panel[panel["date"].isin(deploy_dates)]
        test = panel[panel["date"].isin(test_dates)].copy()
        assert len(train_dates) >= cfg.min_train
        assert train["date"].max() < dates[val_start-1]
        assert val["date"].max() < dates[test_start-1]
        assert deploy["date"].max() == dates[test_start-2]
        if test.empty:
            continue

        if model_kind == "factor":
            best_param: float | int = 0
            best_score = average_rank_ic(
                val.assign(prediction=val["mom_5"]), prediction="prediction"
            )
            test["prediction"] = test["mom_5"].astype(float)
        else:
            best_param, best_score = None, -np.inf
            for param in candidate_params(model_kind):
                model = build_model(model_kind, param, seed=cfg.seed)
                model.fit(train[list(feature_cols)], train["target"])
                scores = val.copy()
                scores["prediction"] = model.predict(val[list(feature_cols)])
                score = average_rank_ic(scores, prediction="prediction")
                # In zero-signal validation keep deterministic first candidate.
                score = float(score) if np.isfinite(score) else -np.inf
                if best_param is None or score > best_score:
                    best_param, best_score = param, score
            model = build_model(model_kind, best_param, seed=cfg.seed)
            model.fit(deploy[list(feature_cols)], deploy["target"])
            test["prediction"] = model.predict(test[list(feature_cols)])

        columns = ["date", "asset", "execution_date", "exit_date", "target", "prediction"]
        panels.append(test[columns].copy())
        folds.append({
            "fold": len(folds) + 1,
            "train_start": str(pd.Timestamp(train_dates[0]).date()),
            "train_end": str(pd.Timestamp(train_dates[-1]).date()),
            "validation_start": str(pd.Timestamp(val_dates[0]).date()),
            "validation_end": str(pd.Timestamp(val_dates[-1]).date()),
            "final_fit_end": str(pd.Timestamp(deploy_dates[-1]).date()),
            "test_start": str(pd.Timestamp(test_dates[0]).date()),
            "test_end": str(pd.Timestamp(test_dates[-1]).date()),
            "train_rows": len(train),
            "validation_rows": len(val),
            "test_rows": len(test),
            "param": best_param,
            "validation_rank_ic": None if not np.isfinite(best_score) else float(best_score),
        })
    if not panels:
        raise ValueError("No test windows were created")
    predictions = pd.concat(panels, ignore_index=True)
    if predictions.duplicated(["date", "asset"]).any():
        raise AssertionError("Overlap between test folds")
    return predictions.sort_values(["date", "asset"]).reset_index(drop=True), folds
