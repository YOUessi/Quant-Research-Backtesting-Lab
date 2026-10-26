"""EXP-002 price-adjustment inspection: explicit non-certification of as-of factors.

Qlib historical OHLCV is stored with adjusted prices and an adjusted/raw factor.
Dividing by factor reconstructs an *estimate* of the nominal traded price, but
one current snapshot cannot tell what adjustment factor was actually published
on a historical decision date. Real corporate action cash/share entitlements
need separate historical records.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def adjustment_audit(panel: pd.DataFrame, *, start: str, end: str) -> dict:
    fields = {"asset", "date", "adj_open", "adj_close", "factor",
              "raw_open_estimate", "raw_close_estimate", "factor_step_ratio",
              "index_member_asof"}
    if not fields.issubset(panel.columns):
        raise ValueError("Missing adjusted-price audit fields")
    frame = panel[panel["date"].between(pd.Timestamp(start), pd.Timestamp(end))]
    members = frame[frame["index_member_asof"]].copy()
    factors = members["factor"].to_numpy(dtype=float)
    valid = np.isfinite(factors) & (factors > 0)
    open_val = members["adj_open"].to_numpy(dtype=float)
    close_val = members["adj_close"].to_numpy(dtype=float)
    raw_open = members["raw_open_estimate"].to_numpy(dtype=float)
    raw_close = members["raw_close_estimate"].to_numpy(dtype=float)
    both = valid & np.isfinite(open_val) & np.isfinite(close_val)
    roundtrip_open = np.isclose(raw_open[both] * factors[both], open_val[both],
                                rtol=2e-7, atol=1e-8)
    roundtrip_close = np.isclose(raw_close[both] * factors[both], close_val[both],
                                 rtol=2e-7, atol=1e-8)
    jumps = members["factor_step_ratio"].sub(1).abs()
    positive = jumps[np.isfinite(jumps)]
    dates_with_jumps = members.loc[jumps.gt(.01), "date"]
    audit = {
        "rows_index_members": len(members),
        "positive_finite_factor_rows": int(valid.sum()),
        "factor_missing_or_nonpositive_rows": int((~valid).sum()),
        "source_adjusted_open_and_close_positive_rows": int(both.sum()),
        "factor_float32_roundtrip_rtol": 2e-7,
        "factor_float32_roundtrip_atol": 1e-8,
        "raw_price_roundtrip_errors": int(
            (~roundtrip_open).sum() + (~roundtrip_close).sum()
        ),
        "factor_ratio_abs_change_gt_1pct": int(jumps.gt(.01).sum()),
        "factor_ratio_abs_change_gt_5pct": int(jumps.gt(.05).sum()),
        "n_distinct_dates_gt_1pct": int(dates_with_jumps.nunique()),
        "median_abs_daily_factor_ratio_change": (
            float(positive.median()) if len(positive) else None
        ),
        "max_abs_daily_factor_ratio_change": (
            float(positive.max()) if len(positive) else None
        ),
        "q_lib_adjusted_price_convention":
            "adjusted_price = factor * nominal_price (nominal approx adjusted/factor)",
        "historical_release_time_factor_snapshots_available": False,
        "time_point_consistent_corporate_actions_verified": False,
        "corporate_action_split_dividend_cashflow_reconciled": False,
        "official_exchange_limit_up_down_fields_available": False,
        "status": "AUDITED_CURRENT_SNAPSHOT_ONLY_PIT_UNVERIFIABLE",
        "decision": (
            "PASS float32-tolerant adjusted/nominal arithmetic only if roundtrip_errors=0; "
            "BLOCK any claim of historically released adjustment factors, "
            "official price-limit fills or actual split/dividend entitlements."
        ),
    }
    if audit["raw_price_roundtrip_errors"]:
        raise ValueError("Qlib factor-adjusted/raw reconstruction inconsistent")
    return audit


def detect_factor_revision(
    old_snapshot: pd.DataFrame, new_snapshot: pd.DataFrame,
    *, threshold: float = 1e-6,
) -> dict:
    """Optional cross-snapshot same-symbol/date factor revisions.

    A pair of independently archived vendor releases is needed. Comparing a
    snapshot with itself is NOT a point-in-time adjustment-factor audit.
    """
    required = {"date", "asset", "factor"}
    for frame in (old_snapshot, new_snapshot):
        if not required.issubset(frame.columns):
            raise ValueError("Both historical snapshots need date,asset,factor")
        if frame.duplicated(["date", "asset"]).any():
            raise ValueError("Duplicate factor key")
    a = old_snapshot[["date", "asset", "factor"]]
    b = new_snapshot[["date", "asset", "factor"]]
    joined = a.merge(b, on=["date", "asset"], how="inner",
                     suffixes=("_older_release", "_newer_release"),
                     validate="one_to_one")
    if joined.empty:
        raise ValueError("No matching symbols/dates for independent release comparison")
    shift = (joined.factor_newer_release / joined.factor_older_release - 1).abs()
    valid = np.isfinite(shift)
    if not valid.all():
        raise ValueError("Factor comparison includes zero/nonfinite values")
    return {
        "overlap": int(len(joined)),
        "abs_relative_revision_gt_threshold": int((shift > threshold).sum()),
        "threshold": threshold,
        "max_revision": float(shift.max()),
        "caveat": (
            "Even two archive snapshots only identify between-release revisions; "
            "they do not prove each historical day carried exactly these values."
        ),
    }
