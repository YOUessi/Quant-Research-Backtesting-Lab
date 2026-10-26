"""Previously fetched independent daily price provenance must match issuer proof."""
import pytest

from quant_lab.pit_nominal_probe import previously_collected_real_unadjusted_marks


def entry():
    return {
        "symbol":"SZ000001","ex_date":"2022-07-22",
        "record_date":"2022-07-21","payment_date":"2022-07-22",
        "gross_cash_per_nominal_share":.228,"issuer_pdf_sha256":"a"*64,
    }


def earlier():
    return {"rights":[{
        "symbol":"SZ000001","ex_date":"2022-07-22",
        "source_issuer_pdf_sha256":"a"*64,
        "pre_tax_dividend_receivable":228,
        "shares_registered_nominal":1000,
        "registered_share_nominal_price_close":13.01,
        "ex_date_share_nominal_price_close":12.81,
        "source_unadjusted_ohlcv":{
            "source":"Eastmoney unadjusted",
            "response_body_sha256":"b"*64,
            "retrieved_utc":"2026-10-26T04:00:00Z",
        },
    }]}


def test_offline_replay_is_real_source_mark_not_newly_fetched():
    bars,source=previously_collected_real_unadjusted_marks(
        earlier(),entry(),shares=1000
    )
    assert bars["date"].tolist()==["2022-07-21","2022-07-22"]
    assert bars["close_raw"].tolist()==[13.01,12.81]
    assert source["data_reused_not_fetched_this_run"]
    assert source["whole_response_body_not_rearchived_in_this_stage"]


def test_prior_vendor_quote_not_accepted_if_pdf_hash_or_dividend_disagrees():
    wrong=entry()
    wrong["issuer_pdf_sha256"]="f"*64
    with pytest.raises(ValueError,match="hash or payout|source mark"):
        previously_collected_real_unadjusted_marks(
            earlier(),wrong,shares=1000
        )
    wrong=entry()
    wrong["gross_cash_per_nominal_share"]=.333
    with pytest.raises(ValueError,match="hash or payout|source mark"):
        previously_collected_real_unadjusted_marks(
            earlier(),wrong,shares=1000
        )


def test_missing_future_cash_post_date_not_synthesized():
    modified=entry()
    modified["payment_date"]="2022-07-26"
    with pytest.raises(ValueError,match="insufficient"):
        previously_collected_real_unadjusted_marks(
            earlier(),modified,shares=1000
        )
