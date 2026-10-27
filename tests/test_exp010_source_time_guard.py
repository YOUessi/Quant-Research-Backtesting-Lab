"""EXP010 prohibits silently promoting published-later fund reports to past decisions."""
from copy import deepcopy

import pytest

from quant_lab.pit_fund_suspension_evidence import SOURCES
from quant_lab.pit_source_time_guard import (
    EXPECTED_DAYS, build_embargo_audit, verify_original_source_report,
)


def stub_source(name):
    s = SOURCES[name]
    return {
        "kind": s["kind"],
        "publication_day": s["publication_day"],
        "source_sha256": s["sha256"],
        "source_url": s["url"],
        "full_reason_specific_interval_proven": False,
    }


def stub_sources():
    return {name: stub_source(name) for name in ("exchange", "broker", "fund1", "fund2")}


def calendar():
    return [
        "2021-06-16", "2021-06-17", "2021-06-18", "2021-06-21",
        "2021-06-22", "2021-06-23", "2021-06-30", "2021-07-01",
        "2021-07-06", "2021-08-27", "2021-08-30", "2021-08-31", "2021-09-01",
    ]


def test_independent_four_publication_embargo_sessions():
    r = build_embargo_audit(stub_sources(), calendar())
    assert r["source_first_usable_sessions"] == {
        "exchange": "2021-06-17", "broker": "2021-07-01",
        "fund1": "2021-08-30", "fund2": "2021-09-01",
    }
    assert r["June_2021_fund_source_day_uses"] == 0
    assert r["June_2021_primary_halt_start_available_asof_days"] == 4
    assert [x["frozen_missing_member_day"] for x in r["five_decision_day_guards"]] == list(EXPECTED_DAYS)
    assert r["five_decision_day_guards"][0]["source_ids_eligible_asof_decision_day"] == []
    assert all(not x["specific_first_halt_reason_end_date_verified_asof_day"]
               for x in r["five_decision_day_guards"])
    assert not r["models_or_frozen_historical_returns_changed"]


def test_announced_same_day_is_not_intraday_available():
    assert not build_embargo_audit(stub_sources(), calendar())[
        "five_decision_day_guards"][0]["original_exchange_halt_START_available_asof_day"]


def test_period_end_is_not_publication_day():
    source = stub_sources()
    source["fund1"]["fund_period_end"] = "2021-06-30"
    audit = build_embargo_audit(source, calendar())
    assert audit["source_first_usable_sessions"]["fund1"] == "2021-08-30"


def test_retrospective_fund_backdate_fails_closed():
    source = stub_sources()
    source["fund1"]["publication_day"] = "2021-06-15"
    with pytest.raises(ValueError, match="retrospective fund PDF"):
        build_embargo_audit(source, calendar())


def test_unverified_halt_end_grade_cannot_be_elevated():
    source = stub_sources()
    source["exchange"]["full_reason_specific_interval_proven"] = True
    with pytest.raises(ValueError, match="silently upgraded"):
        build_embargo_audit(source, calendar())


def test_fund_pdf_requires_full_source_digest():
    source = stub_sources()
    source["fund2"]["source_sha256"] = "sha256-not-verified"
    with pytest.raises(ValueError, match="full source SHA256"):
        build_embargo_audit(source, calendar())


def test_calendar_missing_exchange_trading_day_fails():
    with pytest.raises(ValueError, match="misses one"):
        build_embargo_audit(stub_sources(), calendar()[1:])


def test_fund_originals_all_four_are_required():
    source = stub_sources()
    source.pop("broker")
    with pytest.raises(ValueError, match="Four original"):
        build_embargo_audit(source, calendar())


def test_no_available_future_session_fails_instead_of_guessing():
    with pytest.raises(ValueError, match="No later exchange session"):
        build_embargo_audit(stub_sources(), list(EXPECTED_DAYS))


def test_wrong_report_kind_rejected_even_if_files_exist(tmp_path):
    with pytest.raises(ValueError, match="pinned EXP009"):
        verify_original_source_report(
            {"kind": "GENERIC_EVENT"},
            originals_dir=tmp_path, broker_original=tmp_path/"unknown.html")


def test_report_counters_must_remain_primary_134_not_139(tmp_path):
    report = {
        "kind": "EXP009_SUNING_FIVE_REMAINING_MEMBER_DAY_SECONDARY_ORIGINAL_FUND_CORROBORATION",
        "original_issuer_or_exchange_FULL_interval_verified_days_retained": 139,
    }
    with pytest.raises(ValueError, match="scope changed"):
        verify_original_source_report(
            report, originals_dir=tmp_path, broker_original=tmp_path/"missing.html")
