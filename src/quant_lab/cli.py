"""Command-line entry point for auditable CPU demos and market-data baselines."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from .backtest import topk_backtest
from .data import make_demo_market, validate_market
from .features import BASE_FEATURES, make_factor_panel
from .metrics import summarize
from .validation import WalkForwardConfig, walk_forward


def _json(obj):
    if isinstance(obj, np.generic):
        return obj.item()
    if isinstance(obj, pd.Timestamp):
        return obj.isoformat()
    if isinstance(obj, Path):
        return str(obj)
    raise TypeError(f"Cannot JSON serialize {type(obj)!r}")


def _common(sub: argparse.ArgumentParser) -> None:
    sub.add_argument("--output", type=Path, required=True, help="New run directory (will not overwrite)")
    sub.add_argument("--model", choices=["ridge", "lightgbm", "factor"], default="ridge")
    sub.add_argument("--train-days", type=int, default=60)
    sub.add_argument("--validation-days", type=int, default=20)
    sub.add_argument("--test-days", type=int, default=15)
    sub.add_argument("--top-k", type=int, default=3)
    sub.add_argument("--fee-bps", type=float, default=10.0)
    sub.add_argument("--seed", type=int, default=42)


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="quant-lab",
        description="Leakage-audited CPU quantitative factor baseline (not investment advice)",
    )
    subs = parser.add_subparsers(dest="cmd", required=True)
    demo = subs.add_parser("demo", help="Synthetic smoke test; NEVER report as real-market alpha")
    demo.add_argument("--days", type=int, default=260)
    demo.add_argument("--assets", type=int, default=8)
    _common(demo)
    csv = subs.add_parser("csv", help="Use fully balanced, user-provided daily adjusted OHLCV")
    csv.add_argument("--input", type=Path, required=True)
    csv.add_argument("--provenance", required=True, help="Dataset/source and adjustment notes")
    _common(csv)
    qlib = subs.add_parser("qlib", help="Optional Qlib Alpha158 adapter; real dataset required")
    qlib.add_argument("--provider-uri", required=True)
    qlib.add_argument("--instruments", required=True, help="e.g. csi300 (audit historical membership)")
    qlib.add_argument("--start", required=True)
    qlib.add_argument("--end", required=True)
    qlib.add_argument("--fit-end", required=True)
    _common(qlib)
    return parser


def run(args: argparse.Namespace) -> dict:
    if args.cmd == "demo":
        market = make_demo_market(days=args.days, assets=args.assets, seed=args.seed)
        data_kind = "SYNTHETIC_DEMO_NOT_REAL_MARKET"
        provenance = "NumPy seeded random toy market, no trading claims"
        source_sha = None
        extras: tuple[str, ...] = ()
    elif args.cmd == "csv":
        if not args.input.is_file():
            raise FileNotFoundError(args.input)
        market = validate_market(pd.read_csv(args.input))
        source_sha = hashlib.sha256(args.input.read_bytes()).hexdigest()
        provenance, data_kind = args.provenance, "USER_CSV_REAL_DATA_UNAUDITED"
        extras = ()
    elif args.cmd == "qlib":
        from .qlib_adapter import load_qlib_alpha158
        market, extras = load_qlib_alpha158(
            provider_uri=args.provider_uri, instruments=args.instruments,
            start=args.start, end=args.end, fit_end=args.fit_end,
        )
        market = validate_market(market)
        data_kind, source_sha = "QLIB_ALPHA158_UNAUDITED", None
        provenance = f"provider={args.provider_uri}; instruments={args.instruments}"
    else:
        raise ValueError(f"Unsupported source {args.cmd}")
    panel = make_factor_panel(market, extra_features=extras)
    # Never evaluate on a date where a market asset disappeared during feature
    # processing. This does not solve history-dependent constituent selection.
    full_universe = tuple(sorted(market["asset"].unique()))
    if any(tuple(sorted(group["asset"])) != full_universe
           for _, group in panel.groupby("date")):
        raise ValueError("Factors/targets produced an unbalanced universe: stop instead of filling")
    cfg = WalkForwardConfig(
        min_train=args.train_days, validation_days=args.validation_days,
        test_days=args.test_days, seed=args.seed,
    )
    feature_cols = (*BASE_FEATURES, *extras)
    predictions, folds = walk_forward(
        panel, model_kind=args.model, cfg=cfg, feature_cols=feature_cols,
    )
    daily = topk_backtest(predictions, k=args.top_k, fee_bps=args.fee_bps)
    metrics = summarize(predictions, daily)
    manifest = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "data_kind": data_kind, "provenance": provenance,
        "source_sha256": source_sha, "source_rows": len(market),
        "n_assets": market["asset"].nunique(),
        "source_date_min": market["date"].min().date().isoformat(),
        "source_date_max": market["date"].max().date().isoformat(),
        "model": args.model,
        "feature_names": list(feature_cols),
        "config": asdict(cfg),
        "top_k": args.top_k, "fee_bps": args.fee_bps,
        "n_folds": len(folds),
        "point_in_time_universe_audited": False,
        "live_order_execution_verified": False,
        "notes": "No performance claim; demo synthetic, real inputs require independent provenance audit.",
    }
    path: Path = args.output
    # Intentionally refuse overwrite to keep experiment history immutable.
    path.mkdir(parents=True, exist_ok=False)
    predictions.to_csv(path / "predictions.csv", index=False)
    daily.to_csv(path / "daily_returns.csv", index=False)
    (path / "metrics.json").write_text(
        json.dumps(metrics, indent=2, ensure_ascii=False, default=_json), encoding="utf-8"
    )
    (path / "folds.json").write_text(
        json.dumps(folds, indent=2, ensure_ascii=False, default=_json), encoding="utf-8"
    )
    (path / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, default=_json), encoding="utf-8"
    )
    print(json.dumps(
        {"run_dir": str(path), "data_kind": data_kind, "folds": len(folds),
         "metrics": metrics}, ensure_ascii=False, indent=2, default=_json,
    ))
    return metrics


def main(argv: list[str] | None = None) -> int:
    args = make_parser().parse_args(argv)
    try:
        run(args)
        return 0
    except (ValueError, RuntimeError, FileNotFoundError, FileExistsError) as exc:
        print(f"quant-lab error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
