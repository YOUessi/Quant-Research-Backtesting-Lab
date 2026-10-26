"""EXP-008: exact primary original issuer PDF evidence for previously unresolved 35
historical CSI300 stock-session missing bars in 2021–2022.

The five categories are fixed in docs/EXP008_UNRESOLVED_HALT_RESEARCH.md.
All new claims require original issuer PDF SHA256, an explicit effective stock
halt/resume or rights-offering subscription timetable, full calendar coverage,
and Qlib already frozen PIT index membership with no positive day bars.

DO NOT treat a projected maximum suspension term as an actual full interval.
The separate 2021-06-16->06-22 SZ002024 interval is currently unconfirmed:
another later unrelated 6/23 announcement starts a new pause but is not a
formal dated resumption for the first. The five prior days stay UNKNOWN.
"""
from __future__ import annotations

import argparse
from datetime import date
import hashlib
import json
from pathlib import Path
import re

import pandas as pd
from pypdf import PdfReader


PDFS = {
    "SH601108_rights": (
        "SH601108_20220328_rights_halt.pdf",
        "b16c7c3ebb9d44c1245b2c7c66f007b7a956b2a0fd226d399dbaaab979e7b9b1",
        "https://static.cninfo.com.cn/finalpage/2022-03-28/1212698784.PDF",
        "2022-03-28",
    ),
    "SZ002142_rights": (
        "SZ002142_20211119_rights_issue.pdf",
        "eeb07c5bac99234b7453815cc92b3d49fb780fd25dce2f96ae3ba36280ef9079",
        "https://static.cninfo.com.cn/finalpage/2021-11-19/1211627064.PDF",
        "2021-11-19",
    ),
    "SZ002142_result": (
        "SZ002142_20211202_rights_result.pdf",
        "4375dadafc13620b5069c538b488c4f90f41bddabd6afa71d3aa1bd42e8eff80",
        "https://static.cninfo.com.cn/finalpage/2021-12-02/1211763892.PDF",
        "2021-12-02",
    ),
    "SZ000425_cash_option": (
        "SZ000425_20220729_cash_option_start.pdf",
        "663554d0b81e8296b7a1177fc48a1e5defa16c8ac5a307cb5add849b67ea89b7",
        "https://static.cninfo.com.cn/finalpage/2022-07-29/1214160175.PDF",
        "2022-07-29",
    ),
    "SZ000425_resume": (
        "SZ000425_20220817_resume.pdf",
        "d65103e3dac77abbcb1aa2b32903f136ff64a1087a2dad4504ea27e43baf70d0",
        "https://static.cninfo.com.cn/finalpage/2022-08-17/1214308336.PDF",
        "2022-08-17",
    ),
    "SZ002024_risk_warning": (
        "SZ002024_20220430_one_day.pdf",
        "26174d896c66d1b64ab764f5f47c6100e72a79a40769e6b55c5def3a3f4b254f",
        "https://static.cninfo.com.cn/finalpage/2022-04-30/1213266247.PDF",
        "2022-04-30",
    ),
    "SZ002812_resume": (
        "SZ002812_20210623_resume.pdf",
        "ce58093d667764a694ab99bbe5e1a280e8ce41515617961913bb5199568f58e9",
        "https://static.cninfo.com.cn/finalpage/2021-06-23/1210312708.PDF",
        "2021-06-23",
    ),
    "SZ002812_halt": (
        "SZ002812_1210239096.pdf",
        "df8c1f6c754ea9196eaa2a1795f0dd4a4e6f1b0bb6a22e66a3096821cdae69fc",
        "https://static.cninfo.com.cn/finalpage/2021-06-16/1210239096.PDF",
        "2021-06-16",
    ),
    "SZ002024_june_initial_halt": (
        "SZ002024_20210617_stop.pdf",
        "6badf9c53cdae03fa2b824ef20c5f3d0a35a43cc689ff05c234054bf8e1fda7d",
        "https://static.cninfo.com.cn/finalpage/2021-06-17/1210252853.PDF",
        "2021-06-17",
    ),
}

RULES = (
    {
        "symbol": "SH601108",
        "first": "2022-03-31",
        "resume": "2022-04-12",
        "sources": ("SH601108_rights",),
        "category": "ISSUER_ORIGINAL_RIGHTS_SUBSCRIPTION_CLEARING_RESUME_ONE_PDF",
    },
    {
        "symbol": "SZ002142",
        "first": "2021-11-24",
        "resume": "2021-12-02",
        "sources": ("SZ002142_rights", "SZ002142_result"),
        "category": "ISSUER_ORIGINAL_RIGHTS_SUBSCRIPTION_AND_RESULTS_TWO_PDFS",
    },
    {
        "symbol": "SZ000425",
        "first": "2022-08-01",
        "resume": "2022-08-17",
        "sources": ("SZ000425_cash_option", "SZ000425_resume"),
        "category": "ISSUER_ORIGINAL_CASH_OPTION_CONTINUOUS_HALT_AND_RESUME",
    },
    {
        "symbol": "SZ002024",
        "first": "2022-05-05",
        "resume": "2022-05-06",
        "sources": ("SZ002024_risk_warning",),
        "category": "ISSUER_ORIGINAL_ONE_FULL_DAY_ST_WARNING_HALT_AND_RESUME",
    },
    {
        "symbol": "SZ002812",
        "first": "2021-06-16",
        "resume": "2021-06-23",
        "sources": ("SZ002812_halt", "SZ002812_resume"),
        "category": "ISSUER_ORIGINAL_STOCK_AND_CONVERTIBLE_HALT_AND_RESUME",
    },
)


def _document(name: str, folders: tuple[Path, ...]) -> dict:
    source = PDFS[name]
    candidates=[p for root in folders for p in root.glob(source[0])]
    if len(candidates)!=1:
        raise ValueError("Exactly one archived primary PDF expected for "+name)
    file=candidates[0]
    raw=file.read_bytes()
    digest=hashlib.sha256(raw).hexdigest()
    if digest!=source[1]:
        raise ValueError("Original primary issuer PDF hash differs for "+name)
    contents="\n".join(page.extract_text() or "" for page in
                      PdfReader(file,strict=False).pages[:7])
    if len(contents)<100:
        raise ValueError("Issuer PDF text missing for "+name)
    return {
        "source_label":name,
        "sha256":digest,
        "url":source[2],
        "publication_calendar_day":source[3],
        "normalized_text":re.sub(r"\s+","",contents).replace("Ａ","A"),
    }


def _must(conditional: bool, label: str):
    if not conditional:
        raise ValueError("Issuer PDF effective trade restriction absent: "+label)


def _text_contains(regex: str, doc: dict) -> bool:
    return re.search(regex,doc["normalized_text"]) is not None


def _source_proves(rule:dict, docs:dict[str,dict]) -> dict:
    key=rule["symbol"]+"_"+rule["first"]
    if key=="SH601108_2022-03-31":
        v=docs["SH601108_rights"]
        _must(_text_contains(r"2022年3月31日至2022年4月8日为本次配股缴款期",v),"SH601108 rights payment period")
        _must(_text_contains(r"缴款期公司A股股票.{0,58}?全天停牌",v),"SH601108 actual stock all-day halt")
        _must(_text_contains(r"2022年4月11日为登记公司网上清算期.{0,58}?继续停牌一天",v),"SH601108 additional cleared session")
        _must(_text_contains(r"2022年4月12日开市起公司A股股票.{0,58}?复牌",v),"SH601108 exact resume")
    elif key=="SZ002142_2021-11-24":
        v=docs["SZ002142_rights"]
        end=docs["SZ002142_result"]
        _must(_text_contains(r"2021年11月24日.{0,25}?至2021年12月1日.{0,60}?宁波银行A股股票停止交易",v),"SZ002142 real rights issue no trade period")
        _must(_text_contains(r"自2021年12月2日开市起.{0,22}?公司A股股票复牌",end),"SZ002142 separate result/resumption")
    elif key=="SZ000425_2022-08-01":
        st=docs["SZ000425_cash_option"]
        ed=docs["SZ000425_resume"]
        _must(_text_contains(r"公司股票.{0,70}?(?:将自|自)2022年8月1日开市时起(?:开始)?停牌",st),"SZ000425 cash option halt start")
        _must(_text_contains(r"公司股票.{0,85}?自2022年8月17日开市时起复牌",ed),"SZ000425 final resumption")
    elif key=="SZ002024_2022-05-05":
        v=docs["SZ002024_risk_warning"]
        _must(_text_contains(r"股票交易2022年5月5日开市起停牌一天.{0,18}?2022年5月6日开市起复牌",v),"SZ002024 risk warning exact one-day halt")
        _must(_text_contains(r"2022年5月6日.{0,200}?日涨跌幅限制为5%",v),"SZ002024 risk warning 5 percent daily band")
    elif key=="SZ002812_2021-06-16":
        st=docs["SZ002812_halt"]
        ed=docs["SZ002812_resume"]
        _must(_text_contains(r"公司股票.{0,135}?自2021年6月16日开市起停牌",st),"SZ002812 halt not only bond conversion")
        _must(_text_contains(r"公司股票.{0,135}?(?:将于|于)2021年6月23日开市起复牌",ed),"SZ002812 actual stock resume")
    else:
        raise ValueError("Unregistered issuer category "+key)
    return {
        "symbol":rule["symbol"],
        "issuer_original_category":rule["category"],
        "first_halted_exchange_day":rule["first"],
        "first_resumed_exchange_day":rule["resume"],
        "issuer_source_docs":[{
            "sha256":docs[label]["sha256"],
            "url":docs[label]["url"],
            "publication_calendar_day":docs[label]["publication_calendar_day"],
        } for label in rule["sources"]],
        "issuer_pdf_exact_full_session_effect_verified":True,
        "actual_broker_execution_verified":False,
    }


def _previous_keys(prior_augmented:dict, previous_rights:dict,
                   calendar:list[str]) -> set[tuple[str,str]]:
    if (prior_augmented["kind"]!="EXP007_PAIRED_INDEPENDENT_ORIGINAL_ISSUER_HALT_RESUME_PROOFS"
        or previous_rights["kind"]!="EXP005_ORIGINAL_ISSUER_RIGHTS_ISSUE_PDF_HALT_PERIOD_AUDIT"):
        raise ValueError("Untrusted earlier issuer original docs")
    keys={(x["symbol"],d) for x in prior_augmented["pairs"]
          for d in x["halted_exchange_sessions"]}
    keys|={(x["symbol"],d) for x in previous_rights["recovered"]
           for d in x["issuer_halted_exchange_sessions"]}
    keys|={("SH600340",d) for d in calendar if "2021-01-29"<=d<"2021-02-19"}
    return keys


def evaluate(source_folders:tuple[Path,...], historical:pd.DataFrame,
             calendar:list[str], prior_augmented:dict,
             previous_rights:dict) -> dict:
    if not set(("asset","date","index_member_asof","known_close_t")).issubset(historical.columns):
        raise ValueError("Historical source Qlib panel lacks PIT fields")
    historic=historical.copy()
    historic["date"]=pd.to_datetime(historic["date"]).dt.strftime("%Y-%m-%d")
    missing={
        (x.asset,x.date)
        for x in historic.loc[
            historic["date"].between("2021-01-04","2022-12-30")
            & historic["index_member_asof"]
            & ~historic["known_close_t"]
        ].itertuples(index=False)
    }
    if len(missing)!=139:
        raise ValueError("Frozen 139 missing PIT constituent-days changed")
    trading_days=sorted(set(calendar))
    before=_previous_keys(prior_augmented,previous_rights,trading_days)
    if len(before)!=104 or not before.issubset(missing):
        raise ValueError("Original 104 verified halt source keys changed")
    docs={name:_document(name,source_folders) for rule in RULES
          for name in rule["sources"]}
    new=[]
    added=set()
    for rule in RULES:
        proof=_source_proves(rule,docs)
        dates=[d for d in trading_days if rule["first"]<=d<rule["resume"]]
        if not dates or rule["resume"] not in trading_days:
            raise ValueError("Issuer effective halt/resume date missing exchange calendar")
        if any((rule["symbol"],day) not in missing for day in dates):
            raise ValueError("Original issuer source asserts halt but Qlib has positive bar/absence in index")
        proof["n_halted_exchange_sessions"]=len(dates)
        proof["issuer_confirmed_halted_days"]=dates
        proof["publisher_announcement_intraday_knowledge_certified"]=False
        proof["trade_entry_halt_gate_certified_for_these_dates"]=True
        new.append(proof)
        for day in dates:
            key=(rule["symbol"],day)
            if key in added:
                raise ValueError("Duplicate source-covered missing stock-session")
            added.add(key)
    if added & before:
        raise ValueError("EXP008 newly claimed source gaps are already in prior proofs")
    remaining=sorted(missing-(before|added))
    return {
        "kind":"EXP008_ISSUER_ORIGINAL_EXTRA_UNRESOLVED_PRICE_GAP_PROOFS",
        "original_frozen_unavailable_member_stock_days":len(missing),
        "previous_issuer_original_verified_halt_stock_days":len(before),
        "additional_original_issuer_verified_halt_stock_days":len(added),
        "total_issuer_documented_halt_stock_days":len(before|added),
        "still_missing_original_verified_stoppage_or_resume_source":len(remaining),
        "proposed_max_duration_without_actual_resume_used":False,
        "original_issuer_doc_download_hash_pinned":True,
        "actual_issuer_daily_price_limit_levels_fetched":False,
        "realized_broker_order_receipts_fetched":False,
        "total_historical_139_missing_day_covered":not remaining,
        "remaining_unverified_stock_days":[
            {"symbol":s,"date":d,
             "reason":"NO_INDEPENDENT_ISSUER_RESUME_OR_EXPLICIT_FULL_INTERVAL_PROOF"}
            for s,d in remaining
        ],
        "official_pct_limit_observation_single_symbol":{
            "symbol":"SZ002024",
            "historical_issuer_ST_warning_announced_calendar_day":"2022-04-30",
            "effective_risk_warning_date":"2022-05-06",
            "issuer_stated_daily_limit_percent_after_effective_day":5,
            "is_precise_daily_limit_up_down_price_file":False,
            "actual_auction_fill_certified":False,
        },
        "additional_verified_issuer_intervals":new,
        "warning":"This validates no daily stock trading on issuer-proven suspended sessions, not executable orders on other days, historical auction capacity, or point-in-time corporate-action factor vintages.",
    }


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--new-original-pdf-folder",type=Path,required=True)
    ap.add_argument("--old-original-issuer-pdf-folder",type=Path,required=True)
    ap.add_argument("--historical-panel",type=Path,required=True)
    ap.add_argument("--exchange-calendar",type=Path,required=True)
    ap.add_argument("--augmented-prior-halt",type=Path,required=True)
    ap.add_argument("--previous-rights-halt",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    args=ap.parse_args()
    if args.out.exists():
        raise FileExistsError("Cannot overwrite historical original issuer PDF gap investigation")
    panel=pd.read_parquet(args.historical_panel,
        columns=["asset","date","index_member_asof","known_close_t"])
    dates=pd.read_csv(args.exchange_calendar,header=None)[0].astype(str).tolist()
    augmented=json.loads(args.augmented_prior_halt.read_text("utf-8"))
    previous=json.loads(args.previous_rights_halt.read_text("utf-8"))
    result=evaluate((args.new_original_pdf_folder,
                     args.old_original_issuer_pdf_folder),
                    panel,dates,augmented,previous)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",
                        encoding="utf-8")
    print(json.dumps({
        k:v for k,v in result.items() if k in (
            "original_frozen_unavailable_member_stock_days",
            "previous_issuer_original_verified_halt_stock_days",
            "additional_original_issuer_verified_halt_stock_days",
            "total_issuer_documented_halt_stock_days",
            "still_missing_original_verified_stoppage_or_resume_source",
            "official_pct_limit_observation_single_symbol",
        )
    },ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
