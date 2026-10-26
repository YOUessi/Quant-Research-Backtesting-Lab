"""EXP-002 reproducible preregistered dynamic-constituent historical study.

Run data collection and execution in separate stages. All historical raw
material and event logs remain gitignored. None of the adjusted Qlib proxy
returns is asserted to be an investable performance estimate.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from .event_simulator import ExecutionConfig, simulate
from .pit_adjustment import adjustment_audit
from .pit_universe import load_dynamic_data

FROZEN_FIRST = "2021-01-04"
FROZEN_LAST = "2022-12-30"


def _write_json(path: Path, payload: dict) -> None:
    if path.exists():
        raise FileExistsError("Refusing to overwrite experiment artifact: " + str(path))
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")


def data_stage(*, provider: Path, source_manifest: Path,
               out: Path, first: str = FROZEN_FIRST,
               last: str = FROZEN_LAST) -> dict:
    if (first, last) != (FROZEN_FIRST, FROZEN_LAST):
        raise ValueError("EXP-002 dates are frozen; create a newly preregistered EXP to change")
    if out.exists():
        raise FileExistsError("Refusing to overwrite existing raw-data research directory")
    panel, membership_audit = load_dynamic_data(
        provider=provider, source_manifest=source_manifest,
        first_test=first, last_test=last,
    )
    factor_audit = adjustment_audit(panel, start=first, end=last)
    out.mkdir(parents=True, exist_ok=False)
    panel.to_parquet(out/"dynamic_history.parquet", index=False)
    report = {
        "experiment": "EXP-002",
        "stage": "PRE_REGISTERED_UNIVERSE_DATA_AND_PIT_AUDIT",
        "evaluation_start": first, "evaluation_end": last,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "membership": membership_audit,
        "adjustments": factor_audit,
        "source_snapshot_pinned": True,
        "point_in_time_adjustment_certified": False,
        "latest_github_source_reference": (
            "docs/EXP002_PRE_REGISTRATION.md"
        ),
    }
    _write_json(out/"audit.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return report


def _describe(daily: pd.DataFrame, report: dict) -> dict:
    if report["status"].startswith("CENSORED_"):
        return {"status": report["status"], "reason": report["stop_event"],
                "return_withheld": True}
    r = daily["daily_return_proxy"].to_numpy(dtype=float)
    if len(r) < 3 or not np.isfinite(r).all():
        return {"status": "INSUFFICIENT_DATA", "return_withheld": True}
    compounded = np.cumprod(1 + r)
    peak = np.maximum.accumulate(np.r_[1.0, compounded])[1:]
    sd = float(np.std(r, ddof=1))
    return {
        "status": report["status"],
        "return_is_adjusted_snapshot_proxy_not_executable": True,
        "n_sessions": len(daily),
        "cum_total_return_proxy": float(compounded[-1] - 1),
        "max_drawdown_proxy": float(np.min(compounded / peak - 1)),
        "daily_mean_arithmetic_return_proxy": float(np.mean(r)),
        "annualized_sharpe_proxy": float(np.sqrt(252) * np.mean(r) / sd)
        if sd > 1e-12 else None,
        "n_stale_valuation_days": report["n_stale_close_days"],
        "n_fill_assumption_events": report["n_model_filled_attempts"],
        "blocked_orders": report["blocked_attempts"],
        "unpriced_delisting_cashflow_complete": False,
        "point_in_time_adjustment_certified": False,
        "return_withheld": False,
    }


def simulate_stage(*, audit_dir: Path, out: Path,
                   include_proxy_stress: bool = True) -> dict:
    if out.exists():
        raise FileExistsError("Refusing to overwrite existing execution results")
    audit = json.loads((audit_dir/"audit.json").read_text(encoding="utf-8"))
    if audit["experiment"] != "EXP-002":
        raise ValueError("Only preregistered EXP-002 panel can be simulated")
    panel = pd.read_parquet(audit_dir/"dynamic_history.parquet")
    first, last = audit["evaluation_start"], audit["evaluation_end"]
    if (first, last) != (FROZEN_FIRST, FROZEN_LAST):
        raise ValueError("Evaluation dates differ from frozen protocol")
    # These are PREDECLARED. Never choose the most profitable rule on
    # EXP-002 and then call it an untouched independent holdout.
    configs = {
        "momentum_daily_10bps": ExecutionConfig(
            strategy="momentum", rebalance_sessions=1, k=10, fee_bps=10),
        "momentum_every5_10bps": ExecutionConfig(
            strategy="momentum", rebalance_sessions=5, k=10, fee_bps=10),
        "pit_members_equal_10bps": ExecutionConfig(
            strategy="full_equal", rebalance_sessions=1, k=10, fee_bps=10),
        "momentum_daily_0bps": ExecutionConfig(
            strategy="momentum", rebalance_sessions=1, k=10, fee_bps=0),
        "momentum_every5_0bps": ExecutionConfig(
            strategy="momentum", rebalance_sessions=5, k=10, fee_bps=0),
        "momentum_daily_20bps": ExecutionConfig(
            strategy="momentum", rebalance_sessions=1, k=10, fee_bps=20),
        "momentum_every5_20bps": ExecutionConfig(
            strategy="momentum", rebalance_sessions=5, k=10, fee_bps=20),
    }
    if include_proxy_stress:
        configs["momentum_every5_10bps_limit_PROXY"] = ExecutionConfig(
            strategy="momentum", rebalance_sessions=5, k=10, fee_bps=10,
            price_limit_proxy=True)
    out.mkdir(parents=True, exist_ok=False)
    summaries = {}
    for name, cfg in configs.items():
        daily, events, model_report = simulate(
            panel, first_test=first, last_test=last, cfg=cfg,
        )
        model_dir = out/name
        model_dir.mkdir()
        daily.to_csv(model_dir/"daily.csv", index=False)
        events.to_csv(model_dir/"events.csv", index=False)
        _write_json(model_dir/"execution_audit.json", model_report)
        summaries[name] = _describe(daily, model_report)
        print(name, summaries[name]["status"],
              summaries[name].get("cum_total_return_proxy", "WITHHELD"),
              "filled", model_report["n_model_filled_attempts"],
              "blocked", sum(model_report["blocked_attempts"].values()))
    results = {
        "kind": "EXP002_DYNAMIC_CSI300_2021_2022_PRE_REGISTERED_EXECUTION_AUDIT",
        "status": "PROXY_ONLY_PIT_ADJUSTMENT_UNVERIFIABLE",
        "frozen_validation_first": first, "frozen_validation_last": last,
        "release_sha256": audit["membership"]["source_sha256"],
        "historical_member_count": {
            x: audit["membership"][x] for x in (
                "n_ever_index_members", "hist_member_count_min",
                "hist_member_count_max", "n_symbols_with_listing_end_in_window"
            )
        },
        "preregistration": "docs/EXP002_PRE_REGISTRATION.md",
        "full_index_membership_asof_each_date": True,
        "portfolio_price_representation": "Qlib adjusted-price entitlement proxy only",
        "broker_orderbook_evidence_present": False,
        "official_exchange_limit_prices_present": False,
        "actual_delisting_payouts_present": False,
        "independent_factor_history_snapshots_present": False,
        "result_selection_tuned_on_holdout": False,
        "models": summaries,
        "interpretation": (
            "Exploratory independent period, expanded membership, halt-aware "
            "fill gate with unresolved delistings censored. Any completed "
            "portfolio returns are adjusted-series proxy valuations, never "
            "executed trade outcomes. After seeing EXP-002 results it is no "
            "longer an untouched period for further method development."
        ),
    }
    _write_json(out/"EXP002_SUMMARY.json", results)
    return results


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="Independent EXP-002 full CSI300 PIT proxy evaluation")
    subs = p.add_subparsers(dest="command", required=True)
    data = subs.add_parser("data")
    data.add_argument("--provider", type=Path, required=True)
    data.add_argument("--source-manifest", type=Path, required=True)
    data.add_argument("--output", type=Path, required=True)
    sim = subs.add_parser("simulate")
    sim.add_argument("--data", type=Path, required=True)
    sim.add_argument("--output", type=Path, required=True)
    sim.add_argument("--no-proxy-stress", action="store_true")
    args = p.parse_args(argv)
    if args.command == "data":
        data_stage(provider=args.provider, source_manifest=args.source_manifest,
                   out=args.output)
    else:
        report = simulate_stage(
            audit_dir=args.data, out=args.output,
            include_proxy_stress=not args.no_proxy_stress,
        )
        print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
