"""Point-in-time *eligibility*-aware Qlib CSI300 research runner.

An index constituent is selected at the first analysis date, never by future
price coverage. Historical membership is applied as-of each *decision* date.
Corporate-action factor revisions / exact auction fills and incomplete
delisting/halt cash settlement remain important known model limitations.

The runner refuses a dataset with missing future entry/exit prices for an
otherwise eligible signal. Silently discarding such rows would look ahead.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from .backtest import topk_backtest
from .features import BASE_FEATURES
from .metrics import summarize
from .validation import WalkForwardConfig, walk_forward


def read_member_intervals(filepath: Path) -> pd.DataFrame:
    """Load historical index constituent intervals (symbol, first, last inclusive)."""
    if not filepath.is_file():
        raise FileNotFoundError(filepath)
    table = pd.read_csv(
        filepath, sep="\t", header=None,
        names=["asset", "valid_from", "valid_to"], dtype={"asset": "string"}
    )
    if table.empty:
        raise ValueError("Empty index membership file")
    table["asset"] = table["asset"].str.upper().str.strip()
    for col in ("valid_from", "valid_to"):
        table[col] = pd.to_datetime(table[col], errors="raise").dt.normalize()
    if table[["asset", "valid_from", "valid_to"]].isna().any().any():
        raise ValueError("Invalid index membership record")
    if (table["valid_from"] > table["valid_to"]).any():
        raise ValueError("Index membership interval inverted")
    if (table["asset"] == "").any():
        raise ValueError("Empty member ticker")
    return table


def members_on(intervals: pd.DataFrame, date) -> set[str]:
    timestamp = pd.Timestamp(date).normalize()
    f = (intervals.valid_from <= timestamp) & (timestamp <= intervals.valid_to)
    return set(intervals.loc[f, "asset"].tolist())


def membership_mask(frame: pd.DataFrame, intervals: pd.DataFrame) -> pd.Series:
    """Return eligibility from intervals, never from future price availability."""
    mask = pd.Series(False, index=frame.index)
    for ticker, group in intervals.groupby("asset", sort=False):
        row_ticker = frame["asset"].eq(ticker)
        if not row_ticker.any():
            continue
        active = pd.Series(False, index=frame.index)
        for interval in group.itertuples(index=False):
            active |= (frame["date"] >= interval.valid_from) & (
                frame["date"] <= interval.valid_to
            )
        mask |= row_ticker & active
    return mask


def build_calendar_panel(
    raw: pd.DataFrame,
    alpha: pd.DataFrame,
    calendar: pd.DatetimeIndex,
    selected: tuple[str, ...],
    intervals: pd.DataFrame,
    *,
    first_decision: pd.Timestamp,
    last_decision: pd.Timestamp,
) -> tuple[pd.DataFrame, dict]:
    """Reindex to a global *exchange* calendar before shifting future opens.

    This prevents a suspended ticker's next *available* print from silently
    being treated as tomorrow's price. Missing/zero bar data is never ffilled.
    """
    grid = pd.MultiIndex.from_product(
        [selected, calendar], names=["asset", "date"],
    ).to_frame(index=False)
    raw = raw.copy()
    raw["date"] = pd.to_datetime(raw["date"]).dt.normalize()
    raw["asset"] = raw["asset"].astype(str)
    raw = raw[["date", "asset", "open", "close", "volume"]]
    if raw.duplicated(["date", "asset"]).any():
        raise ValueError("Duplicate Qlib asset/date prices")
    panel = grid.merge(raw, on=["asset", "date"], how="left", validate="one_to_one")
    for name in ["open", "close", "volume"]:
        panel[name] = pd.to_numeric(panel[name], errors="coerce")
        panel.loc[~np.isfinite(panel[name]) | (panel[name] <= 0), name] = np.nan

    # The date grid is exactly the exchange calendar for every asset.
    group = panel.groupby("asset", sort=False)
    cl = group["close"]
    vol = group["volume"]
    opening = group["open"]
    one = cl.pct_change(fill_method=None)
    panel["mom_5"] = cl.pct_change(periods=5, fill_method=None)
    panel["mom_20"] = cl.pct_change(periods=20, fill_method=None)
    panel["reversal_1"] = -one
    panel["volatility_10"] = one.groupby(panel["asset"]).transform(
        lambda s: s.rolling(10, min_periods=10).std()
    )
    panel["volume_ratio_10"] = vol.transform(
        lambda s: s / s.rolling(10, min_periods=10).mean() - 1
    )
    panel["ma_gap_10"] = cl.transform(
        lambda s: s / s.rolling(10, min_periods=10).mean() - 1
    )
    panel["execution_date"] = group["date"].shift(-1)
    panel["exit_date"] = group["date"].shift(-2)
    panel["target"] = opening.shift(-2) / opening.shift(-1) - 1

    alpha = alpha.copy()
    alpha["date"] = pd.to_datetime(alpha["date"]).dt.normalize()
    alpha["asset"] = alpha["asset"].astype(str)
    if alpha.duplicated(["date", "asset"]).any():
        raise ValueError("Duplicate Qlib Alpha158 date/asset features")
    alpha_cols = [c for c in alpha.columns if c.startswith("alpha_")]
    if len(alpha_cols) < 140:
        raise ValueError(f"Expected Qlib Alpha158 features, got {len(alpha_cols)}")
    panel = panel.merge(alpha, on=["date", "asset"], how="left", validate="one_to_one")
    # Membership is defined by historical constituent intervals, not future
    # bar presence or eligibility at the end of the sample.
    panel["eligible_asof"] = membership_mask(panel, intervals)
    in_period = panel["date"].between(first_decision, last_decision, inclusive="both")
    known_features = np.isfinite(
        panel[list(BASE_FEATURES)].to_numpy(dtype=float)
    ).all(axis=1)
    signal_candidates = panel["eligible_asof"] & in_period & known_features
    future_bad = signal_candidates & (
        ~np.isfinite(panel["target"])
        | panel["execution_date"].isna()
        | panel["exit_date"].isna()
    )
    # Do not silently drop instruments using tomorrow's tradability.
    if future_bad.any():
        examples = panel.loc[future_bad, ["date", "asset"]].head(12).astype(str)
        raise ValueError(
            f"{int(future_bad.sum())} signal-eligible rows lack next 2 session opens. "
            "Dropping them would create future-availability look-ahead; abort. "
            f"Examples: {examples.to_dict('records')}"
        )

    out = panel.loc[signal_candidates].copy()
    # Align label calendar; no asset calendar-skipping is allowed.
    assert out["target"].notna().all()
    assert out["execution_date"].gt(out["date"]).all()
    assert out["exit_date"].gt(out["execution_date"]).all()
    out[alpha_cols] = out[alpha_cols].replace([np.inf, -np.inf], np.nan)

    quality = {
        "candidate_eligible_rows": int(signal_candidates.sum()),
        "future_availability_invalid": int(future_bad.sum()),
        "observed_price_rows": int(panel["close"].notna().sum()),
        "total_asset_session_grid_rows": len(panel),
        "missing_or_invalid_price_rows": int(panel["close"].isna().sum()),
        "decision_count": int(out.date.nunique()),
        "selected_basket": list(selected),
        "selected_basket_size": len(selected),
        "asof_member_count_min": int(out.groupby("date")["asset"].nunique().min()),
        "asof_member_count_max": int(out.groupby("date")["asset"].nunique().max()),
        "all_alpha158_columns": len(alpha_cols),
        "fraction_missing_alpha_values": float(out[alpha_cols].isna().mean().mean()),
        "index_member_intervals_used": True,
        "selection_uses_only_first_date_index_membership": True,
        "missing_prices_forward_filled": False,
        "future_membership_filter_applied": False,
        "future_trade_availability_filter_applied": False,
        "note": (
            "A fixed inception-date subset of index members is tracked with historical "
            "as-of membership. This is NOT full CSI300 replication or production execution."
        ),
    }
    if (out.groupby("date")["asset"].nunique() < 3).any():
        raise ValueError("Insufficient eligible assets on one or more sessions")
    return out.sort_values(["date", "asset"]).reset_index(drop=True), quality


def load_live_sample(
    *, provider: Path, start: str, end: str,
    basket_size: int, index: str = "csi300",
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DatetimeIndex, tuple[str, ...], pd.DataFrame, dict]:
    """Fetch real stock bars and 158 causal Qlib features from a pinned local bundle."""
    import qlib
    from qlib.contrib.data.handler import Alpha158
    from qlib.data import D
    from qlib.data.dataset.handler import DataHandlerLP

    if basket_size < 4 or basket_size > 40:
        raise ValueError("basket_size must be between 4 and 40 for audited CPU study")
    provider = provider.expanduser().resolve()
    if not (provider / "calendars" / "day.txt").is_file():
        raise ValueError(f"Qlib calendar missing: {provider}")
    # Never include the artificial future-day calendar in decisions.
    qlib.init(
        provider_uri=str(provider), region="cn", kernels=1,
        expression_cache=None, dataset_cache=None, logging_level="WARNING",
    )
    start_stamp, end_stamp = pd.Timestamp(start), pd.Timestamp(end)
    if start_stamp >= end_stamp:
        raise ValueError("Study start must precede end")
    study_calendar = pd.DatetimeIndex(
        D.calendar(start_time=start, end_time=end, freq="day")
    ).normalize()
    if len(study_calendar) < 140:
        raise ValueError("Study period needs at least 140 exchange sessions")
    first_decision = study_calendar[0]
    intervals = read_member_intervals(provider / "instruments" / f"{index}.txt")
    asof = members_on(intervals, first_decision)
    # Cross-check independently with Qlib's own index-membership API.
    official = set(D.list_instruments(
        D.instruments(index), start_time=str(first_decision.date()),
        end_time=str(first_decision.date()), as_list=True,
    ))
    if asof != official:
        raise ValueError("Index-member interval parser disagrees with Qlib on inception date")
    selected = tuple(sorted(asof)[:basket_size])
    if len(selected) < basket_size:
        raise ValueError("Index has fewer inception-date members than requested")

    # Give Alpha158's 60-session operators a warmup; make all feature values
    # t-asof and all first eligible decisions >= first_decision.
    warmup_start = (first_decision - pd.Timedelta(days=160)).strftime("%Y-%m-%d")
    # Two real future sessions are required to settle the final decision
    # without filtering rows on future price availability.
    fetch_end = (end_stamp + pd.Timedelta(days=16)).strftime("%Y-%m-%d")
    calendar = pd.DatetimeIndex(
        D.calendar(start_time=warmup_start, end_time=fetch_end, freq="day")
    ).normalize()
    if len(calendar[calendar > study_calendar[-1]]) < 2:
        raise ValueError("Fewer than two post-study trading sessions for final label settlement")
    fields = ["$open", "$close", "$volume"]
    raw = D.features(selected, fields, start_time=warmup_start, end_time=fetch_end, freq="day")
    if raw.empty:
        raise ValueError("No Qlib raw prices for selected inception-date basket")
    raw = raw.reset_index().rename(
        columns={"instrument": "asset", "datetime": "date",
                 "$open": "open", "$close": "close", "$volume": "volume"}
    )
    handler = Alpha158(
        instruments=selected,
        start_time=warmup_start, end_time=fetch_end,
        fit_start_time=warmup_start, fit_end_time=start,
        infer_processors=[], learn_processors=[],
    )
    alpha = handler.fetch(col_set="feature", data_key=DataHandlerLP.DK_I)
    if alpha.empty:
        raise ValueError("Qlib Alpha158 computed no features")
    alpha = alpha.reset_index().rename(
        columns={"instrument": "asset", "datetime": "date"}
    )
    rename = {c: "alpha_" + str(c) for c in alpha.columns
              if c not in {"date", "asset"}}
    alpha = alpha.rename(columns=rename)
    source = {
        "qlib_version": qlib.__version__,
        "index": index, "basket_selection_date": str(first_decision.date()),
        "eligible_initial_members_total": len(asof),
        "selected_basket": list(selected),
        "experiment_start": str(first_decision.date()),
        "experiment_end": str(study_calendar[-1].date()),
        "warmup_start": warmup_start, "label_settlement_calendar_end": str(calendar[-1].date()),
        "raw_bar_rows": len(raw), "alpha158_rows": len(alpha),
        "qlib_default_learn_processors_disabled": True,
        "qlib_default_infer_processors_disabled": True,
        "qlib_kernels": 1,
    }
    return raw, alpha, calendar, selected, intervals, source


def run(argv: list[str] | None = None) -> dict:
    parser = argparse.ArgumentParser(
        description="CPU Qlib Alpha158 historical CSI300 sample, as-of member selection"
    )
    parser.add_argument("--provider", type=Path, required=True)
    parser.add_argument("--source-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--start", default="2024-01-02")
    parser.add_argument("--end", default="2025-12-31")
    parser.add_argument("--basket-size", type=int, default=12)
    parser.add_argument("--index", default="csi300")
    parser.add_argument("--model", choices=["factor", "ridge", "lightgbm"], default="ridge")
    parser.add_argument("--train-days", type=int, default=120)
    parser.add_argument("--validation-days", type=int, default=35)
    parser.add_argument("--test-days", type=int, default=35)
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--fee-bps", type=float, default=10.0)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args(argv)
    expected = json.loads(args.source_manifest.read_text(encoding="utf-8"))
    if not expected.get("archive_sha256") or not expected.get("release_tag"):
        raise ValueError("Pinned source release manifest lacks integrity metadata")
    if pd.Timestamp(args.end) > pd.Timestamp(expected["target_trade_date"]):
        raise ValueError("Study extends past the source's last actual trade date")
    raw, alpha, calendar, selected, intervals, source = load_live_sample(
        provider=args.provider, start=args.start, end=args.end,
        basket_size=args.basket_size, index=args.index,
    )
    panel, quality = build_calendar_panel(
        raw, alpha, calendar, selected, intervals,
        first_decision=pd.Timestamp(source["experiment_start"]),
        last_decision=pd.Timestamp(source["experiment_end"]),
    )
    features = (*BASE_FEATURES, *(c for c in panel.columns if c.startswith("alpha_")))
    cfg = WalkForwardConfig(
        min_train=args.train_days, validation_days=args.validation_days,
        test_days=args.test_days, seed=args.seed,
    )
    predictions, folds = walk_forward(
        panel, model_kind=args.model, cfg=cfg,
        feature_cols=features, allow_missing_features=True,
    )
    daily = topk_backtest(predictions, k=args.top_k, fee_bps=args.fee_bps)
    metrics = summarize(predictions, daily)
    report = {
        "kind": "REAL_HISTORICAL_DATA_EXPLORATORY_NOT_TRADEABLE",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_release": {k: expected.get(k) for k in [
            "release_tag", "target_trade_date", "archive_size_bytes",
            "archive_sha256", "investment_data_commit", "dolt_commit",
        ]},
        "source": source, "quality": quality,
        "model": args.model, "features": list(features),
        "config": {**cfg.__dict__, "top_k": args.top_k, "fee_bps": args.fee_bps},
        "folds": len(folds), "metrics": metrics,
        "return_interpretation": (
            "Exploratory price-history study, not an executable CSI300 strategy. "
            "Price adjustment factors may be revised after the fact; open-auction fills, "
            "halts, slippage, survivorship outside the inception basket and dynamic "
            "risk exposures are not fully modeled. No claim of investable alpha."
        ),
        "reproducible_data_bundle_needed": True,
        "point_in_time_index_eligibility": True,
        "point_in_time_fundamental_data_verified": False,
    }
    args.output.mkdir(parents=True, exist_ok=False)
    predictions.to_csv(args.output / "predictions.csv", index=False)
    daily.to_csv(args.output / "daily_returns.csv", index=False)
    (args.output / "folds.json").write_text(
        json.dumps(folds, indent=2), encoding="utf-8"
    )
    (args.output / "report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    summary = {
        "output": str(args.output),
        "model": args.model, "quality": quality,
        "metrics": metrics, "folds": len(folds),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return report


if __name__ == "__main__":
    run()
