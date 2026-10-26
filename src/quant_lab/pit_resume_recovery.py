"""EXP-007: targeted follow-up original issuer RESUMPTION documents only.

The first halt audit downloaded at most 4 PDFs per issuer, choosing ones
nearest to missing bars. Remaining unpaired original effective suspension
dates must NOT be expanded into whole intervals using estimated maximum
halt duration. This collector searches historical CNINFO *resume* disclosure
titles, fetches a bounded number of original PDFs per prior unpaired issuer,
validates issuer stock/date/SHA, and copies the original capped data into a
new immutable folder before rerunning pairwise calendar validation.

No authentication bypass or evasion of published access restrictions.
"""
from __future__ import annotations

import argparse
from datetime import datetime,timezone
import hashlib
from io import BytesIO
import json
from pathlib import Path
import shutil
import time

import requests
from pypdf import PdfReader

from .pit_collect import fetch_cninfo
from .pit_halt_pairs import extract_effects


MAX_PDF_BYTES=8_000_000


def recovery_targets(prior_paired:dict) -> dict[str,list[str]]:
    if prior_paired.get("kind")!="EXP007_PAIRED_INDEPENDENT_ORIGINAL_ISSUER_HALT_RESUME_PROOFS":
        raise ValueError("Expected existing issuer halt pairing audit")
    result={}
    for x in prior_paired["unresolved_not_booked_as_halts"]:
        if x.get("reason")!="NO_SEPARATELY_EXPLICIT_RESUME_DATE":
            continue
        result.setdefault(x["symbol"],[]).append(x["start"])
    return {k:sorted(set(v)) for k,v in result.items()}


def collect(prior:dict, source:dict, source_pdf_dir:Path,
            *,output:Path, max_new_pdfs_per_symbol:int=5,
            delay:float=.55) -> dict:
    if output.exists():
        raise FileExistsError("Refusing to mutate existing PDF audit output")
    if max_new_pdfs_per_symbol<1 or max_new_pdfs_per_symbol>12 or delay<.3:
        raise ValueError("Invalid per-symbol PDF or public access cap")
    targets=recovery_targets(prior)
    output.mkdir(parents=True,exist_ok=False)
    combined=output/"original_issuer_pdfs"
    combined.mkdir()
    audit_source={
        "kind":source["kind"],
        "recovery_version":"EXP007_ENLARGED_OFFICIAL_RESUMPTION_PDF_PROOFS",
        "results":[],
        "original_source_audit_digest":hashlib.sha256(
            json.dumps(source,sort_keys=True,ensure_ascii=False).encode()
        ).hexdigest(),
    }
    for ticker in source["results"]:
        row=dict(ticker)
        row["pdf_proofs"]=list(ticker["pdf_proofs"])
        audit_source["results"].append(row)
        for pdf in row["pdf_proofs"]:
            sha=pdf.get("pdf_sha256")
            if not sha:continue
            original=[x for x in source_pdf_dir.glob(f"{row['symbol']}_*.pdf")
                      if hashlib.sha256(x.read_bytes()).hexdigest()==sha]
            if len(original)!=1:
                raise ValueError("Original issuer source PDF bytes missing/duplicated")
            shutil.copy2(original[0],combined/original[0].name)
    summaries=[]
    with requests.Session() as session:
        for i,(symbol,starts) in enumerate(sorted(targets.items()),1):
            entry={
                "symbol":symbol,"unpaired_effective_halt_starts":starts,
                "indexed_resumption_candidates":0,
                "new_original_resumption_pdfs_verified":0,
                "new_pdf_evidence":[],
                "errors":[],
            }
            try:
                official,logs=fetch_cninfo(
                    session,symbol,first="2021-01-01",
                    last="2023-01-15",include_trading=True,
                )
                selected=[]
                for info in official:
                    title=info.get("announcement_title","")
                    if "复牌" not in title or ("转债" in title and "股票" not in title):
                        continue
                    pub=info.get("published_calendar_date")
                    if pub is None:continue
                    # Historical 2022 resume may appear in Jan 2023, but
                    # no start without an original in the previous audit.
                    if not any(pub>=start for start in starts):
                        continue
                    proximity=min(abs((__import__("datetime").date.fromisoformat(pub)
                                       - __import__("datetime").date.fromisoformat(s)).days)
                                  for s in starts if pub>=s)
                    selected.append((proximity,info))
                selected.sort(key=lambda x:(x[0],x[1]["announcement_id"]))
                entry["indexed_resumption_candidates"]=len(selected)
                for _,info in selected[:max_new_pdfs_per_symbol]:
                    try:
                        url=info["pdf_url"]
                        if not url.startswith("https://static.cninfo.com.cn/finalpage/"):
                            raise ValueError("Nonofficial original PDF source")
                        r=session.get(url,timeout=(7,18),headers={"User-Agent":"Mozilla/5.0"},
                                      stream=True)
                        r.raise_for_status()
                        payload=bytearray()
                        for block in r.iter_content(131072):
                            payload.extend(block)
                            if len(payload)>MAX_PDF_BYTES:
                                raise ValueError("Original issuer PDF exceeds cap")
                        raw=bytes(payload)
                        if not raw.startswith(b"%PDF"):
                            raise ValueError("CNINFO original PDF bytes unavailable")
                        digest=hashlib.sha256(raw).hexdigest()
                        text="\n".join(x.extract_text() or "" for x in
                                      PdfReader(BytesIO(raw),strict=False).pages[:5])
                        effect=extract_effects(text,ticker=symbol)
                        if not effect["effective_resume_from_open_dates"]:
                            raise ValueError("Original issuer text lacks effective share resumption")
                        if not any(d>min(starts) for d in effect["effective_resume_from_open_dates"]):
                            raise ValueError("Resumption date not after known halt starts")
                        filename=f"{symbol}_recovery_{info['announcement_id']}.pdf"
                        (combined/filename).write_bytes(raw)
                        record={
                            "symbol":symbol,
                            "announcement_calendar_day":info["published_calendar_date"],
                            "announcement_title":info["announcement_title"],
                            "official_pdf_url":url,
                            "pdf_sha256":digest,
                            "downloaded_utc":datetime.now(timezone.utc).isoformat(),
                            "effect":{
                                "suspend_start":None,
                                "resume_start":effect["effective_resume_from_open_dates"][0],
                                "reason":"ORIGINAL_ISSUER_RESUME_EFFECTIVE_DATE",
                            },
                            "original_issuer_pdf_text_extractable":True,
                            "original_issuer_response_not_time_versioned":True,
                            "broker_trade_fill_verified":False,
                        }
                        row=next(v for v in audit_source["results"]
                                 if v["symbol"]==symbol)
                        if not any(x.get("pdf_sha256")==digest
                                   for x in row["pdf_proofs"]):
                            row["pdf_proofs"].append(record)
                            entry["new_original_resumption_pdfs_verified"]+=1
                        entry["new_pdf_evidence"].append({
                            "publication_day":info["published_calendar_date"],
                            "resume_effective_dates":effect["effective_resume_from_open_dates"],
                            "sha256":digest,"url":url,
                        })
                    except Exception as exc:
                        entry["errors"].append({
                            "announcement_id":info.get("announcement_id"),
                            "kind":type(exc).__name__,
                            "message":str(exc)[:170],
                        })
                    time.sleep(delay)
                entry["cninfo_meta_response_count"]=len(logs)
            except Exception as exc:
                entry["errors"].append({
                    "kind":type(exc).__name__,
                    "message":str(exc)[:200],
                })
            summaries.append(entry)
            print(i,len(targets),symbol,"unpaired",len(starts),
                  "issuer_original_resume_PDF_verified",
                  entry["new_original_resumption_pdfs_verified"],
                  "failed",len(entry["errors"]),flush=True)
            time.sleep(delay)
    audit_source["resumption_recovery_experiment"]={
        "targeted_issuers":len(targets),
        "new_original_pdf_count":sum(x["new_original_resumption_pdfs_verified"]
                                      for x in summaries),
        "remaining_unresolved_source_errors":sum(len(x["errors"]) for x in summaries),
        "targets":summaries,
    }
    (output/"combined_issuer_audit.json").write_text(
        json.dumps(audit_source,indent=2,ensure_ascii=False)+"\n",encoding="utf8"
    )
    (output/"resume_recovery_summary.json").write_text(
        json.dumps(audit_source["resumption_recovery_experiment"],
                   indent=2,ensure_ascii=False)+"\n",encoding="utf8"
    )
    return audit_source["resumption_recovery_experiment"]


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--prior-pairs",type=Path,required=True)
    p.add_argument("--source-issuer-audit",type=Path,required=True)
    p.add_argument("--original-pdfs",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--per-ticker-pdfs",type=int,default=5)
    p.add_argument("--delay",type=float,default=.55)
    args=p.parse_args()
    source=json.loads(args.source_issuer_audit.read_text("utf8"))
    prior=json.loads(args.prior_pairs.read_text("utf8"))
    summary=collect(prior,source,args.original_pdfs,
                    output=args.out,max_new_pdfs_per_symbol=args.per_ticker_pdfs,
                    delay=args.delay)
    print(json.dumps({
        k:v for k,v in summary.items() if k in (
            "targeted_issuers","new_original_pdf_count",
            "remaining_unresolved_source_errors",
        )
    },indent=2))


if __name__=="__main__":
    main()
