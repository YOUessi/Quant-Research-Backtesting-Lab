"""Daily next-open top-K long-only backtest with explicit transaction costs."""

from __future__ import annotations

import numpy as np
import pandas as pd


def topk_backtest(
    predictions: pd.DataFrame, *, k: int = 3, fee_bps: float = 10.0,
) -> pd.DataFrame:
    """Rebalance at open(t+1) on signals computed at close(t).

    Returns include open(t+1) -> open(t+2). Transaction costs are assessed on
    sum(abs(weight_today - weight_previous)), in bps of traded notional.
    The equal-weight benchmark is charged using the same fee rule.

    The terminal portfolio is *not* separately liquidated. v0 also does not
    model auction fills, limits, halted issues, market impact or borrow.
    """
    if k < 1 or not (0 <= fee_bps < 10000):
        raise ValueError("k >=1 and 0 <= fee_bps <10000 required")
    required = {"date", "asset", "execution_date", "exit_date", "target", "prediction"}
    if not required.issubset(predictions.columns):
        raise ValueError(f"Missing prediction fields {sorted(required-set(predictions.columns))}")
    pred = predictions.copy().sort_values(["date", "asset"])
    pred["date"] = pd.to_datetime(pred["date"])
    if pred.duplicated(["date", "asset"]).any():
        raise ValueError("Duplicate decision/asset predictions")
    if not np.isfinite(pred[["target", "prediction"]].to_numpy(dtype=float)).all():
        raise ValueError("Nonfinite target or prediction")
    prev_model: dict[str, float] = {}
    prev_bench: dict[str, float] = {}
    records = []
    for dt, day in pred.groupby("date", sort=True):
        if len(day) < k:
            raise ValueError(f"Top-{k} exceeds {len(day)} assets on {dt}")
        if day["execution_date"].nunique() != 1 or day["exit_date"].nunique() != 1:
            raise ValueError("Inconsistent execution or exit calendars; reject unbalanced panel")
        chosen = day.sort_values(["prediction", "asset"], ascending=[False, True]).head(k)
        model_w = {a: 1 / k for a in chosen["asset"]}
        bench_w = {a: 1 / len(day) for a in day["asset"]}
        returns = dict(zip(day["asset"], day["target"]))
        gross = float(sum(weight * returns[a] for a, weight in model_w.items()))
        benchmark_gross = float(sum(weight * returns[a] for a, weight in bench_w.items()))
        model_notional = sum(abs(model_w.get(a, 0) - prev_model.get(a, 0))
                             for a in set(model_w) | set(prev_model))
        bench_notional = sum(abs(bench_w.get(a, 0) - prev_bench.get(a, 0))
                             for a in set(bench_w) | set(prev_bench))
        cost = float(model_notional * fee_bps / 10000)
        bench_cost = float(bench_notional * fee_bps / 10000)
        records.append({
            "decision_date": pd.Timestamp(dt),
            "execution_date": pd.Timestamp(day["execution_date"].iloc[0]),
            "exit_date": pd.Timestamp(day["exit_date"].iloc[0]),
            "gross_return": gross,
            "net_return": gross - cost * (1 + gross),
            "benchmark_gross": benchmark_gross,
            "benchmark_net": benchmark_gross - bench_cost * (1 + benchmark_gross),
            "traded_notional": model_notional,
            "benchmark_traded_notional": bench_notional,
            "cost_fraction": cost,
            "benchmark_cost_fraction": bench_cost,
            "selected_assets": ",".join(sorted(chosen["asset"])),
        })
        prev_model, prev_bench = model_w, bench_w
    return pd.DataFrame.from_records(records)
