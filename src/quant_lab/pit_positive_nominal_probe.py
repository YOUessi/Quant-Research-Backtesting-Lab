"""EXP-006 real source-backed 2022 SZ300751 capitalization-transfer pilot.

Original issuer PDF confirms: cash CNY 1.50 per nominal share,
no bonus shares, 6 additional capitalized shares per 10 existing.
Earlier independent 2022-04 Eastmoney fqt=0 raw daily prices were acquired
and saved locally with a recorded HTTP response SHA256. This probe NEVER
uses Qlib adjusted prices and NEVER claims broker execution, holder-specific
aftertax credit, or a historical factor-publisher vintage.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

from .pit_nominal_book import simulate_nominal_right


SYMBOL="SZ300751"
EX="2022-04-14"


def run(cash_file: Path, right_file: Path, bars_file: Path,
        source_file: Path, *, output: Path, shares: int=1000) -> dict:
    if output.exists():
        raise FileExistsError("Refusing to overwrite recorded source evidence")
    cash=json.loads(cash_file.read_text(encoding="utf-8"))
    rights=json.loads(right_file.read_text(encoding="utf-8"))
    events=[e for e in cash["events"] if
            e["symbol"]==SYMBOL and e["ex_date"]==EX]
    if len(events)!=1:
        raise ValueError("Unique original-issuer 2022 dividend event missing")
    e=events[0]
    matches=[r for r in rights["audit"] if
             r["event_id"]==e["event_id"]]
    if len(matches)!=1:
        raise ValueError("Unique original-issuer capitalization record missing")
    r=matches[0]
    if r["issuer_pdf_sha256"]!=e["issuer_pdf_sha256"]:
        raise ValueError("Issuer record source SHA disagreement")
    if not r["known_complete"] or not r["known_positive_stock_rights"]:
        raise ValueError("Both stock distribution and transfer terms must be issuer-known")
    if r["independent_transfer_ratio_crosscheck"]!="MATCH":
        raise ValueError("Issuer capital transfer ratio lacks independent vendor crosscheck")
    if (r["bonus_ratio_per_nominal_share"]!=0
            or abs(r["transfer_ratio_per_nominal_share"]-0.6)>1e-12):
        raise ValueError("Unexpected issuer-verified 10-to-6 nominal share distribution")
    source=json.loads(source_file.read_text("utf-8"))
    digest=source.get("response_body_sha256","")
    if not (len(digest)==64 and source.get("source")==
            "EASTMONEY_PUBLIC_DAILY_UNADJUSTED_BAR"):
        raise ValueError("Raw independent price source metadata invalid")
    bars=pd.read_csv(bars_file,dtype={"date":str})
    cols={"date","open_raw","close_raw","volume_lots","amount_currency"}
    if not cols.issubset(bars.columns):
        raise ValueError("Historical raw OHLCV missing")
    if bars["date"].duplicated().any():
        raise ValueError("Duplicate trade dates")
    if not (bars["close_raw"].gt(0).all()
            and bars["volume_lots"].gt(0).all()):
        raise ValueError("Source day has missing positive close/volume")
    if str(e["record_date"]) not in set(bars.date) or str(e["ex_date"]) not in set(bars.date):
        raise ValueError("Source record/ex session daily bars missing")
    record=float(bars.loc[bars.date.eq(e["record_date"]),"close_raw"].iloc[0])
    exclose=float(bars.loc[bars.date.eq(e["ex_date"]),"close_raw"].iloc[0])
    modeled=simulate_nominal_right(
        e,bars[["date","close_raw"]],
        original_shares=shares,
        share_bonus_ratio=(
            float(r["bonus_ratio_per_nominal_share"])
            +float(r["transfer_ratio_per_nominal_share"])
        ),
        share_bonus_terms_officially_verified=True,
    )
    exrow=next(x for x in modeled["records"] if x["date"]==EX)
    if abs(float(exrow["nominal_shares"])-shares*1.6)>1e-6:
        raise AssertionError("Incorrect corporate-action 10-to-6 shares")
    before=shares*record
    after=shares*1.6*exclose+shares*float(e["gross_cash_per_nominal_share"])
    if abs(float(modeled["ex_close_including_gross_receivable_scenario"])-after)>1e-5:
        raise AssertionError("Nominal-price + cash payout reconciliation failed")
    output.mkdir(parents=True,exist_ok=False)
    details={
        "kind":"EXP006_REAL_ORIGINAL_ISSUER_CASH_AND_STOCK_TRANSFER_NOMINAL_PRICE_MARK",
        "ticker":SYMBOL,
        "issuer_pub_calendar_day":e["announcement_day"],
        "issuer_record_date":e["record_date"],
        "issuer_ex_date":EX,
        "issuer_payment_date_from_original":e["payment_date"],
        "issuer_original_pdf_sha256":e["issuer_pdf_sha256"],
        "issuer_original_pdf_url":e["issuer_pdf_url"],
        "current_thirdparty_TRANSFER_ratio_crosscheck":r["independent_transfer_ratio_crosscheck"],
        "issuer_bonus_per_ten_shares":0,
        "issuer_transfer_per_ten_shares":6,
        "issuer_cash_per_old_share_pre_tax":e["gross_cash_per_nominal_share"],
        "initial_nominal_shares_hypothetical":shares,
        "nominal_shares_after_ex":shares*1.6,
        "record_close_raw_unadjusted":record,
        "ex_close_raw_unadjusted":exclose,
        "record_nominal_market_mark":before,
        "ex_nominal_market_mark_plus_pretax_receivable":after,
        "price_only_change":exclose/record-1,
        "entitlement_aware_nominal_mark_change":after/before-1,
        "pretax_cash_receivable":shares*float(e["gross_cash_per_nominal_share"]),
        "underlying_independent_raw_daily_csv_sha256":
            hashlib.sha256(bars_file.read_bytes()).hexdigest(),
        "underlying_independent_source_response_sha256":digest,
        "source_retrieved_utc":source.get("retrieved_utc"),
        "local_original_issuer_broker_payment_ledger":False,
        "issuer_actual_pay_date_not_yet_verified":e["payment_date"] is None,
        "today_vendor_snapshot_not_historical_factor_vintage":True,
        "source_data_price_adjusted":False,
        "zero_real_broker_fills_observed":True,
        "not_full_investment_portfolio_return":True,
        "notes":[
            "Record close includes cum-rights price; ex close includes adjusted nominal shares plus gross pre-tax cash entitlement once.",
            "Share addition is a source-verified accounting right, NOT proof a brokerage credited issued shares.",
            "Source daily bar volume does not prove the investor can trade at the raw opening price.",
            "Original 2021 SZ300751 event had transfer=8 per 10 but unknown zero-bonus clause; no fully verified valuation is produced for 2021.",
        ],
        "nominal_book":modeled,
    }
    (output/"EXP006_nominal_verified_transfer.json").write_text(
        json.dumps(details,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in details.items() if k in (
        "ticker","issuer_ex_date","initial_nominal_shares_hypothetical",
        "nominal_shares_after_ex","pretax_cash_receivable",
        "record_nominal_market_mark","ex_nominal_market_mark_plus_pretax_receivable",
        "price_only_change","entitlement_aware_nominal_mark_change",
    )},indent=2))
    return details


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--cash-ledger",type=Path,required=True)
    p.add_argument("--share-audit",type=Path,required=True)
    p.add_argument("--raw-bars",type=Path,required=True)
    p.add_argument("--raw-source-meta",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--shares",type=int,default=1000)
    args=p.parse_args()
    run(args.cash_ledger,args.share_audit,args.raw_bars,
        args.raw_source_meta,output=args.out,shares=args.shares)


if __name__=="__main__":
    main()
