"""Index membership, calendar reindexing, and no future-tradability filtering."""

import numpy as np
import pandas as pd
import pytest

from quant_lab.real_qlib import (
    build_calendar_panel,
    members_on,
    membership_mask,
    read_member_intervals,
)


def _dataset():
    dates = pd.bdate_range("2024-01-02", periods=85)
    symbols = ("SH600000", "SH600001", "SZ000001", "SZ000002")
    grid = pd.MultiIndex.from_product([symbols, dates], names=["asset", "date"])
    raw = grid.to_frame(index=False)
    raw["open"] = 20.0 + 0.07 * raw.groupby("asset").cumcount()
    raw["close"] = raw["open"] * 1.002
    raw["volume"] = 1000.0
    alpha = raw[["date", "asset"]].copy()
    for i in range(140):
        alpha[f"alpha_TEST_{i}"] = 0.1
    intervals = pd.DataFrame(
        {"asset": symbols, "valid_from": [dates[0]] * 4, "valid_to": [dates[-1]] * 4}
    )
    return dates, symbols, raw, alpha, intervals


def test_historical_membership_is_asof_not_today(tmp_path):
    path = tmp_path / "csi300.txt"
    path.write_text(
        "SH600000\t2024-01-02\t2024-03-01\n"
        "SZ000001\t2024-02-01\t2024-12-31\n", encoding="utf-8"
    )
    table = read_member_intervals(path)
    assert members_on(table, "2024-01-31") == {"SH600000"}
    assert members_on(table, "2024-02-20") == {"SH600000", "SZ000001"}
    assert members_on(table, "2024-03-02") == {"SZ000001"}
    observations = pd.DataFrame({
        "date": pd.to_datetime(["2024-01-15", "2024-01-15", "2024-03-03"]),
        "asset": ["SH600000", "SZ000001", "SH600000"],
    })
    assert membership_mask(observations, table).tolist() == [True, False, False]


def test_calendar_panel_is_causal_and_keeps_open_open_target():
    dates, symbols, raw, alpha, intervals = _dataset()
    panel, audit = build_calendar_panel(
        raw, alpha, dates, symbols, intervals,
        first_decision=dates[35], last_decision=dates[-4],
    )
    assert audit["future_availability_invalid"] == 0
    assert audit["all_alpha158_columns"] == 140
    row = panel[(panel.asset == symbols[0]) & (panel.date == dates[45])].iloc[0]
    assert row.execution_date == dates[46]
    assert row.exit_date == dates[47]
    o46 = raw[(raw.asset == symbols[0]) & (raw.date == dates[46])].open.iloc[0]
    o47 = raw[(raw.asset == symbols[0]) & (raw.date == dates[47])].open.iloc[0]
    assert row.target == pytest.approx(o47 / o46 - 1)


def test_future_missing_price_aborts_instead_of_lookahead_deletion():
    dates, symbols, raw, alpha, intervals = _dataset()
    # The candidate is live and has complete observed history on day 43.
    # Opening price on day 45 is unexpectedly absent. A naive shift/dropna
    # would remove day 43 with *knowledge of day 45*.
    raw.loc[
        (raw.asset == symbols[0]) & (raw.date == dates[45]), "open"
    ] = np.nan
    with pytest.raises(ValueError, match="look-ahead|future-availability"):
        build_calendar_panel(
            raw, alpha, dates, symbols, intervals,
            first_decision=dates[35], last_decision=dates[-4],
        )


def test_no_price_forward_fill_for_halted_asset():
    dates, symbols, raw, alpha, intervals = _dataset()
    raw.loc[
        (raw.asset == symbols[0]) & (raw.date == dates[45]), "close"
    ] = np.nan
    panel, _ = build_calendar_panel(
        raw, alpha, dates, symbols, intervals,
        first_decision=dates[35], last_decision=dates[-4],
    )
    assert not ((panel.asset == symbols[0]) & (panel.date == dates[45])).any()
    # Rolling factors also become unavailable after a missing close.
    assert not ((panel.asset == symbols[0]) & (panel.date == dates[46])).any()
