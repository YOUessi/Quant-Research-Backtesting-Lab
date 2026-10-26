"""EXP-005: look for original issuer suspension/resumption notices on 17 Qlib gaps.

Issuer index metadata != stock suspension certification. Only a PDF whose
security code and explicit "stock opens suspended/resumes on YYYY-MM-DD"
terms match becomes a known single-security status constraint. Notices
about convertible bonds and unrelated assets are excluded.

This is an independent AFTER-THE-FACT data audit; announcement dates cannot
be used as earlier model features. Raw source documents remain gitignored.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
from io import BytesIO
import json
from pathlib import Path
import re
import time

import pandas as pd
import requests

from .pit_collect import fetch_json, CN_ORG_URL, CN_NOTICE_URL
from .pit_primary_audit import PDF_LIMIT_BYTES
from .pit_events import normalise_cninfo_announcements


def compact(text):
    return re.sub(r"\s+","",text).replace("Ａ","A")


def notice_effects(document_text:str,symbol:str)->dict:
    """No approximation from an announcement date to effective trade day."""
    clean=compact(document_text)
    if symbol[2:] not in clean:
        raise ValueError("Official document lacks the target stock code")
    if not ("股票" in clean or "A股" in clean):
        return {"suspend_start":None,"resume_start":None,"reason":"stock_notice_context_absent"}
    # The noun must be company/common stock, not a bond-only pause.
    stop=re.search(
        r"(?:公司)?股票将于(20\d{2}年\d{1,2}月\d{1,2}日).*?开市起停牌",
        clean,
    )
    resume=re.search(
        r"(?:公司)?股票将于(20\d{2}年\d{1,2}月\d{1,2}日).*?开市起复牌",
        clean,
    )
    def norm(s):
        if not s:return None
        return pd.Timestamp(s.replace("年","-").replace("月","-").replace("日","")).date().isoformat()
    if stop and resume:
        return {"suspend_start":None,"resume_start":None,"reason":"ambiguous_stop_and_resume_in_one_document"}
    return {
        "suspend_start":norm(stop.group(1)) if stop else None,
        "resume_start":norm(resume.group(1)) if resume else None,
        "reason":"EXPLICIT_COMPANY_STOCK_DATE" if stop or resume else "no_explicit_stock_halt_date",
    }


def _query_symbol(session,symbol,*,first="2021-01-01",last="2022-12-31"):
    code=symbol[2:]
    result, orgmeta=fetch_json(
        session,url=CN_ORG_URL,
        params={"keyWord":code,"maxNum":10},post=True,
    )
    ids=[x.get("orgId") for x in result if x.get("code")==code]
    if len(ids)!=1 or not ids[0]:
        raise ValueError("Cannot identify exact CNINFO ticker organization")
    found,proof=[],[orgmeta]
    for keyword in ("停牌","复牌"):
        query={
            "pageNum":"1","pageSize":"100","tabName":"fulltext",
            "column":"sse" if symbol.startswith("SH") else "szse",
            "stock":f"{code},{ids[0]}",
            "searchkey":keyword,
            "seDate":f"{first}~{last}",
            "isHLtitle":"true",
        }
        val,meta=fetch_json(session,url=CN_NOTICE_URL,params=query,post=True)
        if int(val.get("totalAnnouncement") or 0)>100:
            raise ValueError("CNINFO paging capped: manual pagination required")
        found.extend(val.get("announcements") or [])
        proof.append(meta)
        time.sleep(.32)
    notices=normalise_cninfo_announcements(found)
    return list({x["announcement_id"]:x for x in notices}.values()), proof


def audit_missing_halt_sources(*, missing_panel:pd.DataFrame,
                               output:Path, pacing=.55,
                               max_pdfs_per_ticker:int=4):
    if output.exists():raise FileExistsError("Never overwrite halt source audit")
    if pacing<.3 or max_pdfs_per_ticker<1:raise ValueError("Unsafe request pacing")
    wanted=missing_panel.loc[
        missing_panel["index_member_asof"]
        & ~missing_panel["known_close_t"]
        & missing_panel["date"].between("2021-01-04","2022-12-30"),
        ["asset","date"],
    ].copy()
    if len(wanted)!=139 or wanted.asset.nunique()!=17:
        raise ValueError("Frozen EXP002 139 member-day gaps changed; revalidate first")
    wanted["date"]=pd.to_datetime(wanted["date"]).dt.normalize()
    target={a:set(v["date"].dt.date.astype(str)) for a,v in wanted.groupby("asset")}
    output.mkdir(parents=True,exist_ok=False)
    original=output/"original_issuer_pdfs"
    original.mkdir()
    collected,failures=[],[]
    with requests.Session() as s:
        for i,(symbol,dates) in enumerate(sorted(target.items()),1):
            try:
                notices,meta=_query_symbol(s,symbol)
                hits=[]
                for notice in notices:
                    title=notice["announcement_title"]
                    # Filter apparent equity stock halt notices; ambiguous
                    # title remains noncertifying, and never converts into a fill.
                    if "转债" in title or "债券" in title or "回购" in title:
                        continue
                    if "停牌" not in title and "复牌" not in title:
                        continue
                    noticeday=pd.Timestamp(notice["published_calendar_date"])
                    dist=min(abs((pd.Timestamp(x)-noticeday).days) for x in dates)
                    hits.append((dist,notice))
                hits.sort(key=lambda x:(x[0],x[1]["announcement_id"]))
                pdf_proofs=[]
                for _,notice in hits[:max_pdfs_per_ticker]:
                    try:
                        url=notice["pdf_url"]
                        if not url.startswith("https://static.cninfo.com.cn/finalpage/"):
                            raise ValueError("Nonofficial issuer PDF endpoint")
                        r=s.get(url,timeout=(8,18),headers={"User-Agent":"Mozilla/5.0"})
                        r.raise_for_status()
                        if len(r.content)>PDF_LIMIT_BYTES or not r.content.startswith(b"%PDF"):
                            raise ValueError("Not a size-bounded original PDF")
                        from pypdf import PdfReader
                        pdf=PdfReader(BytesIO(r.content),strict=False)
                        text="\n".join(p.extract_text() or "" for p in pdf.pages[:5])
                        effect=notice_effects(text,symbol)
                        sha=hashlib.sha256(r.content).hexdigest()
                        dest=original/f"{symbol}_{notice['announcement_id']}.pdf"
                        dest.write_bytes(r.content)
                        pdf_proofs.append({
                            "symbol":symbol,
                            "announcement_calendar_day":notice["published_calendar_date"],
                            "announcement_title":notice["announcement_title"],
                            "official_pdf_url":url,
                            "pdf_sha256":sha,
                            "pdf_bytes":len(r.content),
                            "effect":effect,
                            "document_numeric_terms_not_extracted":True,
                            "publisher_intraday_timestamp_certified":False,
                        })
                    except Exception as e:
                        pdf_proofs.append({
                            "symbol":symbol,"announcement_id":notice["announcement_id"],
                            "error_type":type(e).__name__,
                            "error":str(e)[:180],
                            "effective_halt_status_certified":False,
                        })
                    time.sleep(.45)
                collected.append({
                    "symbol":symbol,"qlib_missing_days":len(dates),
                    "official_notice_index_count":len(notices),
                    "potential_stock_halt_titles":len(hits),
                    "original_pdfs_checked":len(pdf_proofs),
                    "source_provenance":meta,
                    "pdf_proofs":pdf_proofs,
                })
                print(i,len(target),symbol,"notices",len(notices),
                      "pdfs",len(pdf_proofs),
                      "explicit",sum(bool(p.get("effect",{}).get("suspend_start")
                                          or p.get("effect",{}).get("resume_start"))
                                      for p in pdf_proofs),flush=True)
            except Exception as e:
                failures.append({"symbol":symbol,"error":type(e).__name__,
                                 "message":str(e)[:220]})
                print(i,len(target),symbol,"ERROR",type(e).__name__,str(e)[:95],flush=True)
            time.sleep(pacing)
    result={
        "kind":"EXP005_PRIMARY_ISSUER_HALT_ANNOUNCEMENT_EXPLORATION",
        "study_period":["2021-01-04","2022-12-30"],
        "original_qlib_missing_member_days":139,
        "target_symbols":17,
        "official_index_symbols_completed":len(collected),
        "official_index_symbols_failed":len(failures),
        "original_pdf_documents_checked":sum(len(x["pdf_proofs"]) for x in collected),
        "explicit_company_stock_halt_start_date_statements":sum(
            bool(p.get("effect",{}).get("suspend_start"))
            for a in collected for p in a["pdf_proofs"]
        ),
        "explicit_company_stock_resume_date_statements":sum(
            bool(p.get("effect",{}).get("resume_start"))
            for a in collected for p in a["pdf_proofs"]
        ),
        "all_139_days_officially_proven_suspended":False,
        "actual_broker_fill_evidence":False,
        "unreviewed_or_truncated_pdfs_possible":True,
        "results":collected,"failures":failures,
    }
    (output/"source_audit.json").write_text(
        json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf8"
    )
    return result


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--historical-panel",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    ap.add_argument("--max-pdfs-per-ticker",type=int,default=4)
    opts=ap.parse_args()
    frame=pd.read_parquet(
        opts.historical_panel,
        columns=["date","asset","index_member_asof","known_close_t"],
    )
    a=audit_missing_halt_sources(
        missing_panel=frame,output=opts.out,
        max_pdfs_per_ticker=opts.max_pdfs_per_ticker,
    )
    print(json.dumps({k:v for k,v in a.items() if k in (
        "official_index_symbols_completed","official_index_symbols_failed",
        "original_pdf_documents_checked",
        "explicit_company_stock_halt_start_date_statements",
        "explicit_company_stock_resume_date_statements"
    )},indent=2))


if __name__=="__main__":
    main()
