"""EXP-006: original-issuer stock bonus / capitalization transfer rights.

Only original SHA256-verified implementation PDFs are parsed; 'not mentioned'
never means zero. Separate send-bonus shares from capitalization transfers
on EX date; multiply nominal shares by (1+bonus/10+transfer/10). Keep unknown
rights as unresolved. Aggregator stock ratios are a secondary crosscheck only.

This module neither proves historical source vintages nor actual broker credit.
"""
from __future__ import annotations

import argparse
from collections import Counter
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re

from pypdf import PdfReader


def clean(text: str) -> str:
    return re.sub(r"\s+", "", text).translate(str.maketrans(
        "０１２３４５６７８９．ＡＢ", "0123456789.AB"
    ))


# Deliberately bound patterns to explicit issuer-per-ten-share expressions;
# '送股'/‘转增’ in generic risk disclosures has no automatic numerical value.
TRANSFER = re.compile(r"每10股(?:以资本公积金?)?(?:转增|转赠)([0-9]+(?:\.[0-9]+)?)股")
TRANSFER_ALTERNATE = re.compile(
    r"(?:每10股.{0,12}?)?以资本公积金向全体股东每10股转增([0-9]+(?:\.[0-9]+)?)股"
)
BONUS = re.compile(r"每10股(?:送|派送)([0-9]+(?:\.[0-9]+)?)股")
EXPLICIT_NO_BONUS = re.compile(r"不送(?:红)?股")
EXPLICIT_NO_TRANSFER = re.compile(
    r"(?:不以(?:资本)?公积金?转增股本|不进行(?:资本)?公积金?转增股本|"
    r"亦不进行(?:资本)?公积金?转增股本|不转增股本)"
)


def _values(text: str, patterns: tuple[re.Pattern,...]) -> list[float]:
    values = []
    for pattern in patterns:
        for match in pattern.finditer(text):
            v = float(match.group(1))
            if not 0 <= v <= 100:
                raise ValueError("Implausible per-ten-share issuer amount")
            values.append(round(v, 9))
    return sorted(set(values))


def extract_share_terms(text: str) -> dict:
    """Parser outputs evidence states; never infer unknown-rights as zero.

    Multiple DIFFERENT issuer amounts (e.g. revised plans) need manual
    reconciliation to implementation PDF, even if a third-party value matches.
    """
    t = clean(text)
    transfer = _values(t, (TRANSFER, TRANSFER_ALTERNATE))
    bonus = _values(t, (BONUS,))
    no_bonus = bool(EXPLICIT_NO_BONUS.search(t))
    no_transfer = bool(EXPLICIT_NO_TRANSFER.search(t))
    # A positive and a negative statement may refer to old vs amended plan.
    # A single current PDF alone cannot determine priority; fail closed.
    bonus_conflict = (len(bonus) > 1 or (bonus and no_bonus))
    transfer_conflict = (len(transfer) > 1 or (transfer and no_transfer))
    if bonus_conflict:
        bonus_value = None
        bonus_status = "CONFLICTING_BONUS_SOURCE_STATEMENTS_HOLD"
    elif bonus:
        bonus_value = bonus[0] / 10.0
        bonus_status = "EXPLICIT_ISSUER_PER_TEN_BONUS"
    elif no_bonus:
        bonus_value = 0.0
        bonus_status = "EXPLICIT_ISSUER_ZERO_BONUS"
    else:
        bonus_value = None
        bonus_status = "BONUS_UNCONFIRMED"
    if transfer_conflict:
        transfer_value = None
        transfer_status = "CONFLICTING_CAPITAL_TRANSFER_STATEMENTS_HOLD"
    elif transfer:
        transfer_value = transfer[0] / 10.0
        transfer_status = "EXPLICIT_ISSUER_PER_TEN_TRANSFER"
    elif no_transfer:
        transfer_value = 0.0
        transfer_status = "EXPLICIT_ISSUER_ZERO_TRANSFER"
    else:
        transfer_value = None
        transfer_status = "TRANSFER_UNCONFIRMED"
    both_known = bonus_value is not None and transfer_value is not None
    return {
        "bonus_per_ten_distinct_candidates": bonus,
        "transfer_per_ten_distinct_candidates": transfer,
        "bonus_ratio_per_nominal_share": bonus_value,
        "transfer_ratio_per_nominal_share": transfer_value,
        "bonus_source_status": bonus_status,
        "transfer_source_status": transfer_status,
        "full_nominal_share_multiplier_issuer_verified": (
            1.0 + bonus_value + transfer_value if both_known else None
        ),
        "known_complete": both_known,
        "known_positive_stock_rights": bool(
            (bonus_value is not None and bonus_value > 0)
            or (transfer_value is not None and transfer_value > 0)
        ),
        "historical_factor_release_time_certified": False,
        "broker_credit_of_bonus_shares_certified": False,
    }


def inspect_all_cash_events(cash_ledger: dict, *, pdf_dirs: list[Path],
                            vendor_dir: Path | None=None) -> dict:
    if cash_ledger.get("kind")!="EXP005_CANONICAL_ISSUER_CASH_ENTITLEMENT_LEDGER":
        raise ValueError("Unexpected input; require original source-proven event ledger")
    pdfbyhash={}
    for root in pdf_dirs:
        for file in root.glob("*.pdf"):
            digest=hashlib.sha256(file.read_bytes()).hexdigest()
            pdfbyhash[digest]=file
    examined=[]
    for event in cash_ledger["events"]:
        h=event["issuer_pdf_sha256"]
        path=pdfbyhash.get(h)
        if path is None:
            raise ValueError("Cannot find original PDF SHA for "+event["event_id"])
        txt="\n".join(p.extract_text() or "" for p in PdfReader(path).pages[:5])
        if event["symbol"][2:] not in clean(txt):
            raise ValueError("Issuer original PDF stock code mismatch")
        decision=extract_share_terms(txt)
        matched=[]
        if vendor_dir is not None:
            src=vendor_dir/(event["symbol"]+".json")
            if src.is_file():
                body=json.loads(src.read_text(encoding="utf-8"))
                raw=body.get("raw_eastmoney_records") or []
                matched=[r for r in raw
                         if str(r.get("EX_DIVIDEND_DATE") or "")[:10]==event["ex_date"]]
        if len(matched)>1:
            decision["vendor_status"]="MORE_THAN_ONE_EX_DATE_AGGREGATOR_EVENT_HOLD"
        elif len(matched)==1:
            row=matched[0]
            it=row.get("IT_RATIO")
            bs=row.get("BONUS_RATIO")
            def match_known(source, observed):
                if source is None:
                    return "ISSUER_UNKNOWN"
                if observed in (None, ""):
                    return "VENDOR_FIELD_MISSING_NOT_PROOF_OF_ZERO"
                return ("MATCH" if abs(float(observed)/10-float(source))<1e-7
                        else "CONFLICT")
            decision["vendor_status"]="CURRENT_SNAPSHOT_NOT_HISTORICALLY_VERSIONED"
            decision["independent_transfer_ratio_crosscheck"]=match_known(
                decision["transfer_ratio_per_nominal_share"],it)
            decision["independent_stock_bonus_crosscheck"]=match_known(
                decision["bonus_ratio_per_nominal_share"],bs)
        else:
            decision["vendor_status"]="SOURCE_HISTORY_MISSING_FOR_EVENT"
        examined.append({
            "event_id":event["event_id"],"symbol":event["symbol"],
            "ex_date":event["ex_date"],
            "announcement_calendar_day":event["announcement_day"],
            "issuer_pdf_sha256":h,"issuer_pdf_url":event["issuer_pdf_url"],
            **decision,
        })
    status=Counter(
        "POSITIVE_COMPLETE" if r["known_complete"] and r["known_positive_stock_rights"]
        else ("CASH_ONLY_EXPLICIT_ZERO" if r["known_complete"]
              else "PARTIAL_OR_UNKNOWN")
        for r in examined
    )
    return {
        "kind":"EXP006_ORIGINAL_ISSUER_STOCK_DISTRIBUTION_AND_TRANSFER_AUDIT",
        "n_verified_original_cash_events":len(examined),
        "nominal_share_rights_fully_known":sum(x["known_complete"] for x in examined),
        "nominal_share_rights_incomplete":sum(not x["known_complete"] for x in examined),
        "known_positive_stock_distribution_events":sum(x["known_positive_stock_rights"] for x in examined),
        "fully_known_positive_share_distribution_events":status["POSITIVE_COMPLETE"],
        "known_cash_only_explicit_no_distribution":status["CASH_ONLY_EXPLICIT_ZERO"],
        "historical_issuer_pdf_sha_verified_all":True,
        "entitlements_only_no_broker_cash_or_share_credit":True,
        "historical_factor_release_vintages_available":False,
        "audit":examined,
    }


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--cash-ledger",type=Path,required=True)
    parser.add_argument("--issuer-pdfs",type=Path,nargs="+",required=True)
    parser.add_argument("--aggregator-dir",type=Path)
    parser.add_argument("--out",type=Path,required=True)
    a=parser.parse_args()
    cash=json.loads(a.cash_ledger.read_text("utf-8"))
    audit=inspect_all_cash_events(cash,pdf_dirs=a.issuer_pdfs,
                                  vendor_dir=a.aggregator_dir)
    if a.out.exists():raise FileExistsError("Never overwrite prior rights audit")
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(audit,ensure_ascii=False,indent=2)+"\n",
                     encoding="utf-8")
    print(json.dumps({k:v for k,v in audit.items()
                      if k.startswith("n_") or "events" in k},indent=2))


if __name__=="__main__":
    main()
