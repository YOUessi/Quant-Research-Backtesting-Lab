"""EXP-007 original issuer *independent* halt + resumption PDF interval matching.

Evidence condition for a whole halted interval:
  (1) issuer original SHA256-checked PDF explicitly names its own stock,
      an effective halt-from-open date, and the issuer disclosure calendar day;
  (2) a distinct original SHA256-checked issuer PDF explicitly announces an
      effective resumption-from-open date;
  (3) start<resume, exchange-calendar dates between are strictly bounded;
  (4) every ticker/day between belongs to the historical index and Qlib has
      NO positive recorded close/volume (no hindsight universe removal).
Only then label an additional issuer-documented "no share trades" interval.
The original publication calendar day is not a certified intraday issuer
upload time and NO brokerage order fill is inferred from these notices.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import re

import pandas as pd
from pypdf import PdfReader


CHINESE_DATE = r"(20\d{2}年\d{1,2}月\d{1,2}日)"
STOCK = (
    r"(?:本公司|公司)(?:A股)?股票"
    r"(?:[（(][^（）()]{0,105}[）)])?"
    r"(?:.{0,28}?)"
)
HALT = re.compile(
    STOCK + r"(?:自|将自|将于|将在|于)"
    + CHINESE_DATE
    + r"(?:[（(][^（）()]{0,20}[）)])?"
    + r"(?:上午)?(?:开市起|起|开始)?(?:开始)?停牌"
)
RESUME = re.compile(
    STOCK + r"(?:自|将自|将于|将在|于)"
    + CHINESE_DATE
    + r"(?:[（(][^（）()]{0,20}[）)])?"
    + r"(?:上午)?(?:开市起|起|开始)?(?:开始)?复牌"
)


def day(s: str) -> str:
    return str(pd.Timestamp(s.replace("年","-").replace("月","-").replace("日","")).date())


def extract_effects(text: str, *, ticker: str) -> dict:
    """Retrieve *effective* dates; no guess based on issuer notice date."""
    t=re.sub(r"\s+","",text).replace("Ａ","A")
    if ticker[2:] not in t:
        raise ValueError("Original issuer PDF lacks own ticker")
    starts=sorted(set(day(x) for x in HALT.findall(t)))
    resumptions=sorted(set(day(x) for x in RESUME.findall(t)))
    return {
        "ticker":ticker,
        "effective_halt_from_open_dates":starts,
        "effective_resume_from_open_dates":resumptions,
        "has_intraday_only_resumption":bool(re.search(
            r"公司(?:A股)?股票.{0,80}?\d+年\d+月\d+日"
            r"(?:[（(][^（）()]{0,12}[）)])?下午开市起复牌",t)),
        "not_issuer_trading_board_status_file":True,
    }


def reconstruct(audit: dict, pdf_folder: Path,
                panel: pd.DataFrame, exchange_dates: pd.DatetimeIndex,
                *, baseline_original_halt: dict|None=None) -> dict:
    if audit.get("kind")!="EXP005_PRIMARY_ISSUER_HALT_ANNOUNCEMENT_EXPLORATION":
        raise ValueError("Unexpected issuer original source audit")
    calendar=sorted({str(pd.Timestamp(x).date()) for x in exchange_dates})
    if not calendar:
        raise ValueError("Empty trade calendar")
    req={"date","asset","index_member_asof","known_close_t"}
    if not req.issubset(panel.columns):
        raise ValueError("Need original Qlib historical member-day quality marks")
    frame=panel.loc[
        panel["date"].between("2021-01-04","2022-12-30"),
        ["asset","date","index_member_asof","known_close_t"]
    ].copy()
    frame["day"]=pd.to_datetime(frame["date"]).dt.strftime("%Y-%m-%d")
    key={(x.asset,x.day):(bool(x.index_member_asof),bool(x.known_close_t))
         for x in frame.itertuples(index=False)}
    events=[]
    for entity in audit["results"]:
        ticker=entity["symbol"]
        for meta in entity["pdf_proofs"]:
            sha=meta.get("pdf_sha256")
            if not sha:
                continue
            files=[f for f in pdf_folder.glob(f"{ticker}_*.pdf")
                   if hashlib.sha256(f.read_bytes()).hexdigest()==sha]
            if len(files)!=1:
                raise ValueError("Original source PDF SHA missing or ambiguous")
            doc=PdfReader(files[0],strict=False)
            text="\n".join(p.extract_text() or "" for p in doc.pages[:5])
            effect=extract_effects(text,ticker=ticker)
            events.append({
                "symbol":ticker,
                "issuer_notice_calendar_day":meta["announcement_calendar_day"],
                "issuer_pdf_sha256":sha,
                "issuer_pdf_url":meta["official_pdf_url"],
                "notice_title":meta["announcement_title"],
                **effect,
            })

    pairs=[]
    unresolved=[]
    by=defaultdict(list)
    for x in events:by[x["symbol"]].append(x)
    for ticker,records in sorted(by.items()):
        starts=defaultdict(list)
        ends=defaultdict(list)
        for record in records:
            for sd in record["effective_halt_from_open_dates"]:
                starts[sd].append(record)
            for ed in record["effective_resume_from_open_dates"]:
                ends[ed].append(record)
        matched_halting_starts=set()
        for start in sorted(starts):
            plausible=sorted((e for e in ends if e>start))
            if not plausible:
                unresolved.append({"symbol":ticker,"start":start,
                                   "reason":"NO_SEPARATELY_EXPLICIT_RESUME_DATE"})
                continue
            ending=plausible[0]
            # Can't merge with another independent halt start nested inside
            # the date window: need disambiguation before booking.
            interfering=sorted(s for s in starts if start<s<ending)
            if interfering:
                unresolved.append({"symbol":ticker,"start":start,
                                   "ending":ending,
                                   "reason":"OVERLAPPING_OR_CONFLICTING_HALT_STARTS"})
                continue
            if start in matched_halting_starts:
                continue
            if not (start in calendar and ending in calendar):
                unresolved.append({"symbol":ticker,"start":start,
                                   "ending":ending,
                                   "reason":"EFFECTIVE_DATE_MISSING_EXCHANGE_CALENDAR"})
                continue
            between=[d for d in calendar if start<=d<ending]
            if not 1<=len(between)<=25:
                unresolved.append({"symbol":ticker,"start":start,
                                   "ending":ending,
                                   "reason":"UNBOUNDED_HALT_PERIOD"})
                continue
            src_starts=sorted(starts[start],key=lambda x:x["issuer_notice_calendar_day"])
            src_ends=sorted(ends[ending],key=lambda x:x["issuer_notice_calendar_day"])
            # Must use independent PDF *files*, not one later document
            # reporting an entire historical interval by itself.
            proof=next(((a,b) for a in src_starts for b in src_ends
                        if a["issuer_pdf_sha256"]!=b["issuer_pdf_sha256"]),None)
            if proof is None:
                unresolved.append({"symbol":ticker,"start":start,"ending":ending,
                                   "reason":"NO_TWO_DISTINCT_ISSUER_PDFS"})
                continue
            if proof[1]["has_intraday_only_resumption"]:
                unresolved.append({"symbol":ticker,"start":start,"ending":ending,
                                   "reason":"INTRADAY_ONLY_RESUME_NOT_FULL_DAY"})
                continue
            mismatched=[d for d in between
                        if key.get((ticker,d)) != (True,False)]
            if mismatched:
                unresolved.append({"symbol":ticker,"start":start,"ending":ending,
                                   "reason":"MEMBERSHIP_OR_POSITIVE_DAILY_BAR_CONTRADICTION",
                                   "days":mismatched})
                continue
            pairs.append({
                "symbol":ticker,"start_halt_full_session":start,
                "first_resume_full_session":ending,
                "n_exchange_sessions":len(between),
                "confirmed_no_positive_qlib_member_bars":True,
                "halted_exchange_sessions":between,
                "start_issuer_pdf_sha256":proof[0]["issuer_pdf_sha256"],
                "start_issuer_pdf_url":proof[0]["issuer_pdf_url"],
                "start_published_calendar_day":proof[0]["issuer_notice_calendar_day"],
                "resume_issuer_pdf_sha256":proof[1]["issuer_pdf_sha256"],
                "resume_issuer_pdf_url":proof[1]["issuer_pdf_url"],
                "resume_published_calendar_day":proof[1]["issuer_notice_calendar_day"],
                "broker_fill_or_live_trade_status_certified":False,
            })
            matched_halting_starts.add(start)
    new={(x["symbol"],d) for x in pairs for d in x["halted_exchange_sessions"]}
    # Prior first-party halt and rights-issue certificates are joined on
    # exact symbol/trading-day pair, not simply summed as counts.
    prior=set()
    if baseline_original_halt is not None:
        if baseline_original_halt.get("kind")!="EXP005_ORIGINAL_ISSUER_RIGHTS_ISSUE_PDF_HALT_PERIOD_AUDIT":
            raise ValueError("Invalid prior original rights issue halt proof")
        for p in baseline_original_halt["recovered"]:
            for d in p["issuer_halted_exchange_sessions"]:
                prior.add((p["symbol"],d))
        baseline_SH600340 = [
            d for d in calendar if "2021-01-29"<=d<"2021-02-19"
        ]
        if len(baseline_SH600340)!=10:
            raise ValueError("Prior original SH600340 halt calendar unexpected")
        prior.update(("SH600340",d) for d in baseline_SH600340)
    union=prior|new
    if any(x in prior for x in new):
        # Overlap is allowed for duplicate historical original sources but
        # counts must use set union; do not multiply evidence.
        pass
    return {
        "kind":"EXP007_PAIRED_INDEPENDENT_ORIGINAL_ISSUER_HALT_RESUME_PROOFS",
        "original_pdf_documents_examined":len(events),
        "independent_original_issuer_halt_resume_intervals":len(pairs),
        "newly_paired_issuer_halt_stock_session_count":len(new),
        "previously_verified_issuer_halt_stock_sessions":len(prior),
        "unique_issuer_proven_halted_stock_session_union":len(union),
        "new_additional_halt_stock_sessions_not_in_prior":len(new-prior),
        "pairs":pairs,
        "unresolved_not_booked_as_halts":unresolved,
        "issuer_calendar_day_is_not_intraday_disclosure_time":True,
        "broker_auction_trade_execution_verified":False,
        "nonhalt_days_are_not_certified_tradeable":True,
        "still_need_price_limit_levels_and_auction_order_queue":True,
    }


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--issuer-archive",type=Path,required=True)
    ap.add_argument("--original-issuer-pdfs",type=Path,required=True)
    ap.add_argument("--historical-panel",type=Path,required=True)
    ap.add_argument("--calendar",type=Path,required=True)
    ap.add_argument("--previous-rights-halt",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    args=ap.parse_args()
    if args.out.exists():raise FileExistsError(args.out)
    src=json.loads(args.issuer_archive.read_text("utf8"))
    right=json.loads(args.previous_rights_halt.read_text("utf8"))
    panel=pd.read_parquet(args.historical_panel,
                          columns=["asset","date","index_member_asof","known_close_t"])
    calendar=pd.DatetimeIndex(pd.read_csv(args.calendar,header=None)[0])
    proof=reconstruct(src,args.original_issuer_pdfs,panel,calendar,
                      baseline_original_halt=right)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(proof,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps({k:v for k,v in proof.items() if k in (
        "independent_original_issuer_halt_resume_intervals",
        "newly_paired_issuer_halt_stock_session_count",
        "previously_verified_issuer_halt_stock_sessions",
        "unique_issuer_proven_halted_stock_session_union",
        "new_additional_halt_stock_sessions_not_in_prior",
    )},indent=2,ensure_ascii=False))


if __name__=="__main__":
    main()
