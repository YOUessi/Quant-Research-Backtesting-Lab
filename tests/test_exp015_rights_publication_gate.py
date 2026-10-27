"""EXP015 source-clock and incomplete stock-rights fail-closed regressions."""
import copy
from pathlib import Path

import pytest

from quant_lab.pit_rights_publication_gate import (
    assess_event, check_original_first_page, exact_day, parse_calendar,
    right_number, run, verify,
)

CAL = [
    "2021-06-25", "2021-06-28", "2021-06-29", "2021-06-30",
    "2021-07-01", "2021-07-02", "2021-07-05",
]


def event(complete=True):
    return {
        "event_id": "test-original-issuer-event",
        "symbol": "SH600001",
        "announcement_day": "2021-06-29",
        "earliest_usable_exchange_day": "2021-06-30",
        "record_date": "2021-07-01",
        "ex_date": "2021-07-02",
        "scheduled_cash_payment_day": "2021-07-02",
        "issuer_original_pdf_url": "https://static.cninfo.com.cn/finalpage/2021-06-29/123.PDF",
        "issuer_original_pdf_sha256": "a" * 64,
        "bonus_shares_per_old_share": 0.0 if complete else None,
        "capital_transfer_shares_per_old_share": 0.0 if complete else None,
        "full_new_nominal_share_multiplier": 1.0 if complete else None,
        "complete_rights_supported_by_issuer_original": complete,
        "gross_cash_per_old_nominal_share": 0.2,
        "positive_stock_rights": False,
        "original_publication_intraday_time_certified": False,
        "historical_factor_vintage_available": False,
        "broker_share_delivery_and_cash_payment_verified": False,
        "cash_rights_nominal_not_qlib_adjusted": True,
    }


def test_complete_source_still_embargoed_until_next_session():
    proof = assess_event(event(), CAL)
    a, b, c = proof["source_day_decision_probes"]
    assert a["decision_session"] == "2021-06-29"
    assert not a["issuer_pdf_known_from_day_only_notice_asof"]
    assert not a["both_stock_rights_known_asof"]
    assert a["nominal_new_share_multiplier_asof"] is None
    assert b["issuer_pdf_known_from_day_only_notice_asof"]
    assert b["nominal_new_share_multiplier_asof"] == "1.0"
    assert c["nominal_new_share_multiplier_asof"] == "1.0"
    assert not any(p["actual_cash_credit_proven"] for p in (a, b, c))


def test_unknown_source_not_assumed_cash_only_after_publication():
    proof = assess_event(event(False), CAL)
    assert proof["bonus_rights_missing"] and proof["capital_transfer_rights_missing"]
    assert proof["source_day_decision_probes"][1]["issuer_pdf_known_from_day_only_notice_asof"]
    assert not any(p["both_stock_rights_known_asof"] for p in proof["source_day_decision_probes"])
    assert all(p["nominal_new_share_multiplier_asof"] is None
               for p in proof["source_day_decision_probes"])


def test_partial_positive_transfer_remains_censored():
    row = event(False)
    row["capital_transfer_shares_per_old_share"] = 0.8
    row["positive_stock_rights"] = True
    proof = assess_event(row, CAL)
    assert proof["bonus_rights_missing"] is True
    assert proof["capital_transfer_rights_missing"] is False
    assert proof["source_day_decision_probes"][2]["nominal_new_share_multiplier_asof"] is None


def test_nonconsecutive_released_first_session_rejected():
    row = event()
    row["earliest_usable_exchange_day"] = "2021-07-01"
    with pytest.raises(ValueError, match="next exchange session"):
        assess_event(row, CAL)


def test_same_day_source_assumption_rejected():
    row = event()
    row["earliest_usable_exchange_day"] = row["announcement_day"]
    with pytest.raises(ValueError, match="next exchange session"):
        assess_event(row, CAL)


def test_holiday_and_weekend_calendar_respected_without_weekday_guess():
    row = event()
    row.update(announcement_day="2021-06-26",
               issuer_original_pdf_url="https://static.cninfo.com.cn/finalpage/2021-06-26/123.PDF",
               earliest_usable_exchange_day="2021-06-28")
    source = assess_event(row, CAL)
    assert source["first_usable_exchange_day"] == "2021-06-28"


@pytest.mark.parametrize("field, bad, error", [
    ("issuer_original_pdf_sha256", "abc", "SHA256"),
    ("issuer_original_pdf_url", "https://fake.cninfo.com.cn/finalpage/2021-06-29/123.PDF", "URL"),
    ("record_date", "2021-07-03", "exchange session"),
    ("ex_date", "2021-07-01", "effective-day sequence"),
    ("scheduled_cash_payment_day", "2021-06-30", "predates ex-day"),
])
def test_source_identity_and_effective_dates_refuse_tampering(field, bad, error):
    row = event()
    row[field] = bad
    with pytest.raises(ValueError, match=error):
        assess_event(row, CAL)


@pytest.mark.parametrize("field", [
    "original_publication_intraday_time_certified",
    "historical_factor_vintage_available",
    "broker_share_delivery_and_cash_payment_verified",
])
def test_no_invented_broker_factor_or_intraday_evidence(field):
    row = event()
    row[field] = True
    with pytest.raises(ValueError, match="incorrectly promoted"):
        assess_event(row, CAL)


def test_source_complete_flag_requires_two_known_categories():
    row = event(False)
    row["complete_rights_supported_by_issuer_original"] = True
    with pytest.raises(ValueError, match="completeness"):
        assess_event(row, CAL)


def test_partial_unknown_cannot_emit_fake_multiplier():
    row = event(False)
    row["full_new_nominal_share_multiplier"] = 1.0
    with pytest.raises(ValueError, match="Unknown stock right"):
        assess_event(row, CAL)


def test_complete_stock_claim_must_match_sum():
    row = event()
    row["bonus_shares_per_old_share"] = 0.2
    row["positive_stock_rights"] = True
    with pytest.raises(ValueError, match="inconsistent"):
        assess_event(row, CAL)


@pytest.mark.parametrize("bad", ["nan", "Infinity", -0.2, True])
def test_ratio_cannot_be_nonfinite_negative_or_boolean(bad):
    row = event()
    row["bonus_shares_per_old_share"] = bad
    with pytest.raises(ValueError):
        assess_event(row, CAL)


def test_calendar_strict_order_and_accurate_iso_days():
    assert parse_calendar("\n".join([f"2021-01-{i:02d}" for i in range(1, 30)] +
           [f"2021-02-{i:02d}" for i in range(1, 29)] +
           [f"2021-03-{i:02d}" for i in range(1, 32)] +
           [f"2021-04-{i:02d}" for i in range(1, 31)] +
           [f"2021-05-{i:02d}" for i in range(1, 32)] +
           [f"2021-06-{i:02d}" for i in range(1, 31)] +
           [f"2021-07-{i:02d}" for i in range(1, 32)] +
           [f"2021-08-{i:02d}" for i in range(1, 32)] +
           [f"2021-09-{i:02d}" for i in range(1, 31)] +
           [f"2021-10-{i:02d}" for i in range(1, 32)]).encode())[-1] == "2021-10-31"
    with pytest.raises(ValueError, match="sorted and unique"):
        parse_calendar(b"2021-06-30\n2021-06-29\n")
    with pytest.raises(ValueError, match="Invalid"):
        exact_day("2021-02-30")


def test_mutated_catalog_and_calendar_original_byte_digest_fail():
    with pytest.raises(ValueError, match="catalog full SHA256"):
        verify(catalog_bytes=b"{}", calendar_bytes=b"", pdf_dirs=[])
    # Deliberate actual original catalog hash is required even for well-formed JSON.


def test_original_issuer_pdf_header_guard_fails_closed():
    with pytest.raises(ValueError, match="not PDF"):
        check_original_first_page(event(), b"not-a-real-PDF")


def test_output_path_is_immutable_before_any_input_read(tmp_path: Path):
    out = tmp_path / "existing.json"
    out.write_text("old")
    with pytest.raises(FileExistsError, match="overwrite"):
        run(tmp_path / "missing-catalog.json", tmp_path / "missing-calendar.txt", [], out)
    assert out.read_text() == "old"


def test_issuer_pdf_url_publication_day_cannot_be_backdated():
    row = event()
    row["issuer_original_pdf_url"] = (
        "https://static.cninfo.com.cn/finalpage/2021-06-28/123.PDF"
    )
    with pytest.raises(ValueError, match="dated publication-day"):
        assess_event(row, CAL)


def test_calendar_full_bytes_digest_is_independently_pinned(monkeypatch):
    import hashlib
    import quant_lab.pit_rights_publication_gate as gate

    # Unit-test only: pass the first pin to exercise the independent second
    # calendar digest guard, without substituting any real source file.
    fake_catalog = b"{}"
    monkeypatch.setattr(
        gate, "CATALOG_SHA256", hashlib.sha256(fake_catalog).hexdigest()
    )
    with pytest.raises(ValueError, match="calendar full SHA256"):
        gate.verify(catalog_bytes=fake_catalog, calendar_bytes=b"tampered", pdf_dirs=[])
