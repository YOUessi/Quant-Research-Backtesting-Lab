"""Independent issuer/right and retrospective vendor factor arithmetic tests."""
import pandas as pd
import pytest

from quant_lab.pit_factor_event_crosscheck import audit


def sample():
    cash={"events":[{
        "event_id":"event1","symbol":"SZ300751","ex_date":"2022-04-14",
        "record_date":"2022-04-13","gross_cash_per_nominal_share":1.5,
        "issuer_pdf_sha256":"a"*64,
        "issuer_pdf_url":"https://static.cninfo.com.cn/finalpage/2022-04-07/notice.PDF",
    }]}
    right={"audit":[{
        "event_id":"event1","issuer_pdf_sha256":"a"*64,"known_complete":True,
        "known_positive_stock_rights":True,
        "independent_transfer_ratio_crosscheck":"MATCH",
        "full_nominal_share_multiplier_issuer_verified":1.6,
    }]}
    q=pd.DataFrame([
        {"asset":"SZ300751","date":"2022-04-13","raw_close_estimate":468.95999,
         "factor_step_ratio":1.000003},
        {"asset":"SZ300751","date":"2022-04-14","raw_close_estimate":282.400024,
         "factor_step_ratio":1.605164},
    ])
    raw=pd.DataFrame([
        {"date":"2022-04-13","close_raw":468.96},
        {"date":"2022-04-14","close_raw":282.40},
    ])
    return cash,right,q,raw


def test_issuer_10to6_cash_dividend_explains_factor_step():
    data=sample()
    audit_result=audit(*data,quote_sha256="b"*64)
    assert audit_result["factor_arithmetic_consistent_with_simple_corporate_formula_within_0_05pct"]
    assert 1.605 < audit_result["theoretical_backward_factor_step_from_source_rights"] < 1.606
    assert not audit_result["historical_decision_day_adjustment_factor_version_proven"]
    assert audit_result["max_abs_price_difference_Qlib_reconstructed_vs_independent_raw"] < .0051


def test_real_raw_source_discrepancy_rejected():
    cash,share,q,raw=sample()
    raw.loc[raw.date.eq("2022-04-14"),"close_raw"]=290.0
    with pytest.raises(ValueError,match="Cross-source nominal price mismatch"):
        audit(cash,share,q,raw,quote_sha256="b"*64)


def test_incomplete_issuer_bonus_blocks_factor_certificate():
    cash,share,q,raw=sample()
    share["audit"][0]["known_complete"]=False
    with pytest.raises(ValueError,match="source-verified stock right multiplier"):
        audit(cash,share,q,raw,quote_sha256="b"*64)
