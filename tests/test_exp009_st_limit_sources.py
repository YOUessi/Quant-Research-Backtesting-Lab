"""Historical source-confirmed ST percentage vs hypothetical opening fill tests."""
from decimal import Decimal

import pandas as pd
import pytest

from quant_lab.pit_st_limit_exploratory import (
    classify_auction_hypothesis, derived_band, verify_original_st_rule,
)


def market_bars():
    return pd.DataFrame([
        {"date":"2022-04-29","open_raw":2.95,"high_raw":3.23,"low_raw":2.94,
         "close_raw":3.23,"volume_lots":451916},
        {"date":"2022-05-06","open_raw":3.07,"high_raw":3.07,"low_raw":3.07,
         "close_raw":3.07,"volume_lots":16452},
        {"date":"2022-05-09","open_raw":2.92,"high_raw":2.92,"low_raw":2.92,
         "close_raw":2.92,"volume_lots":35449},
        {"date":"2022-05-10","open_raw":2.77,"high_raw":2.77,"low_raw":2.77,
         "close_raw":2.77,"volume_lots":67116},
    ])


def calendar():
    return ["2022-04-29","2022-05-05","2022-05-06","2022-05-09","2022-05-10"]


def test_original_2022_issuer_st_and_resume_wording_required():
    document=(
        "证券代码：002024 苏宁易购关于被实施其他风险警示暨停复牌公告"
        "公司股票交易2022年5月5日开市起停牌一天，"
        "并于2022年5月6日开市起复牌；"
        "被实施其他风险警示后，股票简称为“ST易购”，"
        "股票交易的日涨跌幅限制为5%。"
    )
    check=verify_original_st_rule(document)
    assert check["risk_warning_effective_day"]=="2022-05-06"
    assert check["source_full_day_halt"]=="2022-05-05"
    assert not check["actual_security_day_exchange_limit_levels_present_in_original_pdf"]
    with pytest.raises(ValueError,match="5% rule"):
        verify_original_st_rule(document.replace("5%","10%"))


def test_decimal_rounding_and_pinned_three_one_price_days():
    assert derived_band(Decimal("3.23"))==(Decimal("3.39"), Decimal("3.07"))
    assert derived_band(Decimal("3.07"))==(Decimal("3.22"), Decimal("2.92"))
    assert derived_band(Decimal("2.92"))==(Decimal("3.07"), Decimal("2.77"))
    records=classify_auction_hypothesis(market_bars(),calendar=calendar())
    assert [r["trade_day"] for r in records]==[
        "2022-05-06","2022-05-09","2022-05-10"]
    assert records[0]["derived_limit_down_price_NOT_OFFICIAL"]=="3.07"
    assert records[0]["observed_positive_daily_volume_lots"]=="16452.0"
    assert all(r["historical_one_price_down_at_derived_issuer_band"] for r in records)
    assert all(not r["real_broker_execution_receipt"] for r in records)
    assert all("DO_NOT_ASSUME" in r["conservative_hypothetical_sell_queue_status"] for r in records)


def test_volume_is_positive_but_not_auction_sell_proof():
    frame=market_bars()
    assert frame.loc[frame.date=="2022-05-06","volume_lots"].iloc[0]>0
    records=classify_auction_hypothesis(frame,calendar=calendar())
    assert not records[0]["hypothetical_buy_fill_auction_depth_certified"]
    assert records[0]["conservative_hypothetical_sell_queue_status"]==(
        "DO_NOT_ASSUME_NEXT_OPEN_SELL_FILL_QUEUE_UNVERIFIED")


def test_historical_day_gap_must_be_original_issuer_documented():
    with pytest.raises(ValueError,match="Publisher confirmed suspension"):
        classify_auction_hypothesis(
            market_bars(),calendar=["2022-04-29","2022-05-06","2022-05-09","2022-05-10"])


def test_invented_tradable_market_bar_on_halt_day_rejected():
    fake=market_bars()
    fake.loc[len(fake)]={"date":"2022-05-05","open_raw":3.24,
                         "high_raw":3.25,"low_raw":3.23,
                         "close_raw":3.24,"volume_lots":100000}
    with pytest.raises(ValueError,match="Publisher confirmed suspension"):
        classify_auction_hypothesis(fake,calendar=calendar())


def test_wrong_5pct_limit_day_or_false_high_low_cannot_pass():
    frame=market_bars()
    frame.loc[frame.date=="2022-05-06","low_raw"]=2.99
    with pytest.raises(ValueError,match="one-price"):
        classify_auction_hypothesis(frame,calendar=calendar())


def test_no_missing_or_infinite_daily_prices():
    frame=market_bars()
    frame.loc[frame.date=="2022-05-09","close_raw"]=float("nan")
    with pytest.raises(ValueError,match="Invalid positive"):
        classify_auction_hypothesis(frame,calendar=calendar())


def test_halt_requires_real_positive_daily_volume_even_at_price_limit():
    frame=market_bars()
    frame.loc[frame.date=="2022-05-06","volume_lots"]=0
    with pytest.raises(ValueError,match="Invalid positive"):
        classify_auction_hypothesis(frame,calendar=calendar())
