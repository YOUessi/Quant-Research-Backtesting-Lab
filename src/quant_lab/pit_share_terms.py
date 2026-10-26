"""EXP-005: hash-checked original issuer PDF evidence for zero bonus share rights.

An exact no-bonus/no-capital-transfer issuer sentence permits a **cash-only**
nominal-share assumption for that dividend. All other records remain UNKNOWN;
never set them to zero by default. Historical issuer PDFs are local, gitignored.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re

from pypdf import PdfReader


def zero_stock_bonus_sentence(issuer_text: str) -> bool:
    t=re.sub(r"\s+","",issuer_text)
    # Two explicit negative declarations in one distribution-plan context.
    # Generic market narrative or absence of stock-bonus words is insufficient.
    return bool(re.search(
        r"不送红股.{0,80}?不(?:以|进行)(?:资本)?公积金?转增股本",
        t,
    ))


def audit_zero_stock_bonus(event_book: dict, *, original_dirs: list[Path]) -> dict:
    if event_book.get("kind")!="EXP005_CANONICAL_ISSUER_CASH_ENTITLEMENT_LEDGER":
        raise ValueError("Unsupported issuer event ledger")
    bysha={}
    for directory in original_dirs:
        if not directory.is_dir():
            raise FileNotFoundError(directory)
        for path in directory.glob("*.pdf"):
            digest=hashlib.sha256(path.read_bytes()).hexdigest()
            if digest in bysha and bysha[digest]!=path:
                continue
            bysha[digest]=path
    decisions=[]
    for event in event_book["events"]:
        digest=event["issuer_pdf_sha256"]
        path=bysha.get(digest)
        if path is None or hashlib.sha256(path.read_bytes()).hexdigest()!=digest:
            raise ValueError("Missing or modified original issuer PDF "+digest)
        text="\n".join(p.extract_text() or "" for p in PdfReader(path).pages[:5])
        explicit=zero_stock_bonus_sentence(text)
        decisions.append({
            "event_id":event["event_id"],"symbol":event["symbol"],
            "ex_date":event["ex_date"],"issuer_pdf_sha256":digest,
            "zero_stock_bonus_and_capital_transfer_explicit":explicit,
            "status":(
                "ISSUER_EXPLICIT_NO_BONUS_OR_TRANSFER"
                if explicit else "NO_UNAMBIGUOUS_ZERO_STOCK_BONUS_EVIDENCE"
            ),
            "historical_issuer_rights_effective_asof_release_time_certified":False,
            "cash_dividend_payment_at_broker_verified":False,
        })
    if len(decisions)!=event_book["unique_cash_events"]:
        raise AssertionError("Unaccounted canonical issuer cash event")
    return {
        "kind":"EXP005_ORIGINAL_PDF_ZERO_STOCK_SHARE_RIGHTS_AUDIT",
        "source_issuer_events":len(decisions),
        "explicit_no_bonus_no_transfer_evidence":sum(
            x["zero_stock_bonus_and_capital_transfer_explicit"]
            for x in decisions
        ),
        "zero_share_rights_unknown":sum(
            not x["zero_stock_bonus_and_capital_transfer_explicit"]
            for x in decisions
        ),
        "does_not_establish_positive_stock_bonus_split_rights":True,
        "cash_ledger_full_historical_company_action_certified":False,
        "events":decisions,
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--ledger",type=Path,required=True)
    p.add_argument("--issuer-dirs",nargs="+",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    opts=p.parse_args()
    src=json.loads(opts.ledger.read_text("utf-8"))
    out=audit_zero_stock_bonus(src,original_dirs=opts.issuer_dirs)
    if opts.out.exists():
        raise FileExistsError("Never overwrite PDF rights status report")
    opts.out.parent.mkdir(parents=True,exist_ok=True)
    opts.out.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({
        k:v for k,v in out.items() if k in (
            "source_issuer_events",
            "explicit_no_bonus_no_transfer_evidence",
            "zero_share_rights_unknown",
        )
    },ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
