"""Recover public original issuer evidence for failed aggregator symbols.

Never interpret 'third-party API returned empty' as proof of no dividends.
Official issuer notices may appear despite a delisted/rebranded ticker not
appearing in today's market-data vendor records.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def audit_gaps(original: dict, recovery: dict[str, dict],
               issuer_batch: dict|None=None) -> dict:
    fail={item["symbol"]:item for item in original.get("failures",[])}
    if not fail:
        raise ValueError("No upstream missing symbols to recover")
    documents=issuer_batch.get("documents",[]) if issuer_batch else []
    entries=[]
    for sym in sorted(fail):
        r=recovery.get(sym)
        if r is None or r.get("result")!="OFFICIAL_INDEX_SEARCH":
            entries.append({
                "symbol":sym,
                "aggregator_reason":fail[sym].get("message"),
                "official_index": "NOT_AVAILABLE",
                "official_implementation_notices_found":None,
                "notice_pdf_verified_count":0,
                "status":"UNKNOWN_DO_NOT_ASSUME_NO_CORPORATE_ACTION",
            })
            continue
        notices=r.get("relevant_pdf_records",[])
        candidates=[x for x in notices
                    if "实施" in x.get("announcement_title","")
                    and any(y in x["announcement_title"] for y in
                            ("权益分派","分红派息","利润分配"))]
        fetched=[x for x in documents if x["symbol"]==sym]
        entries.append({
            "symbol":sym,"aggregator_reason":fail[sym].get("message"),
            "official_index":"OFFICIAL_INDEX_SEARCH_COMPLETED",
            "official_implementation_notices_found":len(candidates),
            "original_pdf_metadata":[
                {"announcement_id":x.get("announcement_id"),
                 "publication_calendar_date":x["published_calendar_date"],
                 "pdf_url":x["pdf_url"],
                 "title":x["announcement_title"]}
                for x in candidates
            ],
            "notice_pdf_verified_count":len(fetched),
            "pdf_cash_amounts_crossmatched_with_aggregator":sum(
                x.get("status")=="PDF_CASH_MATCHED_TO_THIRDPARTY"
                for x in fetched),
            "pdf_cash_amounts_verified_as_unique_number_without_aggregator":sum(
                x.get("status")=="OFFICIAL_PDF_NUMBER_ONLY_NOT_RECONCILED"
                and x.get("cash_per_share_verified") is not None
                for x in fetched),
            "status":(
                "SOME_ORIGINAL_ISSUER_EVENTS_RECOVERED"
                if fetched else (
                    "OFFICIAL_ISSUER_IMPLEMENTATION_NOTICES_FOUND_PDF_PENDING"
                    if candidates else "NO_MATCH_ON_LIMITED_KEYWORDS_NOT_ZERO_ACTION_CERTIFICATE"
                )
            ),
        })
    return {
        "kind":"PIT_GAP_RECOVERY_THIRDPARTY_ABSENCE_VS_ORIGINAL_ISSUER_DISCLOSURE",
        "study_period":["2021-01-01","2022-12-31"],
        "original_missing_tickers":len(fail),
        "official_index_retrieved":sum(x["official_index"]=="OFFICIAL_INDEX_SEARCH_COMPLETED"
                                      for x in entries),
        "official_implementation_notice_tickers":sum((x.get("official_implementation_notices_found") or 0)>0 for x in entries),
        "official_implementation_notice_count":sum(x.get("official_implementation_notices_found") or 0 for x in entries),
        "issuer_pdf_records_verified":sum(x.get("notice_pdf_verified_count") or 0 for x in entries),
        "all_11_gaps_fully_resolved":False,
        "no_dividend_certification_for_unmatched_tickers":False,
        "recorded_data_provider_gap_is_not_a_zero_dividend":True,
        "ticker_findings":entries,
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--collection-summary",type=Path,required=True)
    p.add_argument("--recovery-root",type=Path,required=True)
    p.add_argument("--issuer-pdf-batch",type=Path)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    original=json.loads(a.collection_summary.read_text("utf8"))
    recovery={}
    for f in a.recovery_root.glob("*.json"):
        obj=json.loads(f.read_text("utf8"))
        if "symbol" in obj:
            recovery[obj["symbol"]]=obj
    batch=json.loads(a.issuer_pdf_batch.read_text("utf8")) if a.issuer_pdf_batch else None
    result=audit_gaps(original,recovery,batch)
    if a.out.exists():
        raise FileExistsError(f"Refusing to overwrite source-gap results: {a.out}")
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({
        k:result[k] for k in (
            "original_missing_tickers","official_index_retrieved",
            "official_implementation_notice_tickers",
            "official_implementation_notice_count","issuer_pdf_records_verified",
            "all_11_gaps_fully_resolved")},indent=2,ensure_ascii=False))


if __name__=="__main__":
    main()
