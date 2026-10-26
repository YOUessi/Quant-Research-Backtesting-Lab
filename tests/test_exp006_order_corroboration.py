"""Issuer-halt trade attempt overlays never upgrade assumed broker fills."""
import pandas as pd
import pytest

from quant_lab.pit_order_corroboration import corroborate_frozen_attempts


def test_existing_idealized_halt_fill_flagged_not_hidden():
    attempts=pd.DataFrame([
        {"date":"2022-01-20","signal_date":"2022-01-19","asset":"SH600030",
         "side":"buy","gross_notional":.3,
         "status":"idealized_next_open_fill_unverified"},
        {"date":"2022-01-20","signal_date":"2022-01-19","asset":"SH600030",
         "side":"sell","gross_notional":.2,
         "status":"suspended_or_missing_open_or_volume"},
        {"date":"2022-01-28","signal_date":"2022-01-27","asset":"SH600030",
         "side":"buy","gross_notional":.1,
         "status":"idealized_next_open_fill_unverified"},
    ])
    issuer={("SH600030","2022-01-20"):{
        "source_pdf_sha256":"a"*64,
        "source_url":"https://static.cninfo.com.cn/finalpage/2022-01-14/p.PDF",
    }}
    audit,rows=corroborate_frozen_attempts(attempts,issuer)
    assert audit["issuer_halt_contradictory_assumed_fills"]==1
    assert audit["issuer_halt_correlated_blocked_orders"]==1
    assert audit["uncertified_assumed_fills_no_auction_limits"]==1
    assert audit["requires_model_backtest_revision_if_contradiction"]
    assert not audit["all_realized_broker_fills_certified"]
    assert not audit["frozen_strategy_returns_recomputed_or_reoptimized"]


def test_missing_previous_signal_day_is_rejected():
    frame=pd.DataFrame([{
        "date":"2022-01-20","signal_date":"2022-01-20","asset":"SH600030",
        "side":"buy","gross_notional":.5,
        "status":"idealized_next_open_fill_unverified",
    }])
    with pytest.raises(ValueError,match="future signal"):
        corroborate_frozen_attempts(frame,{})
