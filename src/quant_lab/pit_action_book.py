"""EXP-005: PDF-verified nominal cash events; no Qlib adjusted-price double count.

A publication calendar date is NOT a historical intraday release timestamp.
Never apply a cash dividend to a backtest already using Qlib adjusted returns.
"""
from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path

import pandas as pd


def date(x):
    if not x:
        raise ValueError("Missing essential date")
    return pd.Timestamp(x).date().isoformat()


def create_event(*, symbol, announced, record, ex, cash, sha, url,
                 grade, pay=None, date_proof="issuer_date_literal"):
    announced, record, ex = date(announced), date(record), date(ex)
    pay = date(pay) if pay else None
    if not announced < record < ex or (pay and pay < ex):
        raise ValueError(f"Impossible announcement/record/ex/pay dates: {symbol}")
    cash = float(cash)
    if not 0 < cash < 200:
        raise ValueError("Invalid gross cash per nominal share")
    if len(sha) != 64 or not url.startswith("https://static.cninfo.com.cn/finalpage/"):
        raise ValueError("Original issuer PDF proof is missing")
    identity = f"{symbol}|{record}|{ex}|cash_dividend"
    return {
        "event_id": hashlib.sha256(identity.encode()).hexdigest()[:24],
        "identity": identity, "symbol": symbol,
        "announcement_day": announced, "record_date": record,
        "ex_date": ex, "payment_date": pay,
        "gross_cash_per_nominal_share": cash,
        "issuer_pdf_sha256": sha, "issuer_pdf_url": url,
        "evidence_grade": grade, "date_proof": date_proof,
        "earliest_usable_exchange_day": None,
        "share_bonus_and_transfer_verified_zero": False,
        "tax_or_broker_cash_posting_verified": False,
        "publisher_factor_historical_vintage_verified": False,
        "intraday_announcement_time_known": False,
    }


def _read_and_verify_pdf(source_dir, item, *, recovered=False):
    if recovered:
        name = (f"{item['symbol']}_{item['published_calendar_day']}_"
                f"{item['original_batch_announcement_id']}.pdf")
        target_sha = item["issuer_pdf_sha256"]
    else:
        name = (f"{item['symbol']}_{item['official_notice_day']}_"
                f"{item['announcement_id']}.pdf")
        target_sha = item["issuer_pdf_sha256"]
    file = Path(source_dir) / name
    if not file.is_file() or hashlib.sha256(file.read_bytes()).hexdigest() != target_sha:
        raise ValueError(f"PDF changed or absent: {name}")
    return file


def verified_from_crossmatched(audit, *, pdf_dir):
    if audit.get("kind") != "OFFLINE_RECHECK_OF_PINNED_ISSUER_PDF_BYTES":
        raise ValueError("Unexpected crossmatch input")
    events = []
    for row in audit["documents"]:
        if row["status"] != "PDF_CASH_MATCHED_TO_THIRDPARTY":
            continue
        if not row["issuer_pdf_ex_record_date_literals_both_present"]:
            raise ValueError("Previously crossmatched date literal is absent")
        _read_and_verify_pdf(pdf_dir, row)
        events.append(create_event(
            symbol=row["symbol"], announced=row["official_notice_day"],
            record=row["thirdparty_record_date"], ex=row["thirdparty_ex_date"],
            pay=None, cash=row["cash_per_share_verified"],
            sha=row["issuer_pdf_sha256"], url=row["issuer_pdf_url"],
            grade="ISSUER_PDF_GROSS_CASH_AND_VENDOR_DATES_CROSSMATCHED",
            date_proof="ISSUER_PDF_RECORD_AND_EX_DATE_LITERALS",
        ))
    return events


def verified_from_recovered(audit, *, pdf_dir):
    if audit.get("kind") != "ISSUER_ORIGINAL_MISSING_VENDOR_CORPORATE_ACTION_DATE_RECOVERY":
        raise ValueError("Unexpected recovered original issuer input")
    events = []
    for row in audit["issuer_cash_dates_directly_parsed_events"]:
        if row["status"] != "PDF_DATES_AND_EXPLICIT_GROSS_CASH_CONFIRMED":
            continue
        _read_and_verify_pdf(pdf_dir, row, recovered=True)
        events.append(create_event(
            symbol=row["symbol"], announced=row["published_calendar_day"],
            record=row["record_date"], ex=row["ex_date"],
            pay=row["payment_date"],
            cash=row["cash_pre_tax_per_nominal_share_recovered"],
            sha=row["issuer_pdf_sha256"], url=row["issuer_pdf_url"],
            grade="ISSUER_PDF_ORIGINAL_GROSS_CASH_AND_DATES_NO_VENDOR",
            date_proof="REEXTRACTED_FROM_ORIGINAL_ISSUER_PDF",
        ))
    return events


def canonicalize(events, *, calendar):
    """Conflicting payout terms HOLD; duplicate publications book once."""
    sessions = sorted({date(x) for x in calendar})
    by_identity = defaultdict(list)
    for event in events:
        by_identity[event["identity"]].append(event)
    accepted, held, duplicate = [], [], []
    for key, group in sorted(by_identity.items()):
        different = {round(x["gross_cash_per_nominal_share"], 9) for x in group}
        if len(different) != 1:
            held.append({"identity": key, "reason": "CONFLICTING_PAYOUT_HOLD",
                         "amounts": sorted(different)})
            continue
        group = sorted(group, key=lambda x: (x["announcement_day"], x["issuer_pdf_sha256"]))
        chosen = dict(group[0])
        usable = next((d for d in sessions if d > chosen["announcement_day"]), None)
        if usable is None or usable > chosen["record_date"]:
            held.append({"identity": key, "reason": "PIT_AVAILABILITY_MISSING"})
            continue
        chosen["earliest_usable_exchange_day"] = usable
        chosen["all_pdf_sha256s"] = sorted({g["issuer_pdf_sha256"] for g in group})
        chosen["all_announcement_days"] = sorted({g["announcement_day"] for g in group})
        if len(group) > 1:
            duplicate.append({"identity": key, "source_count": len(group)})
        accepted.append(chosen)
    return {
        "kind": "EXP005_CANONICAL_ISSUER_CASH_ENTITLEMENT_LEDGER",
        "candidate_source_events": len(events),
        "unique_cash_events": len(accepted),
        "contradictory_identities_held": len(held),
        "duplicate_groups_booked_once": len(duplicate),
        "events": accepted, "held": held, "duplicates": duplicate,
        "stock_bonus_split_rights_verified_full_universe": False,
        "historical_factor_publication_vintages_available": False,
        "broker_payment_or_trade_fill_verified": False,
        "must_never_add_to_qlib_adjusted_returns": True,
    }


def load_reports(batch19, batch30, recovered, pdf19, pdf30, calendar_path):
    events = []
    for report, directory in [(batch19, pdf19), (batch30, pdf30)]:
        data = json.loads(Path(report).read_text("utf-8"))
        events.extend(verified_from_crossmatched(data, pdf_dir=directory))
    rec = json.loads(Path(recovered).read_text("utf-8"))
    events.extend(verified_from_recovered(rec, pdf_dir=pdf19))
    calendar = pd.read_csv(calendar_path, header=None)[0].astype(str).tolist()
    return canonicalize(events, calendar=calendar)
