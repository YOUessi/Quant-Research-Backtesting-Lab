"""Recover issuer-verified rights-issue FULL-SESSION stock halts from PDFs.

Requires original publisher PDF bytes with source SHA256, explicit subscription
date range, following clearing day, and next opening resumption. This is NOT
a fill claim; the issuer-original evidence is not a separate exchange log.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re

import pandas as pd


def norm(chinese_date):
    return pd.Timestamp(chinese_date.replace("年","-")
                        .replace("月","-").replace("日","")).date().isoformat()


def original_rights_halt(text, symbol, *, calendar):
    t=re.sub(r"\s+","",text).replace("Ａ","A")
    if symbol[2:] not in t:
        raise ValueError("Issuer code missing in original PDF")
    if "配股" not in t or "股票全天停牌" not in t:
        return None
    period=re.search(
        r"(20\d{2}年\d{1,2}月\d{1,2}日)至"
        r"(20\d{2}年\d{1,2}月\d{1,2}日)"
        r"为本次(?:A股)?配股缴款期",
        t,
    )
    clearing=re.search(
        r"(20\d{2}年\d{1,2}月\d{1,2}日)"
        r"为登记公司网上清算期",
        t,
    )
    resume=re.search(
        r"(?:A股)?股票将于"
        r"(20\d{2}年\d{1,2}月\d{1,2}日)"
        r"开市起复牌",
        t,
    )
    if not (period and clearing and resume and "股票继续停牌一天" in t):
        return None
    begin,end,clear,again=[
        norm(x) for x in
        (period.group(1),period.group(2),clearing.group(1),resume.group(1))
    ]
    days=sorted({pd.Timestamp(d).date().isoformat() for d in calendar})
    in_halt=[d for d in days if begin<=d<again]
    subscribed=[d for d in days if begin<=d<=end]
    if (not in_halt or not subscribed or
        subscribed[-1]>=clear or clear>=again or
        set(in_halt)!=set(subscribed)|{clear} or
        not all(subscribed[i]<subscribed[i+1] for i in range(len(subscribed)-1))):
        raise ValueError("Issuer rights-halt/clear/resume exchange-calendar inconsistency")
    return {
        "symbol":symbol,
        "first_halted_exchange_session":begin,
        "subscription_last_exchange_session":end,
        "clearing_exchange_session":clear,
        "first_resumed_exchange_session":again,
        "issuer_halted_exchange_sessions":in_halt,
        "n_issuer_halted_exchange_sessions":len(in_halt),
        "issuer_original_explicit_rights_issue_halt":True,
        "official_exchange_separate_status_file_consulted":False,
        "real_opening_order_fill_proven":False,
    }


def audit_rights_halts(source_report, *, raw_dir, panel, calendar):
    from pypdf import PdfReader
    available=panel.loc[
        panel.date.between("2021-01-04","2022-12-30")
        & panel.index_member_asof,
        ["asset","date","known_close_t"],
    ].copy()
    available["day"]=pd.to_datetime(available.date).dt.strftime("%Y-%m-%d")
    allby=available.set_index(["asset","day"])
    recovered,unknown=[],[]
    for ticker in source_report["results"]:
        symbol=ticker["symbol"]
        for pdf in ticker["pdf_proofs"]:
            if not pdf.get("pdf_sha256"):
                continue
            matching=list(Path(raw_dir).glob(f"{symbol}_*.pdf"))
            matches=[p for p in matching
                     if hashlib.sha256(p.read_bytes()).hexdigest()==pdf["pdf_sha256"]]
            if len(matches)!=1:
                raise ValueError("Cannot prove single original rights-issue PDF hash")
            text="\n".join(page.extract_text() or "" for page in
                           PdfReader(matches[0]).pages[:4])
            try:
                proof=original_rights_halt(text,symbol,calendar=calendar)
            except ValueError as exc:
                unknown.append({"symbol":symbol,"pdf_sha256":pdf["pdf_sha256"],
                                "reason":str(exc)[:150]})
                continue
            if proof is None:continue
            if pdf["announcement_calendar_day"]>=proof["first_halted_exchange_session"]:
                unknown.append({"symbol":symbol,"reason":"Issuer publish day not prior to effective halt",
                                "sha256":pdf["pdf_sha256"]})
                continue
            inconsistent=[]
            for day in proof["issuer_halted_exchange_sessions"]:
                key=(symbol,day)
                if key not in allby.index or bool(allby.loc[key,"known_close_t"]):
                    inconsistent.append(day)
            proof["issuer_pdf_sha256"]=pdf["pdf_sha256"]
            proof["issuer_original_document_url"]=pdf["official_pdf_url"]
            proof["issuer_release_calendar_day"]=pdf["announcement_calendar_day"]
            proof["Qlib_halt_days_without_positive_daily_bar"]=(
                len(proof["issuer_halted_exchange_sessions"])-len(inconsistent)
            )
            proof["Qlib_inconsistent_or_missing_member_day"]=inconsistent
            proof["full_period_Qlib_independently_corroborates_halt"]=not inconsistent
            recovered.append(proof)
    by=(p for x in recovered for p in x["issuer_halted_exchange_sessions"])
    distinct_pairs={(x["symbol"],d) for x in recovered
                    for d in x["issuer_halted_exchange_sessions"]}
    result={
        "kind":"EXP005_ORIGINAL_ISSUER_RIGHTS_ISSUE_PDF_HALT_PERIOD_AUDIT",
        "unique_issuer_events_confirmed":len(recovered),
        "covered_securities":len({x["symbol"] for x in recovered}),
        "historical_issuer_halted_stock_days":len(distinct_pairs),
        "source_pdfs_proven_by_sha256":True,
        "Qlib_positive_bar_disagreement_count":sum(
            len(x["Qlib_inconsistent_or_missing_member_day"]) for x in recovered
        ),
        "all_source_index_halt_days_certified":False,
        "separate_exchange_event_file_consulted":False,
        "opening_auction_fills_certified":False,
        "recovered":recovered,"unresolved_or_inconsistent":unknown,
    }
    return result


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--source-report",type=Path,required=True)
    p.add_argument("--issuer-pdfs",type=Path,required=True)
    p.add_argument("--historical-panel",type=Path,required=True)
    p.add_argument("--exchange-calendar",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    source=json.loads(a.source_report.read_text("utf-8"))
    panel=pd.read_parquet(a.historical_panel,
                          columns=["date","asset","index_member_asof","known_close_t"])
    cal=pd.read_csv(a.exchange_calendar,header=None)[0]
    audit=audit_rights_halts(source,raw_dir=a.issuer_pdfs,
                            panel=panel,calendar=cal)
    if a.out.exists():raise FileExistsError("Cannot overwrite halt proof")
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(audit,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps({
        "verified_issuer_rights_issue_stock_halt_events":audit["unique_issuer_events_confirmed"],
        "issuers":audit["covered_securities"],
        "halted_stock_sessions":audit["historical_issuer_halted_stock_days"],
        "source_Qlib_disagreements":audit["Qlib_positive_bar_disagreement_count"],
    },indent=2,ensure_ascii=False))


if __name__=="__main__":
    main()
