"""Regressions for hard-to-notice time-series benchmark mistakes."""

import pandas as pd
import pytest

from quant_lab.backtest import topk_backtest
from quant_lab.data import make_demo_market
from quant_lab.features import make_factor_panel
from quant_lab.validation import WalkForwardConfig, walk_forward


def test_first_test_predictions_independent_of_heldout_target():
    """Mutating future OOS labels must NOT change predictions made before seeing them."""
    panel = make_factor_panel(make_demo_market(days=145, assets=5, seed=12))
    cfg = WalkForwardConfig(min_train=35, validation_days=10, test_days=10)
    original, _ = walk_forward(panel, model_kind="ridge", cfg=cfg)
    first_test_date = sorted(panel.date.unique())[cfg.min_train + cfg.validation_days + 2]
    altered = panel.copy()
    altered.loc[altered.date >= first_test_date, "target"] = -0.99
    predicted_after_mutation, _ = walk_forward(altered, model_kind="ridge", cfg=cfg)
    first_end = original.date[original.date >= first_test_date].sort_values().unique()[cfg.test_days - 1]
    old = original[original.date <= first_end][["date", "asset", "prediction"]]
    new = predicted_after_mutation[predicted_after_mutation.date <= first_end][["date", "asset", "prediction"]]
    pd.testing.assert_frame_equal(old.reset_index(drop=True), new.reset_index(drop=True))


def test_fee_zero_is_identical_to_gross():
    panel = make_factor_panel(make_demo_market(days=145, assets=5, seed=22))
    pred, _ = walk_forward(
        panel, model_kind="factor",
        cfg=WalkForwardConfig(min_train=35, validation_days=10, test_days=10),
    )
    daily = topk_backtest(pred, k=2, fee_bps=0)
    assert (daily["gross_return"] == daily["net_return"]).all()
    assert (daily["benchmark_gross"] == daily["benchmark_net"]).all()
    assert (daily["cost_fraction"] == 0).all()
