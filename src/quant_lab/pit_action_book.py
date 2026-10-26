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



def verified_from_primary_issuer_pdfs(audit, *, pdf_dir):
    """Include original-PDF verified pilot events independent of vendor batch."""
    from pypdf import PdfReader
    from .pit_original_date_recovery import issuer_implementation_dates
    events=[]
    for proof in audit.get("verified_documents", []):
        if proof.get("kind") != "cash_dividend":
            continue
        if proof.get("cash_per_nominal_share_pre_tax_pdf_confirmed") is None:
            continue
        path=Path(pdf_dir)/(proof["primary_document_url"].split("/")[-1])
        # Local primary audit persisted PDFs as <key>.pdf, not URL filenames.
        name=next((x for x in audit["verified_documents"]
                   if x.get("primary_document_sha256")==proof["primary_document_sha256"]), None)
        if name is None:raise ValueError("Primary document source missing")
        if not path.is_file():
            # The audited filename is its fixed document identity.
            from .pit_primary_audit import DOCUMENTS
            key=next((x["key"] for x in DOCUMENTS
                      if x["sha256"]==proof["primary_document_sha256"]),None)
            if key is None:raise ValueError("Unrecognized pinned primary issuer PDF")
            path=Path(pdf_dir)/(key+".pdf")
        if (not path.is_file()
            or hashlib.sha256(path.read_bytes()).hexdigest()!=proof["primary_document_sha256"]):
            raise ValueError("Pinned original issuer PDF bytes changed")
        text="\\n".join(p.extract_text() or "" for p in PdfReader(path).pages)
        try:
            dated=issuer_implementation_dates(text,proof["symbol"])
        except ValueError:
            dated={}
        pay=dated.get("pay_date") if (dated.get("record_date")==proof["record_date_pdf_confirmed"]
                and dated.get("ex_date")==proof["ex_date_pdf_confirmed"]) else None
        event=create_event(
            symbol=proof["symbol"],announced=proof["official_release_calendar_date"],
            record=proof["record_date_pdf_confirmed"],
            ex=proof["ex_date_pdf_confirmed"],pay=pay,
            cash=proof["cash_per_nominal_share_pre_tax_pdf_confirmed"],
            sha=proof["primary_document_sha256"],
            url=proof["primary_document_url"],
            grade="PINNED_ORIGINAL_ISSUER_PDF_CASH_AND_DATES_DIRECT",
            date_proof="ISSUER_PRIMARY_PROOF_AND_INDEPENDENT_EXTRACT",
        )
        compact="".join(text.split())
        event["share_bonus_and_transfer_verified_zero"]=(
            "不送红股" in compact and "不以公积金转增股本" in compact)
        events.append(event)
    return events

def load_reports(batch19, batch30, recovered, pdf19, pdf30, calendar_path, primary=None, primary_pdf_dir=None):
    events = []
    for report, directory in [(batch19, pdf19), (batch30, pdf30)]:
        data = json.loads(Path(report).read_text("utf-8"))
        events.extend(verified_from_crossmatched(data, pdf_dir=directory))
    rec = json.loads(Path(recovered).read_text("utf-8"))
    events.extend(verified_from_recovered(rec, pdf_dir=pdf19))
    if (primary is None) != (primary_pdf_dir is None):
        raise ValueError("Primary audit and PDF directory must be provided together")
    if primary is not None:
        record = json.loads(Path(primary).read_text("utf-8"))
        events.extend(verified_from_primary_issuer_pdfs(
            record, pdf_dir=primary_pdf_dir
        ))
    calendar = pd.read_csv(calendar_path, header=None)[0].astype(str).tolist()
    return canonicalize(events, calendar=calendar)
