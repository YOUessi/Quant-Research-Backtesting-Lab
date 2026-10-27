"""EXP015: immutable original-issuer source time and incomplete-rights gate.

This independently rehashes all 89 locally archived original announcement PDFs,
the existing EXP014 36/53 catalog, and the frozen historical Qlib calendar. A
day-only publication date is usable no earlier than the NEXT exchange session.
It is not a certified intraday timestamp, correction history, broker share
delivery, exact limit price, auction fill, or investible backtest validation.
"""
from __future__ import annotations

import argparse
import bisect
from decimal import Decimal, InvalidOperation
import hashlib
from io import BytesIO
import json
from pathlib import Path
import re

from pypdf import PdfReader

CATALOG_SHA256 = "f47b34380951ea998f9c494687d2d8f0f2355cea4bfd0ef000bf5eece6ea19d2"
CALENDAR_SHA256 = "245bb32a907fe942c1a4c3671e35c0c5f7ecbb73b5aae90bbbc4ff7e7e83ae46"
CATALOG_KIND = "EXP014_SUPPLEMENTAL_ISSUER_CURRENT_ZERO_RIGHTS_CATALOG"
DATE = re.compile(r"20\d{2}-\d{2}-\d{2}\Z")
DIGEST = re.compile(r"[0-9a-f]{64}\Z")
ORIGINAL_URL = re.compile(
    r"https://static\.cninfo\.com\.cn/finalpage/(20\d{2}-\d{2}-\d{2})/\d+\.PDF\Z"
)


def exact_day(day: str) -> str:
    from datetime import date
    if not isinstance(day, str) or not DATE.fullmatch(day):
        raise ValueError("Invalid ISO source or trading day")
    try:
        if date.fromisoformat(day).isoformat() != day:
            raise ValueError("Not a real calendar day")
    except (TypeError, ValueError) as exc:
        raise ValueError("Invalid calendar day") from exc
    return day


def parse_calendar(source: bytes) -> list[str]:
    """Pinned Qlib exchange calendar; do not improvise weekends/holidays."""
    try:
        days = [exact_day(s) for s in source.decode("utf-8").splitlines()]
    except UnicodeError as exc:
        raise ValueError("Calendar is not UTF-8") from exc
    if len(days) < 250 or days != sorted(set(days)):
        raise ValueError("Historical exchange calendar must be sorted and unique")
    return days


def right_number(value: object, name: str) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError(f"Boolean cannot establish issuer {name}")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError(f"Invalid issuer {name}") from exc
    if not number.is_finite() or number < 0:
        raise ValueError(f"Nonfinite or negative issuer {name}")
    return number


def assess_event(row: dict, calendar: list[str]) -> dict:
    """Validate an immutable event without upgrading a missing right to zero."""
    symbol = row.get("symbol")
    if not isinstance(symbol, str) or not re.fullmatch(r"(?:SH|SZ)\d{6}", symbol):
        raise ValueError("Invalid A-stock identity")
    announcement = exact_day(row.get("announcement_day"))
    earliest = exact_day(row.get("earliest_usable_exchange_day"))
    record = exact_day(row.get("record_date"))
    ex = exact_day(row.get("ex_date"))
    url = row.get("issuer_original_pdf_url")
    match = ORIGINAL_URL.fullmatch(url) if isinstance(url, str) else None
    if match is None or match.group(1) != announcement:
        raise ValueError("Original issuer URL and dated publication-day identity mismatch")
    original_sha = row.get("issuer_original_pdf_sha256")
    if not isinstance(original_sha, str) or DIGEST.fullmatch(original_sha) is None:
        raise ValueError("Issuer full original PDF SHA256 absent")
    pos = bisect.bisect_right(calendar, announcement)
    if pos == len(calendar) or pos == 0 or calendar[pos] != earliest:
        raise ValueError("Original publication embargo must equal next exchange session")
    if record not in calendar or ex not in calendar:
        raise ValueError("Issuer record/ex date not an exchange session")
    if not announcement < earliest <= record < ex:
        raise ValueError("Invalid original issuer publication / effective-day sequence")
    payment = row.get("scheduled_cash_payment_day")
    if payment is not None and exact_day(payment) < ex:
        raise ValueError("Issuer payment schedule predates ex-day")
    bonus = right_number(row.get("bonus_shares_per_old_share"), "bonus")
    transfer = right_number(row.get("capital_transfer_shares_per_old_share"), "transfer")
    multiplier = right_number(row.get("full_new_nominal_share_multiplier"), "multiplier")
    complete = bonus is not None and transfer is not None
    if row.get("complete_rights_supported_by_issuer_original") is not complete:
        raise ValueError("Source-completeness flag contradicts missing stock rights")
    if complete:
        if multiplier is None or abs(multiplier - (Decimal(1) + bonus + transfer)) > Decimal("1e-9"):
            raise ValueError("Source-backed nominal multiplier is inconsistent")
    elif multiplier is not None:
        raise ValueError("Unknown stock right cannot yield numeric multiplier")
    cash = right_number(row.get("gross_cash_per_old_nominal_share"), "cash")
    if cash is None or cash <= 0:
        raise ValueError("Gross cash rights must have positive original-source evidence")
    if row.get("positive_stock_rights") is not bool((bonus or 0) > 0 or (transfer or 0) > 0):
        raise ValueError("Issuer positive-rights status contradicts evidence")
    for forbidden in (
        "original_publication_intraday_time_certified",
        "historical_factor_vintage_available",
        "broker_share_delivery_and_cash_payment_verified",
    ):
        if row.get(forbidden) is not False:
            raise ValueError(f"Unverified external evidence incorrectly promoted: {forbidden}")
    if row.get("cash_rights_nominal_not_qlib_adjusted") is not True:
        raise ValueError("Source cash entitlement cannot use adjusted total-return prices")
    # Three source-clock decision probes: the session before source availability,
    # the first eligible session and the record session.
    # An eligible source never implies the user held stock or could execute it.
    previous = calendar[pos - 1]
    probes = []
    for decision in (previous, earliest, record):
        usable = decision >= earliest
        probes.append({
            "decision_session": decision,
            "issuer_pdf_known_from_day_only_notice_asof": usable,
            "both_stock_rights_known_asof": usable and complete,
            "nominal_new_share_multiplier_asof": (
                str(multiplier) if usable and complete else None
            ),
            "broker_sellable_share_quantity_proven": False,
            "actual_cash_credit_proven": False,
            "historical_factor_version_proven": False,
            "price_limit_and_auction_fill_proven": False,
        })
    if probes[0]["issuer_pdf_known_from_day_only_notice_asof"] or (
        probes[0]["nominal_new_share_multiplier_asof"] is not None
    ) or (not complete and any(p["nominal_new_share_multiplier_asof"] is not None
                                for p in probes)):
        raise AssertionError("Historical future source or unknown rights leaked into mark")
    return {
        "event_id": row["event_id"], "symbol": symbol,
        "original_ex_day": ex, "publication_day": announcement,
        "first_usable_exchange_day": earliest, "record_day": record,
        "original_issuer_pdf_url": url, "original_issuer_pdf_sha256": original_sha,
        "issuer_stock_rights_complete": complete,
        "bonus_rights_missing": bonus is None,
        "capital_transfer_rights_missing": transfer is None,
        "pre_source_source_embargo_active": True,
        "intraday_announcement_timestamp_verified": False,
        "historical_amendment_history_verified": False,
        "source_day_decision_probes": probes,
    }


def check_original_first_page(row: dict, pdf_bytes: bytes) -> None:
    """Hash is checked by caller; first page independently confirms A-stock."""
    if not pdf_bytes.startswith(b"%PDF"):
        raise ValueError("Original issuer evidence is not PDF")
    reader = PdfReader(BytesIO(pdf_bytes), strict=False)
    if not reader.pages:
        raise ValueError("Original issuer PDF has no pages")
    title = reader.pages[0].extract_text() or ""
    if (row["symbol"][2:] not in title or "公告" not in title
            or not any(term in title for term in ("分红", "派息", "权益分派"))):
        raise ValueError("Original PDF first-page A-stock/issuer announcement identity absent")


def verify(*, catalog_bytes: bytes, calendar_bytes: bytes,
           pdf_dirs: list[Path]) -> dict:
    if hashlib.sha256(catalog_bytes).hexdigest() != CATALOG_SHA256:
        raise ValueError("Immutable EXP014 rights catalog full SHA256 mismatch")
    if hashlib.sha256(calendar_bytes).hexdigest() != CALENDAR_SHA256:
        raise ValueError("Historical exchange calendar full SHA256 mismatch")
    catalog = json.loads(catalog_bytes)
    if (catalog.get("kind") != CATALOG_KIND
            or catalog.get("issuer_events") != 89
            or catalog.get("fully_verified_nominal_share_rights") != 36
            or catalog.get("unknown_share_rights") != 53
            or catalog.get("exp014_added_exact_original_source_proofs") != 4):
        raise ValueError("Wrong frozen EXP014 complete/unknown rights catalog")
    rows = catalog.get("events", [])
    if len(rows) != 89 or len({r["event_id"] for r in rows}) != 89 or (
        len({(r["symbol"], r["ex_date"]) for r in rows}) != 89
    ):
        raise ValueError("Duplicate or missing 89 issuer event identities")
    calendar = parse_calendar(calendar_bytes)
    files: dict[str, Path] = {}
    for directory in pdf_dirs:
        if not directory.is_dir():
            raise FileNotFoundError(f"Missing locally archived issuer PDF directory: {directory}")
        for path in directory.glob("*.pdf"):
            data = path.read_bytes()
            files[hashlib.sha256(data).hexdigest()] = path
    summaries = []
    for row in rows:
        item = assess_event(row, calendar)
        digest = item["original_issuer_pdf_sha256"]
        if digest not in files:
            raise FileNotFoundError("Missing complete-SHA original issuer PDF for " + item["event_id"])
        pdf = files[digest].read_bytes()
        if hashlib.sha256(pdf).hexdigest() != digest:
            raise ValueError("Original PDF changed during SHA scan")
        check_original_first_page(row, pdf)
        summaries.append(item)
    total_complete = sum(item["issuer_stock_rights_complete"] for item in summaries)
    if total_complete != 36 or len(summaries) - total_complete != 53:
        raise AssertionError("Source rights completeness counts changed without proof")
    return {
        "kind": "EXP015_SHA_PINNED_ISSUER_RIGHTS_SOURCE_PUBLICATION_GATE",
        "catalog_original_full_sha256": CATALOG_SHA256,
        "historical_qlib_exchange_calendar_full_sha256": CALENDAR_SHA256,
        "calendar_origin": "locally_archived_qlib_calendar_not_independent_official_exchange_timestamp",
        "original_issuer_pdfs_full_SHA256_rechecked": len(summaries),
        "first_page_A_stock_issuer_identity_checked": len(summaries),
        "events_exact_next_session_publication_embargo_verified": len(summaries),
        "source_rights_complete": total_complete,
        "source_rights_still_incomplete": len(summaries) - total_complete,
        "unresolved_missing_both_categories": sum(
            e["bonus_rights_missing"] and e["capital_transfer_rights_missing"]
            for e in summaries),
        "unresolved_missing_one_category": sum(
            e["bonus_rights_missing"] ^ e["capital_transfer_rights_missing"]
            for e in summaries),
        "publication_time_decision_probes_checked": 3 * len(summaries),
        "all_pre_publication_probes_censored": all(
            e["source_day_decision_probes"][0]["nominal_new_share_multiplier_asof"] is None
            for e in summaries
        ),
        "unresolved_rights_after_publication_still_censored": all(
            p["nominal_new_share_multiplier_asof"] is None
            for e in summaries if not e["issuer_stock_rights_complete"]
            for p in e["source_day_decision_probes"]
        ),
        "new_completed_issuer_events": 0,
        "original_source_files_downloaded_this_run": False,
        "original_event_catalog_or_raw_data_rewritten": False,
        "original_intraday_publication_times_proven": False,
        "authoritative_issuer_revision_history_proven": False,
        "broker_cash_stock_credit_or_actual_orders_proven": False,
        "official_daily_limit_prices_or_auction_queues_proven": False,
        "fresh_independent_holdout_or_investment_alpha_proven": False,
        "events": summaries,
    }


def run(catalog: Path, calendar: Path, pdf_dirs: list[Path], out: Path) -> dict:
    if out.exists():
        raise FileExistsError("Refusing to overwrite an earlier research result")
    report = verify(catalog_bytes=catalog.read_bytes(),
                    calendar_bytes=calendar.read_bytes(), pdf_dirs=pdf_dirs)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--calendar", type=Path, required=True)
    parser.add_argument("--issuer-pdfs", type=Path, nargs="+", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.catalog, args.calendar, args.issuer_pdfs, args.out)
    print(json.dumps({k: v for k, v in result.items() if k != "events"},
                     indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
