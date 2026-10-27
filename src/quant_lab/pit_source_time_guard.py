"""EXP-010: enforce publication-time embargo on retrospective halt evidence.

The two original 2021 fund interim reports show July-06 reopening, but were
published on Aug-27/Aug-31. Their June-30 valuation and resumed-price facts
must never be treated as June decision-day public knowledge. An exchange
halt-START notice without a resume date cannot independently certify a full
reason-specific halt interval.

This is an immutable source/provenance audit, NOT an order fill simulator.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd

from .pit_events import first_usable_exchange_session
from .pit_fund_suspension_evidence import (
    SOURCES, STOCK, verify_exchange_original, verify_broker_original,
    verified_fund_pages, sha256_file,
)

EXPECTED_DAYS = ("2021-06-16", "2021-06-17", "2021-06-18",
                 "2021-06-21", "2021-06-22")
REPORT_KIND = (
    "EXP009_SUNING_FIVE_REMAINING_MEMBER_DAY_SECONDARY_ORIGINAL_FUND_CORROBORATION"
)


def _check_exact(actual: dict, expected: dict, keys: tuple[str, ...], label: str) -> None:
    for key in keys:
        if actual.get(key) != expected.get(key):
            raise ValueError(f"{label}: original source/report mismatch in {key}")


def verify_original_source_report(report: dict, *, originals_dir: Path,
                                  broker_original: Path) -> dict[str, dict]:
    """Rehash original bytes, reparse primary exchange/broker and fund pages.

    No precomputed JSON, filename, URL or fund periodic fiscal as-of date can
    substitute for an actual source *publication* date and full SHA256.
    """
    if report.get("kind") != REPORT_KIND:
        raise ValueError("Not the pinned EXP009 original-source report")
    required = {
        "frozen_qlib_unavailable_member_days_total": 139,
        "original_issuer_or_exchange_FULL_interval_verified_days_retained": 134,
        "new_additional_fund_original_retrospective_only_corrob_days": 5,
        "fund_disclosure_dates_after_halt_and_resume": True,
        "primary_original_issuer_first_five_day_segment_end_date_still_unverified": True,
        "official_exchange_ended_first_segment_on_2021_06_22": False,
        "fund_original_disclosure_count": 2,
    }
    for field, correct in required.items():
        if report.get(field) != correct:
            raise ValueError(f"Historical evidence scope changed: {field}")
    extra = report.get("five_additional_retrospectively_corrob_stock_days", [])
    if [(r.get("symbol"), r.get("date")) for r in extra] != [
        (STOCK, day) for day in EXPECTED_DAYS
    ] or any(r.get("grade") != "TWO_FUND_PERIODIC_ORIGINAL_DISCLOSURES_RETROSPECTIVE"
             for r in extra):
        raise ValueError("Original five Qlib missing-stock-day identities changed")

    verified: dict[str, dict] = {}
    exchange_source = SOURCES["exchange"]
    exchange_file = originals_dir / exchange_source["file"]
    sha256_file(exchange_file, exchange_source["sha256"])
    parsed = verify_exchange_original(exchange_file.read_bytes())
    _check_exact(report["primary_exchange_source"], parsed,
                 ("symbol", "publisher", "publication_day",
                  "initial_full_session_halt_from", "resume_effective_date_given",
                  "evidence_grade", "exact_intraday_notice_publication_certified"),
                 "Exchange")
    _check_exact(report["primary_exchange_source"],
                 {"original_html_sha256": exchange_source["sha256"],
                  "source_url": exchange_source["url"]},
                 ("original_html_sha256", "source_url"), "Exchange bytes")
    verified["exchange"] = {
        "kind": "PRIMARY_HALT_START_ONLY",
        "publication_day": parsed["publication_day"],
        "source_sha256": exchange_source["sha256"],
        "source_url": exchange_source["url"],
        "full_reason_specific_interval_proven": False,
    }

    broker_source = SOURCES["broker"]
    sha256_file(broker_original, broker_source["sha256"])
    broker = verify_broker_original(broker_original.read_bytes())
    _check_exact(report["dated_broker_source"], broker,
                 ("symbol", "publisher", "publication_day",
                  "historical_halt_start", "resume_time",
                  "evidence_grade", "does_not_establish_actual_resume_day"),
                 "Broker")
    _check_exact(report["dated_broker_source"],
                 {"original_html_sha256": broker_source["sha256"],
                  "source_url": broker_source["url"]},
                 ("original_html_sha256", "source_url"), "Broker bytes")
    verified["broker"] = {
        "kind": "SECONDARY_HALT_START_ONLY_RESUME_BLANK",
        "publication_day": broker["publication_day"],
        "source_sha256": broker_source["sha256"],
        "source_url": broker_source["url"],
        "full_reason_specific_interval_proven": False,
    }

    originals = report.get("fund_original_report_proofs", [])
    if len(originals) != 2 or len({x.get("fund_manager") for x in originals}) != 2:
        raise ValueError("Expected two distinct original fund managers")
    for key, claim in zip(("fund1", "fund2"), originals, strict=True):
        metadata = SOURCES[key]
        file = originals_dir / metadata["file"]
        sha256_file(file, metadata["sha256"])
        parsed, pages = verified_fund_pages(file, metadata)
        _check_exact(claim, parsed,
                     ("symbol", "fund_manager", "fund_name",
                      "original_report_publication_day", "original_period_end",
                      "historical_halt_start_reported", "eventual_actual_resume_reported",
                      "halted_share_mark_at_2021_06_30", "reported_resumption_open",
                      "fund_reported_nominal_shares", "fund_reported_total_mark",
                      "fund_mark_math_verified", "retrospectively_reported_after_resume",
                      "not_historical_decision_day_observable",
                      "evidence_grade"), f"Original {key}")
        _check_exact(claim, {"source_url": metadata["url"],
                             "original_fund_pdf_sha256": metadata["sha256"],
                             "original_report_halted_stock_table_pdf_zero_indexed_page": pages[0]},
                     ("source_url", "original_fund_pdf_sha256",
                      "original_report_halted_stock_table_pdf_zero_indexed_page"),
                     f"Original {key} SHA/page")
        verified[key] = {
            "kind": "ORIGINAL_FUND_PERIODIC_DISCLOSURE_RETROSPECTIVE",
            "publication_day": parsed["original_report_publication_day"],
            "fund_period_end": parsed["original_period_end"],
            "source_sha256": metadata["sha256"],
            "source_url": metadata["url"],
            "full_reason_specific_interval_proven": False,
            "actual_resume_from_report": parsed["eventual_actual_resume_reported"],
        }
    if not all(x["publication_day"] > "2021-07-06"
               for k, x in verified.items() if k.startswith("fund")):
        raise ValueError("Funds cannot disclose eventual reopening before its publication")
    return verified


def build_embargo_audit(sources: dict[str, dict],
                        exchange_calendar: list[str]) -> dict[str, Any]:
    """Decisions use day-only disclosures only from the NEXT exchange session.

    As-of eligibility means a published source is available, NOT that its
    partial proof establishes a halt end, a session-by-session exchange state,
    a valid mark for another holder or an executable broker order.
    """
    cal = sorted({pd.Timestamp(x).date().isoformat() for x in exchange_calendar})
    if cal != sorted(cal) or not set(EXPECTED_DAYS).issubset(set(cal)):
        raise ValueError("Exchange calendar misses one of the five frozen trading days")
    if len(sources) != 4 or set(sources) != {"exchange", "broker", "fund1", "fund2"}:
        raise ValueError("Four original source types must be independently present")
    starts = {}
    for name, proof in sources.items():
        pub = pd.Timestamp(proof["publication_day"]).date().isoformat()
        if len(str(proof.get("source_sha256", ""))) != 64:
            raise ValueError("Missing full source SHA256")
        if proof.get("full_reason_specific_interval_proven") is not False:
            raise ValueError("Source grade cannot be silently upgraded")
        starts[name] = first_usable_exchange_session(pub, cal)
    if starts["exchange"] != "2021-06-17":
        raise ValueError("Exchange first-usable day violates conservative embargo")
    days = []
    for day in EXPECTED_DAYS:
        available = [k for k in ("exchange", "broker", "fund1", "fund2")
                     if starts[k] <= day]
        funds = [k for k in available if k.startswith("fund")]
        days.append({
            "symbol": STOCK, "frozen_missing_member_day": day,
            "source_ids_eligible_asof_decision_day": available,
            "original_exchange_halt_START_available_asof_day": "exchange" in available,
            "retrospective_fund_reports_available_asof_day": bool(funds),
            "specific_first_halt_reason_end_date_verified_asof_day": False,
            "official_full_session_exchange_state_verified_by_these_sources": False,
            "broker_executable_fill_certified": False,
            "source_mark_5_59_or_resume_6_15_safe_as_day_signal": False,
        })
    if any(r["retrospective_fund_reports_available_asof_day"] for r in days):
        raise ValueError("A retrospective fund PDF has leaked into June decisions")
    return {
        "kind": "EXP010_ORIGINAL_SOURCE_PUBLICATION_TIME_EMBARGO",
        "research_date": "2026-10-27",
        "frozen_unavailable_qlib_member_days": 139,
        "prior_original_issuer_full_interval_stock_days_unchanged": 134,
        "remaining_reason_specific_original_interval_unresolved": 5,
        "extra_independent_fund_RETROSPECTIVE_ONLY_stock_days": 5,
        "source_first_usable_sessions": starts,
        "source_provenance": sources,
        "five_decision_day_guards": days,
        "June_2021_fund_source_day_uses": sum(
            int(d["retrospective_fund_reports_available_asof_day"]) for d in days),
        "June_2021_primary_halt_start_available_asof_days": sum(
            int(d["original_exchange_halt_START_available_asof_day"]) for d in days),
        "original_fund_report_fair_value_cross_holder_mark_certified": False,
        "original_reason_specific_halt_end_2021_06_22_proven": False,
        "newly_eligible_model_fills_or_backfilled_returns": 0,
        "models_or_frozen_historical_returns_changed": False,
        "research_limit": "Only source publication embargo validated. No historical full exchange interval upgrade, official daily limit price, broker mark/auction queue, contemporaneous factor version or investment alpha.",
    }


def run(*, report_path: Path, originals_dir: Path, broker_original: Path,
        exchange_calendar: Path, out: Path) -> dict[str, Any]:
    if out.exists():
        raise FileExistsError("Will not replace an existing research audit")
    sources = verify_original_source_report(
        json.loads(report_path.read_text("utf-8")),
        originals_dir=originals_dir, broker_original=broker_original)
    calendar = pd.read_csv(exchange_calendar, header=None)[0].astype(str).tolist()
    result = build_embargo_audit(sources, calendar)
    result["derived_exp009_report_sha256"] = hashlib.sha256(
        report_path.read_bytes()).hexdigest()
    result["source_bytes_sha256_rechecked"] = True
    result["generated_utc"] = datetime.now(timezone.utc).isoformat()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")
    return result


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--exp009-original-source-report", type=Path, required=True)
    p.add_argument("--original-funds-and-exchange-dir", type=Path, required=True)
    p.add_argument("--broker-original-html", type=Path, required=True)
    p.add_argument("--exchange-calendar", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    result = run(
        report_path=a.exp009_original_source_report,
        originals_dir=a.original_funds_and_exchange_dir,
        broker_original=a.broker_original_html,
        exchange_calendar=a.exchange_calendar, out=a.out)
    print(json.dumps({
        "sources_next_session": result["source_first_usable_sessions"],
        "source_validated_from_original_bytes": result["source_bytes_sha256_rechecked"],
        "five_original_halt_end_reason_unresolved":
            result["remaining_reason_specific_original_interval_unresolved"],
        "fund_future_disclosure_leakage_count": result["June_2021_fund_source_day_uses"],
        "no_portfolio_returns_changed":
            result["models_or_frozen_historical_returns_changed"] is False,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
