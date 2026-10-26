"""Recover nominal cash and record/ex/payment dates directly from issuer PDFs.

The auditor works *offline* against the issuer-PDF bytes whose SHA256 was
already recorded. Extraction is deliberately narrower than a general Chinese
PDF parser. Ambiguous amounts/dates are retained but NOT booked as cash.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re

import pandas as pd
from pypdf import PdfReader

from .pit_official_batch import (
    compact,extract_cash_candidates_per_share,
    extract_explicit_pretax_cash_per_share,
)

SSE_TABLE = re.compile(
    r"(?:A股|Ａ股)"
    r"(20\d{2}/\d{1,2}/\d{1,2})[－-]"
    r"(20\d{2}/\d{1,2}/\d{1,2})"
    r"(20\d{2}/\d{1,2}/\d{1,2})"
)
SZ_REGISTER_EX = re.compile(
    r"本次权益分派股权登记日为[:：]"
    r"(20\d{2}年\d{1,2}月\d{1,2}日)[，,]"
    r"除权除息日为[:：](20\d{2}年\d{1,2}月\d{1,2}日)"
)
SZ_CASH_PAY = re.compile(
    r"现金红利将于(20\d{2}年\d{1,2}月\d{1,2}日)"
)


def normalize_date(date: str) -> str:
    txt=date.replace("年","-").replace("月","-").replace("日","")
    d=pd.Timestamp(txt.replace("/", "-")).normalize()
    return d.date().isoformat()


def issuer_implementation_dates(text: str, symbol: str) -> dict:
    """Verified literal issuer-PDF date extraction; no datetime guesses."""
    c=compact(text)
    if symbol.startswith("SH"):
        matches=SSE_TABLE.findall(c)
        possible=[tuple(normalize_date(x) for x in row) for row in matches]
        possible=sorted(set(possible))
        if len(possible)!=1:
            return {"record_date":None,"ex_date":None,"pay_date":None,
                    "status":"SSE_TABLE_MISSING_OR_AMBIGUOUS"}
        record,ex,pay=possible[0]
    elif symbol.startswith("SZ"):
        found=sorted(set(
            (normalize_date(a),normalize_date(b))
            for a,b in SZ_REGISTER_EX.findall(c)
        ))
        if len(found)!=1:
            return {"record_date":None,"ex_date":None,"pay_date":None,
                    "status":"SZ_RECORD_EX_MISSING_OR_AMBIGUOUS"}
        record,ex=found[0]
        pays=sorted(set(normalize_date(v) for v in SZ_CASH_PAY.findall(c)))
        pay=pays[0] if len(pays)==1 else None
    else:
        raise ValueError("Unsupported exchange")
    if record>=ex:
        raise ValueError("Issuer record/ex chronology invalid")
    if pay and pay<ex:
        raise ValueError("Issuer payment precedes ex date")
    return {
        "record_date":record,"ex_date":ex,"pay_date":pay,
        "status":"PDF_ISSUER_ORIGINAL_DATE_LITERAL_CONFIRMED",
    }


def recover_from_batch(original: dict, source_dir: Path,
                       *, only_missing_vendor: bool = True) -> dict:
    records=[]
    for event in original["documents"]:
        if only_missing_vendor and event["thirdparty_same_day_events"]!=0:
            continue
        symbol=event["symbol"]
        pub=event["official_notice_day"]
        name=(f"{symbol}_{pub}_{event['announcement_id']}.pdf")
        pdf=source_dir/"issuer_pdfs"/name
        if not pdf.is_file():
            raise FileNotFoundError(pdf)
        raw=pdf.read_bytes()
        digest=hashlib.sha256(raw).hexdigest()
        if digest!=event["issuer_pdf_sha256"]:
            raise ValueError("Original historical PDF source differs from first audit")
        text="\n".join(x.extract_text() or "" for x in PdfReader(pdf,strict=False).pages[:4])
        if symbol[2:] not in compact(text):
            raise ValueError("Issuer PDF security code mismatch")
        dates=issuer_implementation_dates(text,symbol)
        if (dates["record_date"] and
            not (pub < dates["record_date"] < dates["ex_date"])):
            raise ValueError("Announcement published after registration/ex date")
        gross=extract_explicit_pretax_cash_per_share(text)
        all_cash=extract_cash_candidates_per_share(text)
        if len(gross)==1:
            amount=gross[0]
            amount_grade="PRIMARY_PDF_EXPLICIT_TAX_INCLUSIVE"
        elif not gross and len(all_cash)==1:
            amount=all_cash[0]
            amount_grade="PRIMARY_PDF_SINGLE_CASH_VALUE_TAX_STATUS_UNCERTAIN"
        else:
            amount=None
            amount_grade="POSSIBLE_NET_OR_MULTIPLE_AMOUNTS_UNRESOLVED"
        if amount is not None and dates["ex_date"]:
            status=(
                "PDF_DATES_AND_EXPLICIT_GROSS_CASH_CONFIRMED"
                if len(gross)==1 else
                "PDF_DATES_AND_SINGLE_CASH_TAX_STATUS_UNCERTAIN"
            )
        elif amount is None:
            status="PDF_DATES_PRESENT_CASH_AMBIGUOUS"
        else:
            status="PDF_CASH_AMOUNT_PRESENT_DATES_UNRESOLVED"
        records.append({
            "symbol":symbol,
            "published_calendar_day":pub,
            "earliest_available_strategy_day":"following_exchange_session",
            "issuer_pdf_sha256":digest,
            "issuer_pdf_url":event["issuer_pdf_url"],
            "original_batch_announcement_id":event["announcement_id"],
            "cash_pre_tax_per_nominal_share_recovered":amount if len(gross)==1 else None,
            "cash_per_nominal_share_tax_context_unconfirmed":(
                amount if amount_grade.endswith("UNCERTAIN") and amount is not None else None
            ),
            "gross_cash_context":amount_grade,
            "all_possible_cash_amounts_per_share":all_cash,
            "record_date":dates["record_date"],
            "ex_date":dates["ex_date"],
            "payment_date":dates["pay_date"],
            "status":status,
            "full_dividend_share_bonus_split_entitlement_verified":False,
            "issuer_original_date_and_amount_read_from_same_pdf":True,
            "source_pdf_hash_reverified":True,
            "does_not_verify_broker_cash_posting":True,
            "does_not_certify_market_order_fill":True,
        })
    return {
        "kind":"ISSUER_ORIGINAL_MISSING_VENDOR_CORPORATE_ACTION_DATE_RECOVERY",
        "source":"Unchanged original CNINFO PDF bytes from audited batch",
        "n_events_from_missing_thirdparty_sources":len(records),
        "n_unique_original_cash_and_dates_explicit_gross":sum(
            e["status"]=="PDF_DATES_AND_EXPLICIT_GROSS_CASH_CONFIRMED"
            for e in records
        ),
        "n_cash_single_tax_context_uncertain":sum(
            e["status"]=="PDF_DATES_AND_SINGLE_CASH_TAX_STATUS_UNCERTAIN"
            for e in records
        ),
        "n_amount_unresolved":sum(
            e["status"]=="PDF_DATES_PRESENT_CASH_AMBIGUOUS"
            for e in records
        ),
        "historical_vendor_snapshot_available":False,
        "all_cash_paid_to_broker_verified":False,
        "corporate_action_correction_history_certified":False,
        "issuer_cash_dates_directly_parsed_events":records,
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--issuer-batch",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    args=p.parse_args()
    batch=json.loads(args.issuer_batch.read_text("utf-8"))
    report=recover_from_batch(batch,args.issuer_batch.parent)
    if args.out.exists():
        raise FileExistsError(args.out)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps({
        k:report[k] for k in (
            "n_events_from_missing_thirdparty_sources",
            "n_unique_original_cash_and_dates_explicit_gross",
            "n_cash_single_tax_context_uncertain",
            "n_amount_unresolved",
        )
    },indent=2,ensure_ascii=False))


if __name__=="__main__":
    main()
