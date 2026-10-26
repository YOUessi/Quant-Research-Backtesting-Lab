"""EXP-007: reconcile audited issuer cash/right events with conservative capital balance.

Separates (1) explicit original PDF zero/positive rights,
(2) complementary zero derived from same original issuer PDF company-capital
conservation, and (3) unverified rights (do NOT assume zero).

Never merge Qlib-adjusted returns into nominal-share/cash bookkeeping.
Original cash events and source SHA links remain unchanged.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def assemble(cash: dict, rights: dict, balance: dict) -> dict:
    if cash.get("kind")!="EXP005_CANONICAL_ISSUER_CASH_ENTITLEMENT_LEDGER":
        raise ValueError("Not an original issuer-cash identity ledger")
    if rights.get("kind")!="EXP006_ORIGINAL_ISSUER_STOCK_DISTRIBUTION_AND_TRANSFER_AUDIT":
        raise ValueError("Not a source-PDF stock-right audit")
    if balance.get("kind")!="EXP007_CORPORATE_CAPITAL_BALANCE_ADDITIONAL_NO_RIGHT_PROOF":
        raise ValueError("Not a full original issuer capital-reconciliation audit")
    events=cash["events"]
    if len(events)!=89 or len(rights["audit"])!=len(events) or len(balance["audits"])!=len(events):
        raise ValueError("Original issuer event counts/key scope differ")
    r={x["event_id"]:x for x in rights["audit"]}
    b={x["event_id"]:x for x in balance["audits"]}
    if len(r)!=len(events) or len(b)!=len(events):
        raise ValueError("Duplicate corporate action events in source audits")
    out=[]
    for original in events:
        key=original["event_id"]
        v=r[key]
        c=b[key]
        if (v["issuer_pdf_sha256"]!=original["issuer_pdf_sha256"]
            or c["original_pdf_sha256"]!=original["issuer_pdf_sha256"]):
            raise ValueError("Issuer PDF identity mismatch on merged stock rights")
        bv=v["bonus_ratio_per_nominal_share"]
        tv=v["transfer_ratio_per_nominal_share"]
        evidence={
            "bonus":v["bonus_source_status"],
            "transfer":v["transfer_source_status"],
        }
        inference=c["balanced_accounting_inferred_zero_category"]
        if inference:
            if c["status"]!="ISSUER_IN_SAME_PDF_PRE_POST_AND_ISSUED_SHARE_BALANCE_SUPPORT_ZERO_COMPLEMENT":
                raise ValueError("Balance-derived zero lacks same-original source proof")
            if inference=="transfer" and tv is None and bv is not None and bv>0:
                tv=0.0
                evidence["transfer"]="DERIVED_ZERO_BY_ISSUER_PRE_POST_AND_ISSUED_SHARE_BALANCE"
            elif inference=="bonus" and bv is None and tv is not None and tv>0:
                bv=0.0
                evidence["bonus"]="DERIVED_ZERO_BY_ISSUER_PRE_POST_AND_ISSUED_SHARE_BALANCE"
            else:
                raise ValueError("Capital-conservation source conflicts with parsed rights")
        full=bv is not None and tv is not None
        multiplier=(1+bv+tv) if full else None
        if full and multiplier<1:
            raise ValueError("Invalid share multiplier")
        out.append({
            "event_id":key, "symbol":original["symbol"],
            "announcement_day":original["announcement_day"],
            "earliest_usable_exchange_day":original["earliest_usable_exchange_day"],
            "record_date":original["record_date"],"ex_date":original["ex_date"],
            "scheduled_cash_payment_day":original["payment_date"],
            "gross_cash_per_old_nominal_share":original["gross_cash_per_nominal_share"],
            "issuer_original_pdf_sha256":original["issuer_pdf_sha256"],
            "issuer_original_pdf_url":original["issuer_pdf_url"],
            "bonus_shares_per_old_share":bv,
            "capital_transfer_shares_per_old_share":tv,
            "full_new_nominal_share_multiplier":multiplier,
            "complete_rights_supported_by_issuer_original":full,
            "rights_evidence":evidence,
            "capital_issuer_balance_extra_proof": (
                {"company_before":c["pre_nominal_company_shares"],
                 "company_after":c["post_nominal_company_shares"],
                 "new_issued_shares":c["issuer_explicit_new_share_quantity"]}
                if inference else None
            ),
            "positive_stock_rights":bool((bv or 0)>0 or (tv or 0)>0),
            "cash_rights_nominal_not_qlib_adjusted":True,
            "broker_share_delivery_and_cash_payment_verified":False,
            "original_publication_intraday_time_certified":False,
            "historical_factor_vintage_available":False,
        })
    if len({x["event_id"] for x in out})!=len(out):
        raise AssertionError("Merged rights duplicate identities")
    complete=[x for x in out if x["complete_rights_supported_by_issuer_original"]]
    return {
        "kind":"EXP007_ISSUER_ORIGINAL_BONUS_TRANSFER_AND_CASH_ENTITLEMENT_CATALOG",
        "issuer_events":len(out),
        "fully_verified_nominal_share_rights":len(complete),
        "unknown_share_rights":len(out)-len(complete),
        "complete_positive_stock_rights":sum(x["positive_stock_rights"] for x in complete),
        "partial_positive_stock_rights":sum(
            x["positive_stock_rights"] and not x["complete_rights_supported_by_issuer_original"]
            for x in out
        ),
        "derived_zero_category_by_balanced_issuer_company_shares":sum(
            x["capital_issuer_balance_extra_proof"] is not None for x in out
        ),
        "cash_payment_broker_verification_available":False,
        "stock_credit_broker_verification_available":False,
        "live_transaction_execution_verified":False,
        "historical_factor_version_certified":False,
        "no_double_count_qlib_adjusted_cash":True,
        "events":out,
    }


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--cash-ledger",type=Path,required=True)
    parser.add_argument("--share-audit",type=Path,required=True)
    parser.add_argument("--capital-proof",type=Path,required=True)
    parser.add_argument("--out",type=Path,required=True)
    args=parser.parse_args()
    if args.out.exists():
        raise FileExistsError("Existing PIT issuer cash/share catalog cannot be overwritten")
    src=[
        json.loads(f.read_text("utf-8"))
        for f in (args.cash_ledger,args.share_audit,args.capital_proof)
    ]
    result=assemble(*src)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps({
        k:v for k,v in result.items() if k in (
            "issuer_events","fully_verified_nominal_share_rights",
            "unknown_share_rights","complete_positive_stock_rights",
            "partial_positive_stock_rights",
            "derived_zero_category_by_balanced_issuer_company_shares",
        )
    },indent=2))


if __name__=="__main__":
    main()
