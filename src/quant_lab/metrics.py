"""Transparent annualized research statistics and benchmark comparison."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .validation import average_rank_ic


def _series_stats(returns: pd.Series) -> dict[str, float | None]:
    r = np.asarray(returns, dtype=float)
    if not r.size:
        raise ValueError("Empty return series")
    wealth = np.cumprod(1 + r)
    highwater = np.maximum.accumulate(np.r_[1.0, wealth])[1:]
    max_dd = float(np.min(wealth / highwater - 1))
    std = float(np.std(r, ddof=1)) if len(r) > 1 else 0
    sharpe = float(np.sqrt(252) * np.mean(r) / std) if std > 1e-12 else None
    ann_return = float(wealth[-1] ** (252.0 / len(r)) - 1) if wealth[-1] > 0 else -1.0
    return {
        "observations": int(len(r)),
        "total_return": float(wealth[-1] - 1),
        "annualized_return": ann_return,
        "annualized_volatility": float(std * np.sqrt(252)),
        "sharpe": sharpe,
        "max_drawdown": max_dd,
    }


def summarize(predictions: pd.DataFrame, daily: pd.DataFrame) -> dict:
    score = average_rank_ic(predictions, prediction="prediction")
    return {
        "days": int(len(daily)),
        "assets_per_day": int(predictions.groupby("date")["asset"].nunique().median()),
        "out_of_sample_rank_ic": float(score) if np.isfinite(score) else None,
        "portfolio_net": _series_stats(daily["net_return"]),
        "portfolio_gross": _series_stats(daily["gross_return"]),
        "equal_weight_benchmark_net": _series_stats(daily["benchmark_net"]),
        "equal_weight_benchmark_gross": _series_stats(daily["benchmark_gross"]),
        "mean_daily_traded_notional": float(daily["traded_notional"].mean()),
        "total_transaction_cost_fractions": float(daily["cost_fraction"].sum()),
        "notes": [
            "Equity/Sharpe annualize 252 sessions; estimates may be unstable for short samples.",
            "Benchmark and strategy both include modeled trading fees.",
            "No final liquidation fee, market impact, halts, taxes or survivorship audit.",
        ],
    }
