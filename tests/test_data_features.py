"""Causality and data-integrity regression tests."""

import pandas as pd
import pytest

from quant_lab.data import make_demo_market, validate_market
from quant_lab.features import BASE_FEATURES, make_factor_panel


def test_synthetic_seed_is_repeatable():
    a = make_demo_market(days=110, assets=5, seed=7)
    b = make_demo_market(days=110, assets=5, seed=7)
    pd.testing.assert_frame_equal(a, b)


def test_duplicate_and_missing_dates_fail_closed():
    a = make_demo_market(days=110, assets=5, seed=7)
    with pytest.raises(ValueError, match="Duplicate"):
        validate_market(pd.concat([a, a.iloc[[0]]]))
    with pytest.raises(ValueError, match="Unbalanced"):
        validate_market(a.drop(a.index[15]))


def test_causal_features_do_not_use_future_prices():
    bars = make_demo_market(days=120, assets=4, seed=11)
    original = make_factor_panel(bars)
    signal_date = pd.Timestamp("2023-04-10")
    assert signal_date in set(original["date"])
    altered = bars.copy()
    altered.loc[altered["date"] > signal_date, ["open", "close", "volume"]] *= 2.0
    after = make_factor_panel(altered)
    old = original[original["date"] == signal_date].sort_values("asset")
    new = after[after["date"] == signal_date].sort_values("asset")
    pd.testing.assert_frame_equal(
        old[list(BASE_FEATURES)].reset_index(drop=True),
        new[list(BASE_FEATURES)].reset_index(drop=True),
    )


def test_target_is_next_open_to_following_open():
    bars = make_demo_market(days=120, assets=4, seed=21)
    frame = make_factor_panel(bars)
    row = frame.iloc[0]
    history = bars[bars.asset == row.asset].sort_values("date").reset_index(drop=True)
    i = int(history.index[history["date"] == row["date"]][0])
    expected = history.iloc[i + 2]["open"] / history.iloc[i + 1]["open"] - 1.0
    assert row.target == pytest.approx(expected)
    assert row.execution_date == history.iloc[i + 1]["date"]
    assert row.exit_date == history.iloc[i + 2]["date"]


def test_reject_target_in_feature_set():
    with pytest.raises(ValueError, match="Extra factor"):
        make_factor_panel(make_demo_market(days=110, assets=4), extra_features=("target",))
