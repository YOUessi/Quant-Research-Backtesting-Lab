"""Issuer cash-ledger identity, no-lookahead and nominal accounting regression."""
import pytest
import pandas as pd

from quant_lab.pit_action_book import create_event, canonicalize
from quant_lab.pit_nominal_book import simulate_nominal_right


def event(**kwargs):
    v=dict(symbol="SH600000",announced="2022-07-13",
           record="2022-07-20",ex="2022-07-21",
           pay="2022-07-22",cash=.41,
           sha="a"*64,
           url="https://static.cninfo.com.cn/finalpage/2022-07-13/1214014565.PDF",
           grade="ISSUER_PDF_CASH_VERIFIED")
    v.update(kwargs)
    return create_event(**v)


def with_calendar(*events):
    calendar=pd.bdate_range("2022-07-01","2022-08-15")
    return canonicalize(list(events),calendar=calendar)


def test_known_only_after_announcement_and_duplicate_booked_once():
    x=event()
    y=event(sha="b"*64)
    r=with_calendar(x,y)
    assert r["unique_cash_events"]==1
    assert r["duplicate_groups_booked_once"]==1
    assert r["events"][0]["earliest_usable_exchange_day"]=="2022-07-14"
    assert len(r["events"][0]["all_pdf_sha256s"])==2


def test_same_event_with_conflicting_cash_is_held_not_counted_twice():
    r=with_calendar(event(),event(cash=.43,sha="b"*64))
    assert r["unique_cash_events"]==0
    assert r["contradictory_identities_held"]==1
    assert r["held"][0]["reason"]=="CONFLICTING_PAYOUT_HOLD"


def test_late_announcement_and_payment_before_ex_is_rejected():
    with pytest.raises(ValueError,match="chronology"):
        event(announced="2022-07-20")
    with pytest.raises(ValueError,match="chronology"):
        event(pay="2022-07-19")


def raw_bars():
    return pd.DataFrame({
        "date":["2022-07-20","2022-07-21","2022-07-22"],
        "close_raw":[10.0,9.59,9.59],
    })


def test_ex_date_cash_entitlement_not_double_counted_before_ex():
    e=with_calendar(event())["events"][0]
    b=simulate_nominal_right(e,raw_bars(),
                             original_shares=1000,share_bonus_ratio=0.0,
                             share_bonus_terms_officially_verified=True)
    assert b["record_close_nominal_mark"]=="10000.0"
    assert b["ex_close_including_gross_receivable_scenario"]=="10000.00"
    assert b["ex_close_total_mark_change"]==pytest.approx(0.0)
    rec,ex,pay=b["records"]
    assert rec["pretax_receivable"]=="0"
    assert ex["pretax_receivable"]=="410.00"
    assert pay["pretax_receivable"]=="0"
    assert pay["cash_schedule_only"]=="410.00"
    assert pay["equity_gross_scenario"]==ex["equity_gross_scenario"]
    assert b["cash_payment_broker_confirmed"] is False
    assert b["Qlib_adjusted_total_return_price_used"] is False


def test_stock_bonus_nominal_share_quantity_on_ex_date():
    e=with_calendar(event(cash=.2))["events"][0]
    frame=pd.DataFrame({
        "date":["2022-07-20","2022-07-21","2022-07-22"],
        "close_raw":[10.0,8.0,8.0],
    })
    v=simulate_nominal_right(e,frame,original_shares=1000,
         share_bonus_ratio=.2,share_bonus_terms_officially_verified=True)
    assert float(v["records"][1]["nominal_shares"])==pytest.approx(1200)
    assert float(v["records"][1]["pretax_receivable"])==pytest.approx(200)


def test_unknown_stock_bonus_is_scenario_only_and_requires_disclosure():
    e=with_calendar(event())["events"][0]
    r=simulate_nominal_right(e,raw_bars())
    assert r["corporate_share_terms_status"]=="CASH_ONLY_ASSUMPTION_STOCK_BONUS_UNVERIFIED"
    assert r["completed_actual_portfolio_revaluation"] is False
    with pytest.raises(ValueError,match="unaudited"):
        simulate_nominal_right(e,raw_bars(),share_bonus_ratio=.1)


def test_adjusted_price_and_missing_ex_close_fail_closed():
    e=with_calendar(event())["events"][0]
    a=raw_bars()
    a["close_adjusted"]=a["close_raw"]
    with pytest.raises(ValueError,match="Adjusted"):
        simulate_nominal_right(e,a)
    with pytest.raises(ValueError,match="ex-date"):
        simulate_nominal_right(e,raw_bars().query('date != "2022-07-21"'))


def test_no_actual_broker_payment_can_be_asserted():
    e=with_calendar(event())["events"][0]
    with pytest.raises(ValueError,match="Broker"):
        simulate_nominal_right(e,raw_bars(),broker_payment_verified=True)
