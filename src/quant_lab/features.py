"""Causal end-of-day features with an explicitly delayed execution label."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .data import validate_market

BASE_FEATURES = (
    "mom_5", "mom_20", "reversal_1",
    "volatility_10", "volume_ratio_10", "ma_gap_10",
)


def make_factor_panel(bars: pd.DataFrame, *, extra_features: tuple[str, ...] = ()) -> pd.DataFrame:
    """Create t-close features and t+1-open to t+2-open return labels.

    Decision at close(t), entry at open(t+1), exit at open(t+2).
    Every factor below uses dates <= t. The label is NEVER an input feature.
    """
    frame = validate_market(bars)
    group = frame.groupby("asset", sort=False)
    close = group["close"]
    volume = group["volume"]
    opens = group["open"]
    ret_1 = close.pct_change(fill_method=None)
    frame["mom_5"] = close.pct_change(periods=5, fill_method=None)
    frame["mom_20"] = close.pct_change(periods=20, fill_method=None)
    frame["reversal_1"] = -ret_1
    frame["volatility_10"] = ret_1.groupby(frame["asset"]).transform(
        lambda s: s.rolling(10, min_periods=10).std()
    )
    frame["volume_ratio_10"] = volume.transform(
        lambda s: s / s.rolling(10, min_periods=10).mean() - 1
    )
    frame["ma_gap_10"] = close.transform(
        lambda s: s / s.rolling(10, min_periods=10).mean() - 1
    )
    frame["execution_date"] = group["date"].shift(-1)
    frame["exit_date"] = group["date"].shift(-2)
    frame["target"] = opens.shift(-2) / opens.shift(-1) - 1

    if any(not name.startswith("alpha_") for name in extra_features):
        raise ValueError("Extra factor columns must start with 'alpha_'")
    if len(set(extra_features)) != len(extra_features):
        raise ValueError("Duplicate extra factor names")
    names = list(BASE_FEATURES) + list(extra_features)
    if not set(extra_features).issubset(frame.columns):
        raise ValueError("Extra factors missing from market panel")
    if "target" in names or "execution_date" in names:
        raise ValueError("Target or execution date cannot be input features")

    frame = frame.replace([np.inf, -np.inf], np.nan)
    frame = frame.dropna(subset=names + ["target", "execution_date", "exit_date"])
    if frame.empty:
        raise ValueError("No rows remain after warmup and delayed label construction")
    return frame.sort_values(["date", "asset"]).reset_index(drop=True)
