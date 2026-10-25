"""No-lookahead fold boundaries, fees, baseline behavior, and CLI run tests."""

from argparse import Namespace

import numpy as np
import pandas as pd
import pytest

from quant_lab.backtest import topk_backtest
from quant_lab.cli import run
from quant_lab.data import make_demo_market
from quant_lab.features import make_factor_panel
from quant_lab.validation import WalkForwardConfig, walk_forward


def test_purged_time_boundaries_and_nonoverlap():
    panel = make_factor_panel(make_demo_market(days=148, assets=4, seed=4))
    dates = sorted(pd.to_datetime(panel.date.unique()))
    index = {d.strftime("%Y-%m-%d"): n for n, d in enumerate(dates)}
    pred, folds = walk_forward(
        panel, model_kind="ridge",
        cfg=WalkForwardConfig(min_train=35, validation_days=12, test_days=9),
    )
    assert folds
    assert not pred.duplicated(["date", "asset"]).any()
    for f in folds:
        assert index[f["validation_start"]] - index[f["train_end"]] >= 2
        assert index[f["test_start"]] - index[f["final_fit_end"]] >= 2
        assert index[f["test_start"]] - index[f["validation_end"]] >= 2


def test_factor_baseline_and_models_share_oos_dates():
    panel = make_factor_panel(make_demo_market(days=140, assets=4, seed=5))
    cfg = WalkForwardConfig(min_train=35, validation_days=10, test_days=11)
    factor, _ = walk_forward(panel, model_kind="factor", cfg=cfg)
    ridge, _ = walk_forward(panel, model_kind="ridge", cfg=cfg)
    assert factor[["date", "asset"]].equals(ridge[["date", "asset"]])
    assert np.isfinite(ridge["prediction"]).all()


def test_trading_cost_and_benchmark_charge_traded_notional():
    pred = pd.DataFrame([
        ("2025-01-06", "A", "2025-01-07", "2025-01-08", .02, 0.9),
        ("2025-01-06", "B", "2025-01-07", "2025-01-08", .00, 0.1),
        ("2025-01-07", "A", "2025-01-08", "2025-01-09", .01, 0.1),
        ("2025-01-07", "B", "2025-01-08", "2025-01-09", .03, 0.9),
    ], columns=["date", "asset", "execution_date", "exit_date", "target", "prediction"])
    results = topk_backtest(pred, k=1, fee_bps=10.0)
    assert results.iloc[0].traded_notional == pytest.approx(1.0)
    assert results.iloc[1].traded_notional == pytest.approx(2.0)
    assert results.iloc[0].net_return == pytest.approx((1-.001)*1.02-1)
    assert results.iloc[1].net_return == pytest.approx((1-.002)*1.03-1)
    assert results.iloc[0].benchmark_traded_notional == pytest.approx(1.0)
    assert results.iloc[1].benchmark_traded_notional == pytest.approx(0.0)
    assert (results["net_return"] <= results["gross_return"]).all()


def test_cli_synthetic_run_preserves_manifest_and_refuses_overwrite(tmp_path):
    output = tmp_path / "demo"
    args = Namespace(
        cmd="demo", days=128, assets=4, seed=6, output=output, model="ridge",
        train_days=35, validation_days=10, test_days=9,
        top_k=2, fee_bps=10.0,
    )
    result = run(args)
    assert result["days"] > 0
    import json
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["data_kind"] == "SYNTHETIC_DEMO_NOT_REAL_MARKET"
    assert manifest["point_in_time_universe_audited"] is False
    assert (output / "predictions.csv").is_file()
    assert (output / "daily_returns.csv").is_file()
    assert (output / "folds.json").is_file()
    with pytest.raises(FileExistsError):
        run(args)
