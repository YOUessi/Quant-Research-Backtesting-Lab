"""EXP-011 cash-credit fail-closed regression: issuer schedule != broker cash."""
import pandas as pd
import pytest

from quant_lab.pit_nominal_book import simulate_nominal_right
from quant_lab.pit_receivable_due_audit import (
    PINS, verified_sha, verify_issuer_original,
)


def source_event(pay="2022-07-22"):
    return {
        "symbol": "SH600000", "event_id": "mock-only-unit-fixture",
        "record_date": "2022-07-20", "ex_date": "2022-07-21",
        "payment_date": pay,
        "gross_cash_per_nominal_share": "0.41",
        "issuer_pdf_sha256": "a" * 64,
        "earliest_usable_exchange_day": "2022-07-14",
        "evidence_grade": "UNIT_TEST_NOT_REAL_ISSUER",
    }


def bars():
    return pd.DataFrame({
        "date": ["2022-07-20", "2022-07-21", "2022-07-22",
                 "2022-07-25", "2022-07-26"],
        "close_raw": [10, 9.59, 9.59, 9.60, 9.40],
    })


def booked(event=None, prices=None):
    return simulate_nominal_right(
        source_event() if event is None else event,
        bars() if prices is None else prices,
        original_shares=1000, share_bonus_ratio="0",
        share_bonus_terms_officially_verified=True,
    )


def test_gross_receivable_persists_across_pay_date_and_following_sessions():
    r = booked()
    record, ex, due, later1, later2 = r["records"]
    assert record["pretax_receivable"] == "0"
    for day in (ex, due, later1, later2):
        assert float(day["pretax_receivable"]) == pytest.approx(410)
        assert day["cash_schedule_only"] == "0"
    assert due["gross_receivable_credit_status"] == "ISSUER_SCHEDULE_REACHED_CREDIT_UNVERIFIED"
    assert later2["gross_receivable_credit_status"] == due["gross_receivable_credit_status"]
    assert r["cash_credited_in_this_scenario"] == "0"
    assert r["source_schedule_reached_within_quote_window"] is True
    assert r["cash_payment_broker_confirmed"] is False
    assert "ISSUER_PAYMENT_SCHEDULE_REACHED_BROKER_CREDIT_UNVERIFIED" in due["events"]
    assert "ISSUER_PAYMENT_SCHEDULE_REACHED_BROKER_CREDIT_UNVERIFIED" not in later1["events"]


def test_quote_window_ends_before_issuer_payday_without_making_up_credit():
    r = booked(prices=bars().iloc[:2])
    assert len(r["records"]) == 2
    assert r["scheduled_payment_date"] == "2022-07-22"
    assert r["source_schedule_reached_within_quote_window"] is False
    assert r["records"][-1]["pretax_receivable"] == "410.00"
    assert r["records"][-1]["cash_schedule_only"] == "0"


def test_unknown_issuer_payment_day_is_not_assumed_settled():
    r = booked(event=source_event(pay=None))
    assert r["source_payment_day_unverified"] is True
    assert r["source_schedule_reached_within_quote_window"] is False
    assert r["records"][-1]["gross_receivable_credit_status"] == (
        "GROSS_ENTITLEMENT_UNSETTLED_CREDIT_UNVERIFIED")
    assert r["records"][-1]["pretax_receivable"] == "410.00"


def test_missing_trade_on_issuer_payday_marks_first_available_later_day():
    q = bars()
    q = q[q["date"] != "2022-07-22"]
    r = booked(prices=q)
    assert "ISSUER_PAYMENT_SCHEDULE_REACHED_BROKER_CREDIT_UNVERIFIED" in r["records"][2]["events"]
    assert r["records"][2]["date"] == "2022-07-25"
    assert r["records"][2]["pretax_receivable"] == "410.00"


def test_mark_equity_preserves_claim_and_does_not_double_count_it():
    r = booked()
    for x in r["records"][1:]:
        assert float(x["equity_gross_scenario"]) == pytest.approx(
            1000 * float(x["unadjusted_nominal_close"]) + 410)
    assert r["ex_close_total_mark_change"] == pytest.approx(0.0)


def test_broker_cash_credit_cannot_be_claimed_without_actual_record():
    with pytest.raises(ValueError, match="separate actual credit"):
        simulate_nominal_right(
            source_event(), bars(),
            broker_payment_verified=True,
            share_bonus_ratio="0", share_bonus_terms_officially_verified=True)


def test_pinned_sha_detects_even_one_modified_original_byte():
    raw = b"prior original issuer PDF bytes unit fixture"
    import hashlib
    h = hashlib.sha256(raw).hexdigest()
    assert verified_sha(raw, h, "unit fixture") == h
    with pytest.raises(ValueError, match="SHA256 mismatch"):
        verified_sha(raw + b"x", h, "unit fixture")
    with pytest.raises(ValueError, match="Invalid pinned SHA"):
        verified_sha(raw, "a", "unit fixture")


def test_issuer_source_cannot_upgrade_incomplete_share_rights():
    pin = PINS[("SH600276", "2021-06-10")]
    with pytest.raises(ValueError, match="Partial corporate"):
        verify_issuer_original(
            {"issuer_original_pdf_sha256": pin["pdf_sha256"],
             "issuer_original_pdf_url": "https://static.cninfo.com.cn/finalpage/test.PDF",
             "complete_rights_supported_by_issuer_original": False},
            b"no PDF", pin)


def test_issuer_source_rejects_wrong_publication_usable_day_even_if_pdf_bytes_unreadable():
    pin = PINS[("SH600276", "2021-06-10")]
    row = {
        "issuer_original_pdf_sha256": pin["pdf_sha256"],
        "issuer_original_pdf_url": "https://static.cninfo.com.cn/finalpage/test.PDF",
        "complete_rights_supported_by_issuer_original": True,
        "earliest_usable_exchange_day": "2021-06-04",
        "scheduled_cash_payment_day": pin["pay"],
        "record_date": pin["record"],
        "gross_cash_per_old_nominal_share": 0.2,
        "bonus_shares_per_old_share": 0.2,
        "capital_transfer_shares_per_old_share": 0,
    }
    # Date-gate preflight must reject a backdated claim even before the
    # (separately mandatory) full original PDF byte verification.
    with pytest.raises(ValueError, match="date/publication embargo mismatch"):
        verify_issuer_original(row, b"not original", pin)


def test_derived_source_pin_is_not_authority_for_actual_http_response_bytes():
    # A stored digest is not an archived HTTP response body; the audit must
    # expose this uncertainty rather than saying the provider was re-fetched.
    pin = PINS[("SH600760", "2021-06-24")]
    assert len(pin["http_response_sha256"]) == 64
    assert pin["http_response_sha256"] != pin["csv_sha256"]
    assert pin["meta_sha256"] != pin["pdf_sha256"]


def test_gross_receivable_claim_not_a_broker_confirmed_account_asset():
    r = booked()
    assert r["completed_actual_portfolio_revaluation"] is False
    assert r["gross_receivable_retained_without_broker_credit"] is True
    assert r["trade_fills_or_auction_orderbook_verified"] is False
