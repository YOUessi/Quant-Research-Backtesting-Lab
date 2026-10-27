"""EXP-012: issuer stock-right UNKNOWN must censor ex-date numeric marks.

These are explicitly synthetic unit fixtures. Exact original issuer PDF,
CSV and catalogue SHA checks run separately in the Mac offline source replay.
"""
from decimal import Decimal
import json

import pandas as pd
import pytest

from quant_lab.pit_nominal_book import simulate_nominal_right
from quant_lab import pit_nominal_probe


def mock_event(pay="2022-07-22"):
    return {
        "symbol": "SH600000", "event_id": "SYNTHETIC_EXP012_FIXTURE",
        "record_date": "2022-07-20", "ex_date": "2022-07-21",
        "payment_date": pay, "gross_cash_per_nominal_share": "0.41",
        "issuer_pdf_sha256": "a" * 64,
        "earliest_usable_exchange_day": "2022-07-14",
        "evidence_grade": "SYNTHETIC_UNIT_TEST_NOT_ACTUAL_ISSUER",
    }


def mock_bars():
    return pd.DataFrame({
        "date": ["2022-07-20", "2022-07-21", "2022-07-22", "2022-07-25"],
        "close_raw": [10, 9.59, 9.59, 9.60],
    })


def book(ratio=None, **extra):
    return simulate_nominal_right(
        mock_event(), mock_bars(), original_shares=1000,
        share_bonus_ratio=ratio,
        share_bonus_terms_officially_verified=(ratio is not None),
        **extra,
    )


def test_unknown_stock_bonus_is_not_silently_zero_or_a_fabricated_return():
    b = book()
    original, ex, due, later = b["records"]
    assert Decimal(original["equity_gross_scenario"]) == Decimal("10000")
    assert original["nominal_shares"] == "1000"
    assert original["stock_rights_mark_status"] == "RECORD_DAY_CUM_RIGHTS_UNSEPARATED"
    for day in (ex, due, later):
        assert day["nominal_shares"] is None
        assert day["share_mark"] is None
        assert day["equity_gross_scenario"] is None
        assert day["issuer_new_share_claim_uncredited"] is None
        assert day["issuer_new_share_claim_price_mark"] is None
        assert day["stock_rights_mark_status"] == "CENSORED_UNVERIFIED_ISSUER_SHARE_RIGHTS"
        assert Decimal(day["pretax_receivable"]) == Decimal("410")
        assert day["cash_schedule_only"] == "0"
    assert b["post_ex_stock_mark_censored_unknown_issuer_rights"] is True
    assert b["ex_close_including_gross_receivable_scenario"] is None
    assert b["ex_close_total_mark_change"] is None
    assert "EX_CASH_CLAIM_KNOWN_STOCK_RIGHTS_MARK_CENSORED" in ex["events"]


def test_explicit_source_verified_zero_retains_numeric_mark():
    b = book("0")
    ex = b["records"][1]
    assert b["post_ex_stock_mark_censored_unknown_issuer_rights"] is False
    assert ex["nominal_shares"] == "1000"
    assert Decimal(ex["share_mark"]) == Decimal("9590")
    assert Decimal(ex["equity_gross_scenario"]) == Decimal("10000")
    assert ex["issuer_new_share_claim_uncredited"] == "0"
    assert ex["broker_confirmed_new_share_quantity"] is None
    assert ex["broker_confirmed_sellable_share_quantity"] is None


def test_positive_issuer_share_rights_are_claims_not_broker_credited_inventory():
    b = book("0.2")
    original, ex, due, later = b["records"]
    for day in (ex, due, later):
        assert Decimal(day["nominal_shares"]) == Decimal("1200")
        assert Decimal(day["issuer_new_share_claim_uncredited"]) == Decimal("200")
        assert Decimal(day["issuer_new_share_claim_price_mark"]) == (
            Decimal("200") * Decimal(day["unadjusted_nominal_close"]))
        assert Decimal(day["share_mark"]) == (
            Decimal("1000") * Decimal(day["unadjusted_nominal_close"])
            + Decimal(day["issuer_new_share_claim_price_mark"]))
        assert day["broker_confirmed_new_share_quantity"] is None
        assert day["broker_confirmed_sellable_share_quantity"] is None
        assert day["stock_rights_mark_status"] == "ISSUER_SHARE_CLAIM_NOT_BROKER_CREDIT"
    assert original["issuer_new_share_claim_uncredited"] == "0"
    assert b["issuer_share_entitlement_is_not_broker_delivered_sellable_inventory"] is True
    assert b["broker_sellable_share_quantity_not_available"] is True


def test_claim_remains_unknown_even_when_issuer_scheduled_payment_passes():
    b = book()
    assert b["source_schedule_reached_within_quote_window"] is True
    assert b["records"][-1]["gross_receivable_credit_status"] == (
        "ISSUER_SCHEDULE_REACHED_CREDIT_UNVERIFIED")
    assert b["records"][-1]["equity_gross_scenario"] is None
    assert b["cash_credited_in_this_scenario"] == "0"


def test_unaudited_stock_ratio_still_rejected():
    with pytest.raises(ValueError, match="unaudited"):
        simulate_nominal_right(
            mock_event(), mock_bars(), original_shares=1000,
            share_bonus_ratio="0", share_bonus_terms_officially_verified=False)


def test_probe_can_archive_censored_case_without_claiming_ex_date_return(tmp_path, monkeypatch):
    # Synthetic probe response: no real market data is fetched or redistributed.
    e = {**mock_event(pay="2022-07-21"),
         "share_bonus_and_transfer_verified_zero": False,
         "announcement_day": "2022-07-13"}
    ledger = tmp_path / "mock_cash_ledger.json"
    ledger.write_text(json.dumps({"events": [e]}), "utf-8")
    monkeypatch.setattr(pit_nominal_probe, "TARGETS", {("SH600000", "2022-07-21")})

    class NoNetworkSession:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return None

    def fake_bars(session, symbol, *, start, end):
        assert symbol == "SH600000"
        return mock_bars(), {"response_body_sha256": "b" * 64,
                             "source": "SYNTHETIC_TEST_NOT_VENDOR"}

    monkeypatch.setattr(pit_nominal_probe.requests, "Session", NoNetworkSession)
    monkeypatch.setattr(pit_nominal_probe, "fetch_independent_unadjusted_bars", fake_bars)
    output = tmp_path / "synthetic_probe"
    result = pit_nominal_probe.run(ledger, output)
    case = result["items"][0]
    assert case["post_ex_stock_rights_mark_censored"] is True
    assert case["historical_nominal_ledger"]["ex_close_total_mark_change"] is None
    assert case["historical_nominal_ledger"]["ex_close_including_gross_receivable_scenario"] is None
    assert json.loads((output / "EXP005_nominal_probe.json").read_text())["items"][0][
        "post_ex_stock_rights_mark_censored"] is True
