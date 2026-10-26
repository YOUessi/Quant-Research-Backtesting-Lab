"""Issuer announced unrestricted new-share listing gate, independent of PnL."""
import pytest
from quant_lab.pit_listing_availability import (
    issuer_sse_new_share_listing_date,
    nominal_trade_availability,
)


def issuer_source():
    return (
        "相关日期股份类别股权登记日最后交易日除权（息）日"
        "新增无限售条件流通股份上市日现金红利发放日"
        "Ａ股2021/6/9－2021/6/102021/6/112021/6/10"
    )


def verified():
    return issuer_sse_new_share_listing_date(
        issuer_source(),record="2021-06-09",ex="2021-06-10",
    )


def corporate_event():
    return {
        "event_id":"example","symbol":"SH600276",
        "record_date":"2021-06-09","ex_date":"2021-06-10",
        "full_new_nominal_share_multiplier":1.2,
    }


def test_original_issuer_new_shares_listing_is_after_ex_day():
    p=verified()
    assert p["new_unrestricted_shares_listing_day"]=="2021-06-11"
    assert p["issuer_scheduled_cash_payment_day"]=="2021-06-10"
    assert not p["individual_shares_unrestricted_verified"]


def test_no_sell_of_bonus_shares_on_ex_day_even_though_valued():
    source=verified()
    x=nominal_trade_availability(
        corporate_event(),source,day="2021-06-10",
        original_nominal_shares=1000,
        original_shares_independently_confirmed_sellable=True,
    )
    assert x["maximum_model_sellable_old_shares_only"]=="1000"
    assert x["new_bonus_transfer_entitlement_shares"]=="200.0"
    assert not x["new_shares_tradeable"]
    assert x["status"]=="ENTITLEMENT_VALUED_BUT_NEW_SHARES_NOT_LISTED"


def test_new_listing_day_still_requires_broker_credit():
    v=nominal_trade_availability(
        corporate_event(),verified(),day="2021-06-11",
        original_nominal_shares=1000,
        original_shares_independently_confirmed_sellable=True,
    )
    assert v["status"]=="NEW_SHARES_LISTED_BUT_HOLDER_BROKER_CREDIT_UNKNOWN"
    assert not v["share_quantity_order_certified"]
    after=nominal_trade_availability(
        corporate_event(),verified(),day="2021-06-11",
        original_nominal_shares=1000,
        original_shares_independently_confirmed_sellable=True,
        broker_new_share_credit_verified=True,
    )
    assert after["maximum_model_nominal_shares_eligible_for_order"]=="1200.0"
    assert after["share_quantity_order_certified"]
    assert not after["realized_broker_trade_fill"]


def test_share_listing_unrecognized_without_original_date_table():
    x=issuer_sse_new_share_listing_date(
        "证券代码600276公司新增权益公告，但没有股份上市交易日。",
        record="2021-06-09",ex="2021-06-10")
    assert x["new_unrestricted_shares_listing_day"] is None
    event=nominal_trade_availability(
        corporate_event(),x,day="2021-06-11",
        original_nominal_shares=1000,
        original_shares_independently_confirmed_sellable=True,
    )
    assert event["status"]=="ISSUER_NEW_SHARES_LISTING_DATE_UNKNOWN"


def test_wrong_issuer_row_calendar_must_fail_closed():
    bad=issuer_source().replace("2021/6/11","2021/6/9")
    with pytest.raises(ValueError,match="contradictory"):
        issuer_sse_new_share_listing_date(
            bad,record="2021-06-09",ex="2021-06-10")


def test_no_assumption_original_nominal_shares_are_broker_sellable():
    event=nominal_trade_availability(
        corporate_event(),verified(),day="2021-06-11",
        original_nominal_shares=1000,
        original_shares_independently_confirmed_sellable=False,
        broker_new_share_credit_verified=False,
    )
    assert event["status"]=="OLD_SHARE_CREDIT_OR_RESTRICTION_NOT_VERIFIED"
    assert not event["new_shares_tradeable"]
