"""PIT source evidence, primary announcement rights and execution gates."""

import math

import pandas as pd
import pytest

from quant_lab.pit_events import (
    normalise_eastmoney_dividends, normalise_cninfo_announcements,
    attach_official_announcement, first_usable_exchange_session,
    implementation_known_on, settle_nominal_action,
)
from quant_lab.pit_tradeability import (
    TradeEvidence, audit_execution, normalise_tushare_limits,
    normalise_tushare_suspensions,
)
from quant_lab.pit_primary_audit import (
    DOCUMENTS, verify_pdf_text, verify_official_suspension_with_bar_calendar,
)


def stock_action(**kw):
    base = {
        "SECUCODE": "600000.SH",
        "PLAN_NOTICE_DATE": "2022-04-28 00:00:00",
        "NOTICE_DATE": "2022-07-13 00:00:00",
        "EQUITY_RECORD_DATE": "2022-07-20 00:00:00",
        "EX_DIVIDEND_DATE": "2022-07-21 00:00:00",
        "ASSIGN_PROGRESS": "实施分配",
        "PRETAX_BONUS_RMB": 4.1,  # per ten shares
        "BONUS_RATIO": 0, "IT_RATIO": 0,
    }
    base.update(kw)
    return base


def test_date_only_announcement_does_not_leak_preliminary_or_same_day():
    events, excluded = normalise_eastmoney_dividends(
        [stock_action()], first_ex="2021-01-01", last_ex="2022-12-31")
    assert not excluded
    assert len(events) == 1
    e = events[0]
    assert e["implementation_announcement_date"] == "2022-07-13"
    assert e["plan_announcement_date"] == "2022-04-28"
    assert e["cash_per_share_pre_tax"] == pytest.approx(.41)
    assert not implementation_known_on(e, "2022-07-12")
    assert not implementation_known_on(e, "2022-07-13")
    assert implementation_known_on(e, "2022-07-14")
    cal = pd.to_datetime(["2022-07-13", "2022-07-14", "2022-07-15"])
    assert first_usable_exchange_session("2022-07-13", cal) == "2022-07-14"


def test_missing_implementation_and_post_ex_announcement_fail():
    bad = [
        stock_action(NOTICE_DATE="2022-07-22"),
        stock_action(ASSIGN_PROGRESS="预案"),
        stock_action(EQUITY_RECORD_DATE="2022-08-01"),
    ]
    good, excluded = normalise_eastmoney_dividends(
        bad, first_ex="2021-01-01", last_ex="2022-12-31")
    assert not good
    assert len(excluded) == 3


def test_official_index_metadata_only_not_equivalent_to_pdf_amount_audit():
    idx = normalise_cninfo_announcements([{
        "secCode": "600000",
        "announcementTime": 1657641600000,
        "announcementTitle": "2021年度分红派息实施公告",
        "announcementId": "1214014565",
        "adjunctUrl": "finalpage/2022-07-13/1214014565.PDF",
    }])
    event, _ = normalise_eastmoney_dividends(
        [stock_action()],first_ex="2022-01-01",last_ex="2022-12-31")
    merged = attach_official_announcement(event, idx)[0]
    assert merged["official_announcement_metadata_matches"] == 1
    assert merged["amount_verified_against_official_pdf"] is False


def test_nominal_entitlements_are_not_adjusted_price_returns():
    event = normalise_eastmoney_dividends(
        [stock_action()],first_ex="2022-01-01",
        last_ex="2022-12-31")[0][0]
    payout = settle_nominal_action(shares_at_record_close=1000, event=event)
    assert payout["dividend_receivable_pre_tax"] == pytest.approx(410)
    assert payout["shares_ex_date_nominal"] == pytest.approx(1000)
    assert payout["payment_posted"] is False
    assert payout["cash_tax_and_broker_entitlement_verification_pending"] is True
    with pytest.raises(ValueError, match="nominal"):
        settle_nominal_action(
            shares_at_record_close=1000,
            event={**event,"nominal_shares_and_currency_only":False},
        )


def test_transfer_shares_are_preregistered_and_per_ten_not_per_share():
    event = normalise_eastmoney_dividends(
        [stock_action(BONUS_RATIO=1,IT_RATIO=2)],
        first_ex="2022-01-01",last_ex="2022-12-31",
    )[0][0]
    result = settle_nominal_action(shares_at_record_close=100, event=event)
    assert result["shares_ex_date_nominal"] == pytest.approx(130)
    assert result["dividend_receivable_pre_tax"] == pytest.approx(41)


def test_trade_without_official_limits_remains_uncertified():
    x = TradeEvidence(
        symbol="SH600000",trade_date="2022-07-21",
        exchange_listed_asof=True,bar_open_raw=7.8,
        bar_volume_positive=True,
    )
    result = audit_execution(x,side="buy",intended_order_shares=100,
                             decision_day="2022-07-20")
    assert result["status"] == "UNCERTIFIED_NO_DAILY_OFFICIAL_LIMIT_LEVELS"
    assert not result["is_verified_broker_fill"]
    assert not result["would_simulator_fill"]
    with pytest.raises(ValueError,match="prior/same"):
        audit_execution(x,side="buy",intended_order_shares=100,
                        decision_day="2022-07-21")


def test_halt_and_actual_limit_gates():
    base = dict(
        symbol="SH600340",trade_date="2021-01-29",
        exchange_listed_asof=True,
        bar_open_raw=10,bar_volume_positive=True,
    )
    halted = audit_execution(
        TradeEvidence(**base,full_day_suspension=True,
                      official_halt_source="issuer_original_pdf_and_exchange_calendar"),
        side="buy",intended_order_shares=100,decision_day="2021-01-28",
    )
    assert halted["status"] == "BLOCKED_OFFICIALLY_SUSPENDED"
    limit = audit_execution(
        TradeEvidence(**base,official_up_limit_raw=10,official_down_limit_raw=8,
                      official_limits_source="TUSHARE_STK_LIMIT_AUTHENTICATED",
                      source_trading_status="NORMAL"),
        side="buy",intended_order_shares=100,decision_day="2021-01-28",
    )
    assert limit["status"] == "BLOCKED_CONSERVATIVE_BUY_AT_PRICE_LIMIT"


def test_tushare_normalizers_enforce_dates_and_prices():
    limits = normalise_tushare_limits([{
        "ts_code":"600000.SH","trade_date":"20220721",
        "up_limit":10.00,"down_limit":8.20,
    }])
    assert limits.iloc[0].symbol == "SH600000"
    with pytest.raises(ValueError,match="below"):
        normalise_tushare_limits([{
            "ts_code":"600000.SH","trade_date":"20220721",
            "up_limit":8,"down_limit":9,
        }])
    halts = normalise_tushare_suspensions([{
        "ts_code":"600340.SH","trade_date":"20210129",
        "suspend_type":"S","suspend_timing":"",
    }])
    assert bool(halts.iloc[0]["full_day_suspension"])


def test_pinned_primary_pdf_text_check_no_network():
    docs = {d["key"]:d for d in DOCUMENTS}
    text = (
        "证券代码：600000 上海浦东发展银行股份有限公司"
        "每股现金红利人民币0.41元（含税）"
        "Ａ股2022/7/20－2022/7/212022/7/21"
    )
    result = verify_pdf_text(docs["SH600000_dividend_20220721"],text)
    assert result["cash_per_nominal_share_pre_tax_pdf_confirmed"] == pytest.approx(.41)
    with pytest.raises(ValueError,match="amount"):
        verify_pdf_text(docs["SH600000_dividend_20220721"],
                        text.replace("0.41元","0.52元"))


def test_historical_exchange_halt_never_has_daily_market_bar():
    cal=pd.bdate_range("2021-01-25",periods=25)
    actual=pd.DataFrame({
        "date":["2021-01-28","2021-02-19"],
        "open_raw":[9.54,8.51],"volume_lots":[475631,128401],
    })
    x=verify_official_suspension_with_bar_calendar(
        suspension_from="2021-01-29",resume_from="2021-02-19",
        bars=actual,exchange_calendar=cal,
    )
    assert x["independent_daily_bar_during_halt"] == 0
    bad=pd.concat([actual,pd.DataFrame({
        "date":["2021-02-03"],"open_raw":[8.8],"volume_lots":[1000],
    })],ignore_index=True)
    with pytest.raises(ValueError,match="during officially halted"):
        verify_official_suspension_with_bar_calendar(
            suspension_from="2021-01-29",resume_from="2021-02-19",
            bars=bad,exchange_calendar=cal,
        )
