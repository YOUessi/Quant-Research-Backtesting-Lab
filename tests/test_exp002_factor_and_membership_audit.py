"""Precision-aware factor audits and point-in-time stock-membership invariants."""

import numpy as np
import pandas as pd
import pytest

from quant_lab.pit_adjustment import adjustment_audit, detect_factor_revision
from quant_lab.pit_universe import asset_membership_mask


def test_float32_factor_roundtrip_is_not_falsely_declared_corrupt():
    dt = pd.bdate_range("2021-01-04", periods=8)
    f = np.asarray([0.5, 0.50, 0.51, 0.51, 0.51, 0.57, 0.57, 0.57], dtype=np.float32)
    adj_open = np.asarray([9.20, 9.25, 9.26, 9.40, 9.55, 9.6, 9.7, 9.9], dtype=np.float32)
    adj_close = adj_open * np.float32(1.001)
    panel = pd.DataFrame({
        "asset": "SH600000", "date": dt, "factor": f,
        "adj_open": adj_open, "adj_close": adj_close,
        "raw_open_estimate": adj_open / f,
        "raw_close_estimate": adj_close / f,
        "factor_step_ratio": pd.Series(f).pct_change(fill_method=None) + 1,
        "index_member_asof": True,
    })
    x = adjustment_audit(panel, start="2021-01-04", end="2021-01-13")
    assert x["raw_price_roundtrip_errors"] == 0
    assert x["factor_ratio_abs_change_gt_1pct"] >= 1
    assert x["time_point_consistent_corporate_actions_verified"] is False
    assert x["historical_release_time_factor_snapshots_available"] is False


def test_archived_source_factor_revision_detector_requires_real_pair():
    d = pd.date_range("2021-01-01", periods=3)
    a = pd.DataFrame({"date": d, "asset": "A", "factor": [1.,1.,1.]})
    b = a.copy()
    b.loc[1,"factor"] = 1.03
    result = detect_factor_revision(a, b, threshold=.01)
    assert result["overlap"] == 3
    assert result["abs_relative_revision_gt_threshold"] == 1
    with pytest.raises(ValueError, match="Duplicate"):
        detect_factor_revision(pd.concat([a,a.iloc[[0]]]), b)


def test_dynamic_member_eligibility_never_uses_future_joiners():
    frame = pd.DataFrame({
        "asset": ["A", "B", "A", "B", "A", "B"],
        "date": pd.to_datetime([
            "2021-01-04", "2021-01-04",
            "2021-01-05", "2021-01-05",
            "2021-01-06", "2021-01-06",
        ]),
    })
    active = pd.DataFrame({
        "asset": ["A","B"],
        "valid_from": pd.to_datetime(["2020-01-01","2021-01-05"]),
        "valid_to": pd.to_datetime(["2021-12-31","2021-01-06"]),
    })
    assert asset_membership_mask(frame, active).tolist() == [
        True, False, True, True, True, True,
    ]
    changed = active.copy()
    changed.loc[changed.asset.eq("B"), "valid_to"] = pd.Timestamp("2022-01-01")
    # Extending B's membership in the future must not change earlier days.
    assert asset_membership_mask(frame, changed).tolist() == [
        True, False, True, True, True, True,
    ]
