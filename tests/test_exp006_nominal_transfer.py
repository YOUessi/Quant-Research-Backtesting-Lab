"""Full issuer-certified 10-to-6 transfer plus dividend nominal mark tests."""
from pathlib import Path
import json

import pandas as pd
import pytest

from quant_lab.pit_positive_nominal_probe import run


def fixtures(tmp_path):
    cash={"events":[{
        "event_id":"e1","symbol":"SZ300751","ex_date":"2022-04-14",
        "record_date":"2022-04-13","announcement_day":"2022-04-07",
        "payment_date":None,"issuer_pdf_sha256":"a"*64,
        "issuer_pdf_url":"https://static.cninfo.com.cn/finalpage/2022-04-07/original.PDF",
        "gross_cash_per_nominal_share":1.5,
        "earliest_usable_exchange_day":"2022-04-08",
        "evidence_grade":"original_issuer_PDF"
    }]}
    rights={"audit":[{
        "event_id":"e1","symbol":"SZ300751","issuer_pdf_sha256":"a"*64,
        "bonus_ratio_per_nominal_share":0.0,
        "transfer_ratio_per_nominal_share":0.6,
        "known_complete":True,
        "known_positive_stock_rights":True,
        "independent_transfer_ratio_crosscheck":"MATCH"
    }]}
    bars=pd.DataFrame([
        {"date":"2022-04-13","open_raw":486.5,"close_raw":468.96,
         "volume_lots":1000,"amount_currency":500000},
        {"date":"2022-04-14","open_raw":294.5,"close_raw":282.4,
         "volume_lots":2000,"amount_currency":510000},
    ])
    source={"source":"EASTMONEY_PUBLIC_DAILY_UNADJUSTED_BAR",
            "response_body_sha256":"b"*64,
            "retrieved_utc":"2026-10-27T00:00:00Z"}
    files=[tmp_path/f for f in ("cash.json","rights.json","bars.csv","source.json")]
    files[0].write_text(json.dumps(cash));files[1].write_text(json.dumps(rights))
    bars.to_csv(files[2],index=False);files[3].write_text(json.dumps(source))
    return files


def test_2022_issuer_dividend_transfer_prevents_false_39pct_equity_loss(tmp_path):
    inputs=fixtures(tmp_path)
    result=run(*inputs,output=tmp_path/"out")
    assert result["nominal_shares_after_ex"]==pytest.approx(1600)
    assert result["pretax_cash_receivable"]==pytest.approx(1500)
    assert result["record_nominal_market_mark"]==pytest.approx(468960)
    assert result["ex_nominal_market_mark_plus_pretax_receivable"]==pytest.approx(453340)
    assert result["price_only_change"] < -.3
    assert -.04<result["entitlement_aware_nominal_mark_change"]<-.03
    assert not result["zero_real_broker_fills_observed"] is False
    assert not result["nominal_book"]["Qlib_adjusted_total_return_price_used"]


def test_issuer_bonus_ratio_must_be_complete(tmp_path):
    inp=fixtures(tmp_path)
    rights=json.loads(inp[1].read_text())
    rights["audit"][0]["bonus_ratio_per_nominal_share"]=None
    rights["audit"][0]["known_complete"]=False
    inp[1].write_text(json.dumps(rights))
    with pytest.raises(ValueError,match="issuer-known"):
        run(*inp,output=tmp_path/"bad")


def test_issuer_cash_or_independent_quote_mismatch_fails_closed(tmp_path):
    inputs=fixtures(tmp_path)
    book=json.loads(inputs[1].read_text())
    book["audit"][0]["issuer_pdf_sha256"]="c"*64
    inputs[1].write_text(json.dumps(book))
    with pytest.raises(ValueError,match="source SHA disagreement"):
        run(*inputs,output=tmp_path/"bad")
