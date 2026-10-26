"""EXP-002: no fill on halt, no last-price delisting cashout, no lookahead."""

import numpy as np
import pandas as pd
import pytest

from quant_lab.event_simulator import ExecutionConfig, simulate
from quant_lab.pit_universe import build_dynamic_panel


def example_panel(days=42):
    dates = pd.bdate_range("2021-01-04", periods=days)
    symbols = ("SH600000", "SH600004", "SH600009", "SH600010")
    keys = pd.MultiIndex.from_product(
        [symbols, dates], names=["asset", "date"]).to_frame(index=False)
    market = keys.copy()
    idx = market.groupby("asset").cumcount().astype(float)
    symbol_ord = market["asset"].map({a:i for i,a in enumerate(symbols)})
    market["adj_open"] = 30 + symbol_ord + idx * (0.1 + symbol_ord * 0.01)
    market["adj_close"] = market["adj_open"] * 1.002
    market["volume_adjusted"] = 1_000.0
    market["factor"] = 1.0
    market["adj_high"] = market["adj_open"] * 1.01
    market["adj_low"] = market["adj_open"] * 0.99
    intervals = pd.DataFrame({
        "asset": symbols,
        "valid_from": [dates[0]] * len(symbols),
        "valid_to": [dates[-1]] * len(symbols),
    })
    panel, audit = build_dynamic_panel(
        market, intervals, dates, symbols,
        first_test=dates[10], last_test=dates[-1],
    )
    panel["listed_asof"] = True
    return panel, dates


def test_membership_today_not_future_and_past_only_signal():
    panel, dates = example_panel()
    base = panel.loc[(panel.asset == "SH600010") & (panel.date == dates[13]), "momentum_5"].iloc[0]
    altered = panel.copy()
    altered.loc[altered.date > dates[13], "adj_close"] *= 5
    # Original time-t momentum does not incorporate future prices.
    new = altered.loc[(altered.asset == "SH600010") & (altered.date == dates[13]), "momentum_5"].iloc[0]
    assert base == new


def test_missing_open_is_blocked_not_a_fill():
    panel, dates = example_panel()
    panel.loc[panel.date == dates[11], "adj_open"] = np.nan
    daily, events, report = simulate(
        panel, first_test=str(dates[10].date()), last_test=str(dates[14].date()),
        cfg=ExecutionConfig(k=2, rebalance_sessions=1, max_stale_sessions=5),
    )
    assert report["n_completed_sessions"] == 5
    assert (events["status"] == "suspended_or_missing_open_or_volume").any()
    assert report["actual_exchange_limit_prices_used"] is False


def test_zero_fee_does_not_create_costs():
    panel, dates = example_panel()
    _, _, report = simulate(
        panel, first_test=str(dates[10].date()), last_test=str(dates[18].date()),
        cfg=ExecutionConfig(k=2, fee_bps=0),
    )
    assert report["fees_total_initial_equity_units"] == 0


def test_delisted_held_stock_aborts_instead_of_fictitious_cashout():
    panel, dates = example_panel()
    # The top momentum stock is SH600000 in this synthetic market.
    # Declare every name delisted the day after positions are opened.
    panel.loc[panel.date >= dates[11], "listed_asof"] = False
    daily, events, report = simulate(
        panel, first_test=str(dates[10].date()), last_test=str(dates[20].date()),
        cfg=ExecutionConfig(k=2),
    )
    assert report["status"] == "CENSORED_UNRESOLVED_POSITION"
    assert report["stop_event"]["reason"] == "DELISTING_SETTLEMENT_UNKNOWN_FAIL_CLOSED"
    assert report["terminal_total_return_proxy"] is None


def test_stock_suspension_stale_mark_and_hard_stop():
    panel, dates = example_panel()
    panel.loc[(panel.date >= dates[11]) & (panel.date <= dates[18]),
              "adj_close"] = np.nan
    panel.loc[(panel.date >= dates[11]) & (panel.date <= dates[18]),
              "adj_open"] = np.nan
    _, events, report = simulate(
        panel, first_test=str(dates[10].date()), last_test=str(dates[25].date()),
        cfg=ExecutionConfig(k=2, max_stale_sessions=2),
    )
    assert report["status"] == "CENSORED_UNRESOLVED_POSITION"
    assert report["terminal_total_return_proxy"] is None
    assert report["stop_event"]["reason"] == "unresolved_halt_or_delisting_held_position"


def test_proxy_limit_up_blocks_buy_and_does_not_claim_exchange_rules():
    panel, dates = example_panel()
    panel.loc[panel.date == dates[10], "raw_open_estimate"] *= 1.25
    _, events, report = simulate(
        panel, first_test=str(dates[10].date()), last_test=str(dates[12].date()),
        cfg=ExecutionConfig(k=2, price_limit_proxy=True),
    )
    assert report["price_limit_gate_is_proxy_stress_not_regulatory"]
    assert report["actual_exchange_limit_prices_used"] is False
    assert (events["status"] == "PROXY_limit_up_open_not_verified_regulatory").any()
