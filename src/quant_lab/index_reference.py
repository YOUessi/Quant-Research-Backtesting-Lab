"""Non-investable CSI300 *price index* context for EXP-002.

The provider includes SH000300: an index reference, NOT an executable,
fee-adjusted portfolio. No benchmark substitution or unreported dividends.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


def price_index_reference(provider: Path, source_manifest: Path,
                          *, start="2021-01-04", end="2022-12-30") -> dict:
    import qlib
    from qlib.data import D

    release = json.loads(source_manifest.read_text(encoding="utf-8"))
    if (start, end) != ("2021-01-04", "2022-12-30"):
        raise ValueError("EXP002 dates must stay frozen")
    if release["archive_sha256"] != (
        "sha256:0a2974da97b4737e503ecddeea8bb3b2179e0e16ea0fb19fa373ff14155bf315"
    ):
        raise ValueError("Unexpected source release")
    qlib.init(provider_uri=str(provider.resolve()), region="cn", kernels=1,
              logging_level="WARNING", expression_cache=None,dataset_cache=None)
    reference = D.features(["SH000300"], ["$close"], start_time=start,
                           end_time=end, freq="day")
    calendar = pd.DatetimeIndex(D.calendar(start_time=start,
                                           end_time=end, freq="day")).normalize()
    if reference.empty or "$close" not in reference:
        raise ValueError("No CSI300 index close reference in Qlib source")
    series = reference["$close"].droplevel("instrument")
    series.index = pd.to_datetime(series.index).normalize()
    series = series.reindex(calendar)
    values = series.to_numpy(dtype=float)
    good = np.isfinite(values) & (values > 0)
    if not good.all():
        raise ValueError(f"Missing/invalid CSI300 reference index days: {int((~good).sum())}")
    wealth = values / values[0]
    high = np.maximum.accumulate(wealth)
    result = {
        "kind": "EXP002_REFERENCE_ONLY_NONINVESTABLE_CSI300_PRICE_INDEX",
        "ticker": "SH000300",
        "start": str(calendar[0].date()), "end": str(calendar[-1].date()),
        "n_reference_sessions": len(calendar),
        "price_level_start_snapshot": float(values[0]),
        "price_level_end_snapshot": float(values[-1]),
        "price_change_over_exact_dates": float(values[-1]/values[0]-1),
        "max_price_index_drawdown": float(np.min(wealth/high-1)),
        "source_release_sha256": release["archive_sha256"],
        "dividends_or_total_return_index_used": False,
        "market_impact_or_transaction_costs_used": False,
        "idealized_portfolio_covered": False,
        "not_comparable_as_an_executable_total_return_benchmark": True,
        "note": ("Price-index level reference only, not an executable index "
                 "replicating portfolio; Qlib proxy stock portfolios assume "
                 "adjusted-price total-return units and synthetic next-open fills.")
    }
    return result


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--provider",type=Path,required=True)
    p.add_argument("--source-manifest",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    args=p.parse_args()
    result=price_index_reference(args.provider,args.source_manifest)
    if args.out.exists():
        raise FileExistsError(args.out)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps(result,indent=2,ensure_ascii=False))


if __name__=="__main__":
    main()
