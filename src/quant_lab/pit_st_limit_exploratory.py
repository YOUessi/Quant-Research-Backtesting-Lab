"""EXP-009: 2022 SZ002024 source-backed 5% ST daily band *derived* probe.

Original SZ002024 issuer announcement (2022-04-30, SHA pinned) establishes:
  2022-05-05 full-day suspension, 2022-05-06 first ST/resumption day,
  and a 5% percentage band, as of the prior issuer publication calendar day.
An independently archived unadjusted OHLCV feed gives previous-session close.

This audit computes indicative band levels (round-half-up to 0.01 CNY)
and compares actual open/high/low/close. It DOES NOT download or certify
official exchange per-security/day limit PRICE LEVEL files, opening auction
queue position, broker fills, market impact or rules for other securities.

A single-price day at a plausible down-limit with nonzero daily volume
is NOT evidence that OUR sell could fill. Conservatively withhold assumed
sell fills; do not edit EXP002 frozen results.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import json
from pathlib import Path
import re

import pandas as pd
from pypdf import PdfReader


ISSUER_SHA = "26174d896c66d1b64ab764f5f47c6100e72a79a40769e6b55c5def3a3f4b254f"
QUOTE_RESPONSE_SHA = "ab750691b60f2d21b97f499e7a94dbc7d876aae70290f677463ee2749711ce33"
SYMBOL = "SZ002024"
HALT_DAY = "2022-05-05"
FIRST_ST_DAY = "2022-05-06"
PROBE_DAYS = ("2022-05-06", "2022-05-09", "2022-05-10")
TICK = Decimal("0.01")
ST_PCT = Decimal("0.05")


def money(x) -> Decimal:
    d=Decimal(str(x))
    if not d.is_finite() or d<=0:
        raise ValueError("Invalid positive nominal market price")
    return d


def source_sha(path:Path, expected:str) -> str:
    if not path.is_file():
        raise FileNotFoundError(path)
    sha=hashlib.sha256(path.read_bytes()).hexdigest()
    if sha!=expected:
        raise ValueError(f"Source proof byte SHA256 does not match {path}")
    return sha


def verify_original_st_rule(document_text:str) -> dict:
    txt=re.sub(r"\s+","",document_text).replace("Ａ","A")
    clauses=[
        "证券代码：002024",
        "2022年5月5日开市起停牌一天",
        "2022年5月6日开市起复牌",
        "ST易购",
        "股票交易的日涨跌幅限制为5%",
    ]
    if not all(x in txt for x in clauses):
        raise ValueError("Issuer PDF lacks explicit risk warning, trading halt/resumption and 5% rule")
    return {
        "symbol":SYMBOL,
        "original_issuer_publication_day":"2022-04-30",
        "risk_warning_effective_day":FIRST_ST_DAY,
        "source_full_day_halt":HALT_DAY,
        "observed_rule_fraction":str(ST_PCT),
        "original_issuer_document_sha256":ISSUER_SHA,
        "publisher_exact_intraday_release_time_known":False,
        "actual_security_day_exchange_limit_levels_present_in_original_pdf":False,
    }


def derived_band(previous_actual_trade_close:Decimal, *, percent:Decimal=ST_PCT) -> tuple[Decimal,Decimal]:
    if previous_actual_trade_close<=0 or not 0<percent<1:
        raise ValueError("Invalid prior trade price or declared risk band fraction")
    upper=(previous_actual_trade_close*(Decimal(1)+percent)).quantize(TICK,rounding=ROUND_HALF_UP)
    lower=(previous_actual_trade_close*(Decimal(1)-percent)).quantize(TICK,rounding=ROUND_HALF_UP)
    if upper<=lower:
        raise ValueError("Degenerate derived stock price band")
    return upper,lower


def classify_auction_hypothesis(bars:pd.DataFrame, *, calendar:list[str]) -> list[dict]:
    """Posthoc 3-session one-price limit states; no assumed broker fills.

    Halt on May 5 allows a *previous TRADED close* of Apr 29 for May 6.
    This is intentionally narrower than an official exchange day-by-day
    applicable prior-close reference (which may depend on ex-rights).
    """
    need={"date","open_raw","high_raw","low_raw","close_raw","volume_lots"}
    if not need.issubset(bars.columns):
        raise ValueError("Missing real unadjusted OHLCV source columns")
    if bars.date.duplicated().any():
        raise ValueError("Duplicate raw trading session")
    if not (set(PROBE_DAYS)|{"2022-04-29"}).issubset(set(bars.date)):
        raise ValueError("Pinned last pre-ST traded close and first 3 ST session raw bars missing")
    exchange_dates=sorted(set(calendar))
    if not (HALT_DAY in exchange_dates and HALT_DAY not in set(bars.date)):
        raise ValueError("Publisher confirmed suspension not corroborated by raw source market calendar")
    if FIRST_ST_DAY not in exchange_dates:
        raise ValueError("First original issuer ST session not on exchange calendar")
    rows=bars.set_index("date")
    previous_actual_day="2022-04-29"
    outcome=[]
    for when in PROBE_DAYS:
        expected_previous=exchange_dates[exchange_dates.index(when)-1]
        if when==FIRST_ST_DAY:
            if expected_previous!=HALT_DAY:
                raise ValueError("Unexpected exchange calendar around frozen ST risk start")
        elif previous_actual_day!=expected_previous:
            raise ValueError("Trading day gap beyond documented one-day halt")
        prev=money(rows.loc[previous_actual_day, "close_raw"])
        upper,lower=derived_band(prev)
        source=rows.loc[when]
        four={name:money(source[name]) for name in ("open_raw","high_raw","low_raw","close_raw")}
        if money(source["volume_lots"])<=0:
            raise ValueError("Historical ST price source lacks positive daily trading volume")
        if not four["high_raw"]>=max(four["open_raw"],four["close_raw"],four["low_raw"]):
            raise ValueError("Inconsistent actual market daily high")
        if not four["low_raw"]<=min(four["open_raw"],four["close_raw"],four["high_raw"]):
            raise ValueError("Inconsistent actual market daily low")
        plausible_down_limit_locked=all(abs(price-lower)<=Decimal("0.005") for price in four.values())
        if not plausible_down_limit_locked:
            raise ValueError("Pinned historical one-price market session not consistent with original ST 5% band")
        outcome.append({
            "symbol":SYMBOL,
            "trade_day":when,
            "prior_actual_traded_stock_day":previous_actual_day,
            "prior_unadjusted_close":str(prev),
            "original_issuer_declared_st_band_percentage":"5%",
            "derived_limit_up_price_NOT_OFFICIAL":str(upper),
            "derived_limit_down_price_NOT_OFFICIAL":str(lower),
            "observed_raw_open":str(four["open_raw"]),
            "observed_raw_high":str(four["high_raw"]),
            "observed_raw_low":str(four["low_raw"]),
            "observed_raw_close":str(four["close_raw"]),
            "observed_positive_daily_volume_lots":str(source["volume_lots"]),
            "historical_one_price_down_at_derived_issuer_band":True,
            "conservative_hypothetical_sell_queue_status":
                "DO_NOT_ASSUME_NEXT_OPEN_SELL_FILL_QUEUE_UNVERIFIED",
            "hypothetical_buy_fill_auction_depth_certified":False,
            "official_exchange_daily_up_down_PRICE_LEVELS_fetched":False,
            "real_broker_execution_receipt":False,
        })
        previous_actual_day=when
    return outcome


def audit(*, original_issuer_pdf:Path, independent_unadjusted_csv:Path,
          independent_source_meta:Path, exchange_calendar:Path) -> dict:
    source_sha(original_issuer_pdf,ISSUER_SHA)
    pdf=PdfReader(original_issuer_pdf,strict=False)
    text="\n".join(page.extract_text() or "" for page in pdf.pages[:4])
    issuer=verify_original_st_rule(text)
    meta=json.loads(independent_source_meta.read_text("utf-8"))
    # Stage-4 archived the original Eastmoney response provenance inside a
    # multi-stock audit. Never treat the summary's own SHA as the raw HTTP
    # response SHA; identify exactly the specified security.
    if meta.get("kind")=="INDEPENDENT_DAILY_OHLCV_VS_QLIB_MEMBER_DAY_GAP":
        matches=[x for x in meta.get("audits",[]) if x.get("symbol")==SYMBOL]
        if len(matches)!=1:
            raise ValueError("Expected one independently retrieved raw trading-day source for target ticker")
        meta=matches[0]["independent_source"]
    if meta.get("source_response_sha256")!=QUOTE_RESPONSE_SHA:
        raise ValueError("Raw independent historical provider body SHA no longer pinned")
    if meta.get("source_url") != "https://push2his.eastmoney.com/api/qt/stock/kline/get":
        raise ValueError("Unexpected independent unadjusted source")
    rows=pd.read_csv(independent_unadjusted_csv, dtype={"date":str})
    dates=pd.read_csv(exchange_calendar,header=None)[0].astype(str).tolist()
    checks=classify_auction_hypothesis(rows,calendar=dates)
    return {
        "kind":"EXP009_ISSUER_ORIGINAL_ST_5PCT_RAW_DAILY_PRICE_LEVEL_INDICATIVE_PROBE",
        "source_issuer_verified_ST_rule":issuer,
        "source_original_issuer_pdf_url":"https://static.cninfo.com.cn/finalpage/2022-04-30/1213266247.PDF",
        "independent_historical_raw_OHLCV_response_SHA256":QUOTE_RESPONSE_SHA,
        "independent_local_derived_raw_daily_CSV_SHA256":
            hashlib.sha256(independent_unadjusted_csv.read_bytes()).hexdigest(),
        "issuer_calendar_and_ohlcv_crosscheck_2022_05_05_halt":True,
        "n_historical_consecutive_one_price_down_sessions":len(checks),
        "one_price_down_session_details":checks,
        "st_5percent_effective_known_from_prior_issuer_original_publication":True,
        "official_daily_limit_up_down_price_file_not_obtained":True,
        "exchange_corporate_adjusted_prev_close_reference_audited":False,
        "actual_open_auction_sell_queue_fills_observed":False,
        "daily_positive_volume_does_not_prove_sell_at_down_limit":True,
        "frozen_prior_model_retuned_or_returns_rewritten":False,
        "interpretation":"Observed three real 2022 May one-price down sessions consistent with an original issuer 5% ST disclosure and preceding traded raw closes. Lower-price levels are DERIVED and not original official per-day limit price records. Censor unproven model sells and broker execution claims.",
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--original-st-pdf",type=Path,required=True)
    p.add_argument("--independent-raw-daily",type=Path,required=True)
    p.add_argument("--independent-source-meta",type=Path,required=True)
    p.add_argument("--exchange-calendar",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    args=p.parse_args()
    if args.out.exists():
        raise FileExistsError("Refuse to overwrite prior original-source ST evidence")
    result=audit(
        original_issuer_pdf=args.original_st_pdf,
        independent_unadjusted_csv=args.independent_raw_daily,
        independent_source_meta=args.independent_source_meta,
        exchange_calendar=args.exchange_calendar
    )
    result["audited_at_utc"]=datetime.now(timezone.utc).isoformat()
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({
        "symbol":SYMBOL,
        "issuer_rule":"5pct ST original",
        "one_price_down_sessions":len(result["one_price_down_session_details"]),
        "days":[x["trade_day"] for x in result["one_price_down_session_details"]],
        "open_auction_sell_fill_certified":False,
    },ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
