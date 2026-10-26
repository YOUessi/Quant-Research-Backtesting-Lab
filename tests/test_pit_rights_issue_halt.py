"""Issuer rights subscription suspension chronology, no inferred auction fills."""
import pandas as pd
import pytest
from quant_lab.pit_rights_issue_halt import original_rights_halt


def calendar():
    return pd.bdate_range("2022-01-17","2022-01-28")


def good_text():
    return (
        "证券代码：600030中信证券股份有限公司A股配股公告。"
        "根据交易规则，2022年1月19日至2022年1月25日为本次A股配股缴款期，"
        "缴款期公司A股股票全天停牌；2022年1月26日为登记公司网上清算期，"
        "公司A股股票继续停牌一天；公司A股股票将于2022年1月27日开市起复牌。"
    )


def test_original_issuer_rights_dates_cover_exact_six_trading_sessions():
    d=original_rights_halt(good_text(),"SH600030",calendar=calendar())
    assert d["n_issuer_halted_exchange_sessions"]==6
    assert d["first_halted_exchange_session"]=="2022-01-19"
    assert d["first_resumed_exchange_session"]=="2022-01-27"
    assert d["issuer_halted_exchange_sessions"]==[
        "2022-01-19","2022-01-20","2022-01-21",
        "2022-01-24","2022-01-25","2022-01-26"
    ]
    assert not d["real_opening_order_fill_proven"]


def test_bond_only_pause_never_certifies_stock_halt():
    assert original_rights_halt(
        "证券代码：600030本次转债暂停转股，公司股票正常交易。",
        "SH600030",calendar=calendar()) is None


def test_missing_clearing_day_or_inverted_dates_cannot_pass():
    text=good_text().replace(
        "2022年1月26日为登记公司网上清算期",
        "2022年1月27日为登记公司网上清算期")
    with pytest.raises(ValueError,match="inconsistency"):
        original_rights_halt(text,"SH600030",calendar=calendar())
