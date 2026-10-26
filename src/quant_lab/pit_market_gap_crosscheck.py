"""Audit missing Qlib index-constituent OHLCV against an independent daily feed.

Daily OHLCV cross-source agreement is not proof of *legal halt* or auction
order execution. An absence in both feeds is labeled UNCONFIRMED until an
issuer/exchange announcement establishes the suspension interval.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time

import pandas as pd
import requests

URL="https://push2his.eastmoney.com/api/qt/stock/kline/get"
FIELDS2="f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61"


def classify_missing(missing_days: set[str],
                     independent_trade_days: set[str]) -> dict:
    """No future bar fills or invented no-trade status."""
    matched=sorted(missing_days & independent_trade_days)
    absent=sorted(missing_days-independent_trade_days)
    return {
        "qlib_missing_eastmoney_positive_daily_bar": matched,
        "qlib_missing_no_eastmoney_daily_bar_UNCONFIRMED_HALT": absent,
        "cross_source_presence_discrepancies":len(matched),
        "both_daily_sources_absent_not_official_halt_certificate":len(absent),
        "auction_order_fill_certified":False,
    }


def independent_daily(session:requests.Session, symbol:str,
                      *,first:str,last:str) -> tuple[pd.DataFrame,dict]:
    if not (len(symbol)==8 and symbol[:2] in ("SH","SZ")):
        raise ValueError("This Eastmoney feed adapter only supports SH/SZ")
    secid=("1." if symbol.startswith("SH") else "0.")+symbol[2:]
    params={
        "secid":secid,
        "ut":"fa5fd1943c7b386f172d6893dbfba10b",
        "fields1":"f1,f2,f3,f4,f5,f6",
        "fields2":FIELDS2,"klt":101,"fqt":0,
        "beg":first.replace("-",""),"end":last.replace("-",""),
        "lmt":1000,
    }
    res=session.get(URL,params=params,headers={"User-Agent":"Mozilla/5.0"},
                    timeout=(7,17))
    res.raise_for_status()
    info=res.json()
    data=info.get("data") or {}
    if data.get("code")!=symbol[2:]:
        raise ValueError("Eastmoney returned wrong security code")
    lines=data.get("klines") or []
    if not lines:
        raise ValueError("Missing independent daily bar data")
    record=[]
    for line in lines:
        values=line.split(",")
        if len(values)<7:
            raise ValueError("Unexpected daily OHLCV serialization")
        date=values[0]
        if not first<=date<=last:
            raise ValueError("Eastmoney unexpected out-of-range daily bar")
        record.append({
            "date":date,"open_raw":float(values[1]),
            "close_raw":float(values[2]),
            "high_raw":float(values[3]),"low_raw":float(values[4]),
            "volume_lots":float(values[5]),
            "amount_currency":float(values[6]),
        })
    frame=pd.DataFrame(record)
    if frame.date.duplicated().any():
        raise ValueError("Multiple bars on same date")
    # "positive daily trade" needs a recorded trade and positive prices/volume,
    # NOT proof of executable quantity at the open.
    return frame,{
        "source":"Eastmoney fqt=0 unadjusted daily stock bars",
        "source_url":URL,
        "source_response_sha256":hashlib.sha256(res.content).hexdigest(),
        "retrieval_utc":datetime.now(timezone.utc).isoformat(),
        "n_raw_bars":len(frame),
        "first_raw_bar":str(frame.date.min()),
        "last_raw_bar":str(frame.date.max()),
        "official_suspension_certification":False,
        "auction_depth_or_queue_data_available":False,
    }


def audit(panel:pd.DataFrame, output:Path, *,
          first:str="2021-01-04",last:str="2022-12-30",
          pacing:float=.55) -> dict:
    if output.exists():
        raise FileExistsError("Source crosscheck folder exists; never overwrite")
    if pacing<.3:
        raise ValueError("Public source access must stay low-rate")
    required={"date","asset","index_member_asof","known_close_t"}
    if not required.issubset(panel.columns):
        raise ValueError("Missing frozen historical Qlib panel columns")
    frame=panel.loc[
        panel["date"].between(first,last)
        & panel["index_member_asof"]
    ].copy()
    missing=frame.loc[~frame["known_close_t"]].copy()
    if missing.empty:
        raise ValueError("No Qlib member-day gaps to audit")
    missing["trade_date"]=missing.date.dt.strftime("%Y-%m-%d")
    byticker=missing.groupby("asset")["trade_date"].agg(
        lambda x:set(x.tolist())
    )
    output.mkdir(parents=True,exist_ok=False)
    rawdir=output/"independent_unadjusted_market"
    rawdir.mkdir()
    good,failed=[],[]
    with requests.Session() as session:
        for i,(symbol,dates) in enumerate(byticker.items(),1):
            try:
                bars,meta=independent_daily(
                    session,symbol,first=first,last=last
                )
                tradable=set(bars.loc[
                    bars.open_raw.gt(0)&bars.close_raw.gt(0)
                    &bars.volume_lots.gt(0), "date"
                ].tolist())
                result={
                    "symbol":symbol,"n_qlib_member_day_gaps":len(dates),
                    **classify_missing(dates,tradable),
                    "independent_source":meta,
                }
                good.append(result)
                bars.to_csv(rawdir/f"{symbol}.csv",index=False)
                print(f"[{i}/{len(byticker)}] {symbol}: {len(dates)} "
                      f"Qlib missing, {result['cross_source_presence_discrepancies']} "
                      "present in independent daily data",flush=True)
            except Exception as e:
                failed.append({"symbol":symbol,"n_qlib_gaps":len(dates),
                               "type":type(e).__name__,"message":str(e)[:220]})
                print(f"[{i}/{len(byticker)}] ERROR {symbol}: "
                      f"{type(e).__name__}: {str(e)[:80]}",flush=True)
            time.sleep(pacing)
    summary={
        "kind":"INDEPENDENT_DAILY_OHLCV_VS_QLIB_MEMBER_DAY_GAP",
        "original_source":"Qlib 2026-10-25 adjusted snapshot",
        "independent_source":"Eastmoney fqt=0 raw daily OHLCV",
        "period":[first,last],
        "qlib_missing_member_days":len(missing),
        "qlib_missing_distinct_tickers":len(byticker),
        "tickers_audited":len(good),
        "tickers_failed":len(failed),
        "missing_member_days_with_independent_positive_trade_bars":sum(
            x["cross_source_presence_discrepancies"] for x in good
        ),
        "missing_member_days_both_sources_absent_NOT_OFFICIAL_HALT":sum(
            x["both_daily_sources_absent_not_official_halt_certificate"]
            for x in good
        ),
        "original_provider_presence_discrepancies_are_not_automatically_repaired":True,
        "independent_daily_trade_not_an_auction_fill":True,
        "broker_tradability_certified_for_entire_universe":False,
        "audits":good,"failures":failed,
    }
    (output/"summary.json").write_text(
        json.dumps(summary,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    return summary


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--historical-panel",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--delay",type=float,default=.55)
    args=p.parse_args()
    data=pd.read_parquet(args.historical_panel,
                         columns=["date","asset","index_member_asof","known_close_t"])
    summary=audit(data,args.out,pacing=args.delay)
    print(json.dumps({
        key:summary[key] for key in (
            "qlib_missing_member_days","qlib_missing_distinct_tickers",
            "tickers_audited","tickers_failed",
            "missing_member_days_with_independent_positive_trade_bars",
            "missing_member_days_both_sources_absent_NOT_OFFICIAL_HALT",
        )
    },indent=2,ensure_ascii=False))


if __name__=="__main__":
    main()
