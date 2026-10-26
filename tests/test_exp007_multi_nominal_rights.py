"""Nominal mark with original bonus shares, capital transfer and gross cash."""
import pandas as pd
import pytest

from quant_lab.pit_multi_nominal_rights import audit_single


def event():
    return {
        "event_id":"e","symbol":"SH600276","record_date":"2021-06-09",
        "ex_date":"2021-06-10","scheduled_cash_payment_day":"2021-06-11",
        "gross_cash_per_old_nominal_share":.2,
        "issuer_original_pdf_sha256":"a"*64,
        "issuer_original_pdf_url":"https://static.cninfo.com.cn/finalpage/original.PDF",
        "earliest_usable_exchange_day":"2021-06-07",
        "full_new_nominal_share_multiplier":1.2,
        "bonus_shares_per_old_share":.2,
        "capital_transfer_shares_per_old_share":0,
        "rights_evidence":{"bonus":"EXPLICIT_PER_SHARE", "transfer":"BALANCE_DERIVED_ZERO"},
    }


def bars():
    return pd.DataFrame([
        {"date":"2021-06-09","open_raw":90,"close_raw":90,
         "volume_lots":300,"amount_currency":100_000},
        {"date":"2021-06-10","open_raw":74,"close_raw":75,
         "volume_lots":400,"amount_currency":120_000},
        {"date":"2021-06-11","open_raw":76,"close_raw":76,
         "volume_lots":420,"amount_currency":131_000},
    ])


def response():
    return {"source":"EASTMONEY_PUBLIC_DAILY_UNADJUSTED_BAR",
            "response_body_sha256":"b"*64}


def test_issuer_source_cash_and_new_shares_not_double_counted():
    r=audit_single(event(),bars(),response(),csv_sha256="c"*64)
    assert r["nominal_shares_marked_on_ex_day"]=="1200.0"
    assert r["record_day_mark"]=="90000"
    assert r["ex_day_stock_plus_gross_cash_entitlement_mark"]=="90200.0"
    assert r["right_inclusive_mark_change"]==pytest.approx(200/90000)
    assert not r["broker_share_credit_verified"]
    assert not r["actual_ex_day_new_bonus_share_sellable_verified"]
    assert r["nominal_book"]["Qlib_adjusted_total_return_price_used"] is False


def test_unknown_capital_complement_and_missing_source_do_not_pretend_complete():
    e=event()
    e["capital_transfer_shares_per_old_share"]=None
    with pytest.raises(ValueError,match="Partial publisher"):
        audit_single(e,bars(),response(),csv_sha256="c"*64)
    with pytest.raises(ValueError,match="Source response"):
        audit_single(event(),bars(),{},csv_sha256="c"*64)


def test_ex_date_missing_censors_nominal_quote():
    b=bars()
    b=b[b.date!="2021-06-10"]
    with pytest.raises(ValueError,match="do not match"):
        audit_single(event(),b,response(),csv_sha256="c"*64)


def test_income_is_pretax_entitlement_never_actual_broker_settlement():
    r=audit_single(event(),bars(),response(),csv_sha256="c"*64)
    assert r["pretax_dividend_receivable"]=="200.0"
    assert r["broker_dividend_cash_credit_verified"] is False
    assert r["tax_net_received_not_proven"] is True
