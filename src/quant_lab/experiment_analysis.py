"""Reproducible cost sensitivity and paired block-bootstrap OOS diagnostics.

Consumes frozen predictions from earlier fitted models. NO retraining, model
selection or hyperparameter optimization occurs in this diagnostic module.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from .backtest import topk_backtest
from .metrics import summarize


def paired_block_mean_interval(
    daily_a: pd.Series, daily_b: pd.Series,
    *, block: int = 5, draws: int = 1500, seed: int = 11,
) -> dict:
    """Circular moving-block bootstrap for paired daily excess-return mean.

    An exploratory dependence-aware uncertainty diagnostic, NOT a tradable
    strategy significance guarantee nor multiple-hypothesis correction.
    """
    a = np.asarray(daily_a, dtype=float)
    b = np.asarray(daily_b, dtype=float)
    if a.shape != b.shape or len(a) < block * 3 or block < 1 or draws < 100:
        raise ValueError("Paired bootstrap needs aligned series and >=3 blocks")
    if not (np.isfinite(a).all() and np.isfinite(b).all()):
        raise ValueError("Nonfinite daily returns")
    diff = a - b
    rng = np.random.default_rng(seed)
    n = len(diff)
    nblocks = int(np.ceil(n / block))
    values = np.empty(draws, dtype=float)
    for i in range(draws):
        starts = rng.integers(0, n, size=nblocks)
        indices = (starts[:, None] + np.arange(block)[None, :]) % n
        values[i] = np.mean(diff[indices.reshape(-1)[:n]])
    lo, hi = np.quantile(values, [0.025, 0.975])
    return {
        "n_sessions": n,
        "observed_mean_daily_strategy_minus_benchmark": float(np.mean(diff)),
        "bootstrap_95pct_mean_daily_diff": [float(lo), float(hi)],
        "bootstrap_seed": seed,
        "block_sessions": block,
        "bootstrap_draws": draws,
        "method": "paired circular moving-block bootstrap of daily arithmetic return differences",
        "warning": (
            "Descriptive only; dependent folds, selection of assets, survivorship, "
            "auction execution, fees, repeated model comparisons and nonstationarity "
            "preclude a formal positive-alpha significance claim."
        ),
    }


def analyze(run_dirs: dict[str, Path], *, k: int, fees: tuple[float, ...], seed: int = 11) -> dict:
    """Compare all frozen out-of-sample predictions on identical calendar days."""
    results = {}
    common_dates = None
    common_assets = None
    reference_source = None
    for name, path in run_dirs.items():
        pred = pd.read_csv(path / "predictions.csv", parse_dates=[
            "date", "execution_date", "exit_date"
        ])
        report = json.loads((path / "report.json").read_text(encoding="utf-8"))
        if report.get("kind") != "REAL_HISTORICAL_DATA_EXPLORATORY_NOT_TRADEABLE":
            raise ValueError(f"{name}: must use frozen Qlib real historical runs, not synthetic")
        source = report["source_release"].get("archive_sha256")
        if reference_source is None:
            reference_source = source
        elif source != reference_source:
            raise ValueError("Model reports use different source data releases")
        keys = sorted((str(row.date), row.asset) for row in pred.itertuples(index=False))
        if common_dates is None:
            common_dates, common_assets = len(pred.date.unique()), keys
        elif keys != common_assets:
            raise ValueError("Models do not share exactly the same OOS asset/date keys")
        table = []
        for fee in fees:
            daily = topk_backtest(pred, k=k, fee_bps=fee)
            m = summarize(pred, daily)
            interval = paired_block_mean_interval(
                daily["net_return"], daily["benchmark_net"], seed=seed,
            )
            table.append({
                "fee_bps": fee,
                "days": m["days"],
                "mean_daily_traded_notional": m["mean_daily_traded_notional"],
                "total_return_strategy_gross": m["portfolio_gross"]["total_return"],
                "total_return_strategy_net": m["portfolio_net"]["total_return"],
                "total_return_benchmark_net": m["equal_weight_benchmark_net"]["total_return"],
                "strategy_sharpe_net": m["portfolio_net"]["sharpe"],
                "max_drawdown_net": m["portfolio_net"]["max_drawdown"],
                "out_of_sample_rank_ic": m["out_of_sample_rank_ic"],
                "paired_bootstrap": interval,
            })
        results[name] = {"n_rows": len(pred), "fee_sensitivity": table}
    return {
        "kind": "FROZEN_OOS_REAL_DATA_EXPLORATORY_FEE_SENSITIVITY",
        "data_bundle_sha256": reference_source,
        "prediction_files_are_gitignored": True,
        "predictions_not_refitted_or_selected_on_test": True,
        "same_asset_date_keys_across_models": True,
        "cost_grid_is_descriptive_not_strategy_optimized": True,
        "price_auction_or_point_in_time_corporate_action_audit_complete": False,
        "n_models": len(results), "n_oos_decision_days": common_dates,
        "models": results,
        "warning": (
            "A fixed 12-name inception-basket illustration, not full CSI300 replication. "
            "Returns depend on simplified open-to-open fills, normalized price history, "
            "no market impact, and unmodeled intraday halts and trade limits. "
            "No statistically validated market alpha is claimed."
        ),
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--factor-run", type=Path, required=True)
    p.add_argument("--ridge-run", type=Path, required=True)
    p.add_argument("--lightgbm-run", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--top-k", type=int, default=3)
    p.add_argument("--fees", type=float, nargs="+", default=[0, 5, 10, 20])
    args = p.parse_args()
    out = analyze({
        "factor": args.factor_run,
        "ridge": args.ridge_run,
        "lightgbm": args.lightgbm_run,
    }, k=args.top_k, fees=tuple(args.fees))
    if args.out.exists():
        raise FileExistsError(f"Would overwrite prior report: {args.out}")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for name, metrics in out["models"].items():
        print(name)
        for row in metrics["fee_sensitivity"]:
            print(
                f"  fee_bps={row['fee_bps']:4g} "
                f"net={row['total_return_strategy_net']:+.4f} "
                f"bench={row['total_return_benchmark_net']:+.4f} "
                f"IC={row['out_of_sample_rank_ic']:+.5f}"
            )
    print(f"Saved analysis: {args.out}")


if __name__ == "__main__":
    main()
