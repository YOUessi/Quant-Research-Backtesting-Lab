"""EXP-002: full historical-membership Qlib panel with causal daily signals.

This is a point-in-time *index membership* reconstruction, NOT a certified
point-in-time corporate-action price store. No future price is used to choose
which tickers exist at close(t). The adjusted price series is explicitly a
snapshot of the 2026-10-25 community source release.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from .real_qlib import read_member_intervals


SOURCE_SHA256 = "0a2974da97b4737e503ecddeea8bb3b2179e0e16ea0fb19fa373ff14155bf315"
FIELD_NAMES = ["$open", "$close", "$volume", "$factor", "$high", "$low"]
FIELD_RENAME = {"$open": "adj_open", "$close": "adj_close",
                "$volume": "volume_adjusted", "$factor": "factor",
                "$high": "adj_high", "$low": "adj_low"}


def asset_membership_mask(frame: pd.DataFrame, intervals: pd.DataFrame) -> pd.Series:
    """Membership test uses each ticker's own historical intervals only."""
    if frame.duplicated(["asset", "date"]).any():
        raise ValueError("Duplicate asset/date observations")
    date = pd.to_datetime(frame["date"])
    result = np.zeros(len(frame), dtype=bool)
    groups = frame.groupby("asset", sort=False).indices
    mapped = {ticker: group for ticker, group in intervals.groupby("asset", sort=False)}
    for ticker, positions in groups.items():
        groups_for_name = mapped.get(ticker)
        if groups_for_name is None:
            continue
        d = date.iloc[positions].to_numpy(dtype="datetime64[ns]")
        yes = np.zeros(len(positions), dtype=bool)
        for interval in groups_for_name.itertuples(index=False):
            yes |= ((d >= np.datetime64(interval.valid_from))
                    & (d <= np.datetime64(interval.valid_to)))
        result[positions] = yes
    return pd.Series(result, index=frame.index)


def _clean_price_columns(panel: pd.DataFrame) -> pd.DataFrame:
    for name in FIELD_RENAME.values():
        panel[name] = pd.to_numeric(panel[name], errors="coerce")
        panel.loc[~np.isfinite(panel[name]) | (panel[name] <= 0), name] = np.nan
    # No price interpolation, forward fill, or back fill.
    panel["raw_open_estimate"] = panel["adj_open"] / panel["factor"]
    panel["raw_close_estimate"] = panel["adj_close"] / panel["factor"]
    return panel


def build_dynamic_panel(
    observed: pd.DataFrame,
    intervals: pd.DataFrame,
    calendar: pd.DatetimeIndex,
    symbols: tuple[str, ...],
    *,
    first_test: str,
    last_test: str,
) -> tuple[pd.DataFrame, dict]:
    """Reindex globally and build close(t)-available momentum without future bars.

    The *same* full symbol calendar is kept for missing/trading-halt audit.
    Indicator readiness requires the last SIX consecutive closes to exist;
    NaNs never get filled.
    """
    if not symbols:
        raise ValueError("Empty historical-universe list")
    if not calendar.is_monotonic_increasing or not calendar.is_unique:
        raise ValueError("Global Qlib exchange calendar must be sorted and unique")
    calendar = pd.DatetimeIndex(calendar).normalize()
    keys = pd.MultiIndex.from_product(
        [symbols, calendar], names=["asset", "date"]
    ).to_frame(index=False)
    bars = observed.copy()
    bars["date"] = pd.to_datetime(bars["date"]).dt.normalize()
    bars["asset"] = bars["asset"].astype(str)
    if bars.duplicated(["asset", "date"]).any():
        raise ValueError("Duplicated ticker/calendar bar")
    for required in ["asset", "date", *FIELD_RENAME.values()]:
        if required not in bars.columns:
            raise ValueError("Missing Qlib source field "+required)
    panel = keys.merge(bars, how="left", on=["asset", "date"],
                       validate="one_to_one", sort=False)
    panel = _clean_price_columns(panel)
    panel["index_member_asof"] = asset_membership_mask(panel, intervals)
    group = panel.groupby("asset", sort=False)
    close = group["adj_close"]
    panel["momentum_5"] = close.pct_change(periods=5, fill_method=None)
    # If any of six observations needed for the rolling signal was missing,
    # the momentum signal is not valid. This excludes on *known*, past bars.
    history_six = group["adj_close"].transform(
        lambda x: x.rolling(6, min_periods=6).count()
    )
    panel["momentum_5"] = panel["momentum_5"].where(history_six == 6)
    rawclose = group["raw_close_estimate"].shift(1)
    panel["prior_raw_close"] = rawclose
    fprev = group["factor"].shift(1)
    panel["factor_step_ratio"] = panel["factor"] / fprev
    panel["known_close_t"] = (
        panel["adj_close"].notna()
        & panel["volume_adjusted"].gt(0)
        & panel["factor"].gt(0)
    )
    panel["signal_eligible"] = (
        panel["index_member_asof"]
        & panel["known_close_t"]
        & np.isfinite(panel["momentum_5"])
    )
    first, last = pd.Timestamp(first_test), pd.Timestamp(last_test)
    period = panel["date"].between(first, last)
    universe_by_day = panel.loc[period].groupby("date")["index_member_asof"].sum()
    ready_by_day = panel.loc[period].groupby("date")["signal_eligible"].sum()
    if universe_by_day.empty or ready_by_day.empty:
        raise ValueError("No evaluation dates")
    if universe_by_day.min() < 10:
        raise ValueError("Historical CSI300 member count is unexpectedly small")
    if (ready_by_day < 10).any():
        raise ValueError("At least one evaluation day lacks 10 signal-eligible assets")
    mean_factor_shocks = (
        panel.loc[period, "factor_step_ratio"].sub(1).abs().gt(0.01).sum()
    )
    # Missing prices on an index member day are recorded, NOT removed by a
    # future trading-availability filter.
    audit = {
        "n_ever_index_members": len(symbols),
        "n_exchange_calendar_dates": len(calendar),
        "n_global_asset_date_slots": len(panel),
        "n_observed_close_bars": int(panel["adj_close"].notna().sum()),
        "n_missing_close_slots": int(panel["adj_close"].isna().sum()),
        "evaluation_sessions": int(len(universe_by_day)),
        "hist_member_count_min": int(universe_by_day.min()),
        "hist_member_count_max": int(universe_by_day.max()),
        "hist_member_count_median": float(universe_by_day.median()),
        "signal_eligible_min": int(ready_by_day.min()),
        "signal_eligible_max": int(ready_by_day.max()),
        "member_day_missing_or_invalid_close": int(
            (period & panel["index_member_asof"] & ~panel["known_close_t"]).sum()
        ),
        "factor_step_gt_1pct_all_symbols_count": int(mean_factor_shocks),
        "candidate_filter_uses_next_session_price": False,
        "suspension_price_filled": False,
        "corporate_action_adjustment_point_in_time_certified": False,
        "factor_assumption": (
            "Publisher-adjusted data snapshot; adj/factor estimates raw price "
            "but cannot establish release-time adjustment-factor history. "
            "No corporate-action cash entitlements are available."
        ),
    }
    return panel, audit


def load_dynamic_data(
    *, provider: Path, source_manifest: Path,
    first_test: str, last_test: str,
    warmup: str = "2020-06-01", index: str = "csi300",
) -> tuple[pd.DataFrame, dict]:
    """Load the union of as-of index members, without post-hoc survivorship."""
    import qlib
    from qlib.data import D

    release = json.loads(source_manifest.read_text(encoding="utf-8"))
    expected = "sha256:"+SOURCE_SHA256
    if release.get("archive_sha256") != expected:
        raise ValueError("Dataset SHA256 is not the pre-registered source release")
    if pd.Timestamp(last_test) > pd.Timestamp(release["target_trade_date"]):
        raise ValueError("Requested period extends beyond verified source end")
    provider = provider.expanduser().resolve()
    qlib.init(provider_uri=str(provider), region="cn", kernels=1,
              expression_cache=None, dataset_cache=None,
              logging_level="WARNING")
    study = pd.DatetimeIndex(D.calendar(
        start_time=first_test, end_time=last_test, freq="day")).normalize()
    if len(study) < 100:
        raise ValueError("Independent evaluation horizon unexpectedly short")
    # Warmup is chosen before holdout outcomes and is not optimized on returns.
    calendar = pd.DatetimeIndex(D.calendar(
        start_time=warmup, end_time=last_test, freq="day")).normalize()
    if len(calendar) <= len(study)+6:
        raise ValueError("Insufficient price history to form causal factor")
    intervals = read_member_intervals(provider/"instruments"/f"{index}.txt")
    active_interval = (
        (intervals["valid_to"] >= calendar[0])
        & (intervals["valid_from"] <= calendar[-1])
    )
    relevant = intervals.loc[active_interval].copy()
    symbols = tuple(sorted(relevant.asset.unique()))
    if len(symbols) < 300:
        raise ValueError(f"Historical membership union should be >=300, got {len(symbols)}")
    # Independent member count cross-check at key dates, no prices used.
    member_comparisons = {}
    for d in (study[0], study[len(study)//2], study[-1]):
        dt = str(pd.Timestamp(d).date())
        calculated = set(relevant.loc[
            (relevant.valid_from <= d) & (d <= relevant.valid_to), "asset"
        ])
        official = set(D.list_instruments(
            D.instruments(index), start_time=dt, end_time=dt, as_list=True))
        if calculated != official:
            raise ValueError(f"Historical membership and Qlib API disagree at {dt}")
        member_comparisons[dt] = len(official)
    bars = D.features(symbols, FIELD_NAMES, start_time=warmup,
                      end_time=last_test, freq="day")
    if bars.empty:
        raise ValueError("No historical OHLCVF bars from Qlib")
    bars = bars.reset_index().rename(columns={
        "instrument": "asset", "datetime": "date", **FIELD_RENAME})
    panel, audit = build_dynamic_panel(
        bars, relevant, calendar, symbols,
        first_test=first_test, last_test=last_test,
    )
    # Deletion from CSI300 is not a stock delisting. Load an independent
    # historically as-of all-listed register to classify actual delistings.
    all_intervals = read_member_intervals(provider/"instruments"/"all.txt")
    panel["listed_asof"] = asset_membership_mask(panel, all_intervals)
    active_period = panel["date"].between(study[0], study[-1])
    delist_events = all_intervals.loc[
        all_intervals["valid_to"].between(study[0], study[-1])
        & all_intervals["asset"].isin(symbols), ["asset", "valid_to"]
    ].drop_duplicates()
    audit["listing_intervals_present"] = True
    audit["n_symbols_with_listing_end_in_window"] = int(delist_events.asset.nunique())
    audit["n_index_member_but_not_listed_asof_day"] = int((
        active_period & panel["index_member_asof"] & ~panel["listed_asof"]
    ).sum())
    audit["listing_end_dates_are_not_corporate_action_cash_settlements"] = True
    audit.update({
        "index": index, "evaluation_start": first_test,
        "evaluation_end": last_test, "warmup_start": warmup,
        "historical_member_count_verified_at": member_comparisons,
        "source_release_tag": release["release_tag"],
        "source_sha256": expected,
        "source_last_trading_date": release["target_trade_date"],
        "qlib_version": qlib.__version__,
        "input_raw_bar_rows": len(bars),
        "field_names": list(FIELD_RENAME.values()),
        "point_in_time_index_membership_verified": True,
    })
    return panel, audit


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--provider", type=Path, required=True)
    p.add_argument("--source-manifest", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--first-test", default="2021-01-04")
    p.add_argument("--last-test", default="2022-12-30")
    p.add_argument("--warmup", default="2020-06-01")
    args = p.parse_args(argv)
    panel, audit = load_dynamic_data(
        provider=args.provider, source_manifest=args.source_manifest,
        first_test=args.first_test, last_test=args.last_test,
        warmup=args.warmup,
    )
    args.output.mkdir(parents=True, exist_ok=False)
    panel.to_parquet(args.output/"historical_panel.parquet", index=False)
    (args.output/"quality_audit.json").write_text(
        json.dumps(audit, indent=2, ensure_ascii=False)+"\n", encoding="utf-8")
    print(json.dumps(audit, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
