"""EXP-007: real source-driven stock-bonus/transfer and cash nominal-mark audit.

This is NOT tradeable equity performance. The same original issuer PDF
provides a validated gross cash and complete capital rights multiplier,
and independently acquired UNADJUSTED daily closes provide record/ex-day
nominal marks. The day's newly issued shares may be VALUABLE as rights but
not yet LISTED or credited for sale. Reconcile these separately.

Data source evidence has recorded HTTP response SHA256 and the exact saved
daily CSV SHA256; this cannot replay lost provider HTTP response bytes, so
archive-level TLS/vendor historical revision certification is NOT claimed.
"""
from __future__ import annotations

import argparse
from decimal import Decimal
import hashlib
import json
from pathlib import Path

import pandas as pd

from .pit_nominal_book import simulate_nominal_right


TARGETS = (
    ("SH600276", "2021-06-10"),
    ("SH600760", "2021-06-24"),
    ("SH603392", "2022-04-21"),
)


def _decimal(value) -> Decimal:
    result=Decimal(str(value))
    if not result.is_finite():
        raise ValueError("Invalid source numeric mark")
    return result


def _lookup(catalog: dict, ticker: str, exdate: str) -> dict:
    if catalog.get("kind")!="EXP007_ISSUER_ORIGINAL_BONUS_TRANSFER_AND_CASH_ENTITLEMENT_CATALOG":
        raise ValueError("Not an original issuer-verifiable rights catalog")
    found=[x for x in catalog["events"] if x["symbol"]==ticker and x["ex_date"]==exdate]
    if len(found)!=1:
        raise ValueError("No unique issuer-original dividend and stock-right event")
    x=found[0]
    if (not x["complete_rights_supported_by_issuer_original"]
        or x["full_new_nominal_share_multiplier"] is None):
        raise ValueError("Missing original issuer complete bonus/transfer rights")
    if not x["positive_stock_rights"]:
        raise ValueError("This study only evaluates source-positive share rights")
    if not (x["gross_cash_per_old_nominal_share"]>0
            and x["earliest_usable_exchange_day"] <= x["record_date"]):
        raise ValueError("Implausible source cash/time sequence")
    return x


def audit_single(
    rights: dict,
    quotes: pd.DataFrame,
    response: dict,
    *,
    csv_sha256: str,
    original_nominal_shares: int=1000,
) -> dict:
    if original_nominal_shares<1:
        raise ValueError("Must start with positive already-owned shares")
    digest=response.get("response_body_sha256","")
    if (response.get("source")!="EASTMONEY_PUBLIC_DAILY_UNADJUSTED_BAR"
        or len(digest)!=64 or len(csv_sha256)!=64):
        raise ValueError("Source response and archived daily CSV hashes required")
    needed={"date","close_raw","volume_lots","open_raw"}
    if not needed.issubset(quotes.columns):
        raise ValueError("Missing source daily traded-price/volume columns")
    bars=quotes.copy()
    bars["date"]=pd.to_datetime(bars["date"]).dt.normalize()
    if bars["date"].duplicated().any():
        raise ValueError("Duplicate source security/day")
    bars=bars.sort_values("date")
    if not (bars["close_raw"].gt(0).all()
            and bars["volume_lots"].gt(0).all()):
        raise ValueError("Missing/invalid historical actual daily close/volume")
    record=pd.Timestamp(rights["record_date"])
    ex=pd.Timestamp(rights["ex_date"])
    pre=bars.loc[bars.date.eq(record)]
    post=bars.loc[bars.date.eq(ex)]
    if len(pre)!=1 or len(post)!=1:
        raise ValueError("Original issuer record/ex days do not match unadjusted stock bars")
    p0=_decimal(pre["close_raw"].iloc[0])
    p1=_decimal(post["close_raw"].iloc[0])
    shares=_decimal(original_nominal_shares)
    mult=_decimal(rights["full_new_nominal_share_multiplier"])
    cash=_decimal(rights["gross_cash_per_old_nominal_share"])
    ratio=mult-Decimal(1)
    if mult<=1 or cash<=0 or ratio<=0:
        raise ValueError("Issuer positive stock transfer must be verified")
    if (rights["bonus_shares_per_old_share"] is None
        or rights["capital_transfer_shares_per_old_share"] is None):
        raise ValueError("Partial publisher rights cannot be valued fully")
    assert abs(( _decimal(rights["bonus_shares_per_old_share"])
                  +_decimal(rights["capital_transfer_shares_per_old_share"]))-ratio)<Decimal("1e-8")
    # Reuse the exact rights evaluator from EXP-005 and explicitly tell it
    # these ratios are original issuer/source-accounting verified, not broker
    # credited shares. NO model portfolio trades have occurred.
    event={
        "event_id":rights["event_id"],
        "symbol":rights["symbol"],
        "record_date":rights["record_date"],
        "ex_date":rights["ex_date"],
        "payment_date":rights["scheduled_cash_payment_day"],
        "gross_cash_per_nominal_share":rights["gross_cash_per_old_nominal_share"],
        "issuer_pdf_sha256":rights["issuer_original_pdf_sha256"],
        "evidence_grade":"ORIGINAL_ISSUER_PDF_PLUS_COMPANY_SHARE_BALANCE",
        "earliest_usable_exchange_day":rights["earliest_usable_exchange_day"],
    }
    if (event["payment_date"] and
        pd.Timestamp(event["payment_date"])>bars["date"].max()):
        # Missing a later issuer scheduled pay date is fine for a *record
        # and EX-only* mark. Never invent brokerage cash settlement.
        event["payment_date"]=None
        payment_source_status="SCHEDULED_PAY_DATE_KNOWN_OUTSIDE_BAR_WINDOW"
    else:
        payment_source_status=(
            "SOURCE_SCHEDULED_PAY_DATE_NOT_BROKER_POSTED" if event["payment_date"]
            else "SOURCE_PAY_DATE_UNAVAILABLE"
        )
    r=simulate_nominal_right(
        event,bars[["date","close_raw"]],
        original_shares=original_nominal_shares,
        share_bonus_ratio=float(ratio),
        share_bonus_terms_officially_verified=True,
    )
    expect_before=shares*p0
    expect_ex=shares*mult*p1+shares*cash
    if abs(_decimal(r["record_close_nominal_mark"])-expect_before)>Decimal("0.0001"):
        raise ValueError("Inconsistent pre-rights nominal company mark")
    if abs(_decimal(r["ex_close_including_gross_receivable_scenario"])-expect_ex)>Decimal("0.0001"):
        raise ValueError("Inconsistent ex-rights share/pretax cash mark")
    return {
        "symbol":rights["symbol"],"record_date":rights["record_date"],
        "ex_date":rights["ex_date"],"event_id":rights["event_id"],
        "issuer_original_pdf_sha256":rights["issuer_original_pdf_sha256"],
        "issuer_original_pdf_url":rights["issuer_original_pdf_url"],
        "issuer_capital_balance_source_grade":rights["rights_evidence"],
        "nominal_shares_hypothetically_owned_at_record":str(shares),
        "issuer_verified_bonus_per_old_share":rights["bonus_shares_per_old_share"],
        "issuer_verified_transfer_per_old_share":rights["capital_transfer_shares_per_old_share"],
        "issuer_verified_total_nominal_share_multiplier":float(mult),
        "nominal_shares_marked_on_ex_day":str(shares*mult),
        "nominal_record_day_raw_close":float(p0),
        "nominal_ex_day_raw_close":float(p1),
        "pretax_dividend_receivable":str(shares*cash),
        "record_day_mark":str(expect_before),
        "ex_day_stock_plus_gross_cash_entitlement_mark":str(expect_ex),
        "raw_price_only_change":float(p1/p0-1),
        "right_inclusive_mark_change":float(expect_ex/expect_before-1),
        "original_http_response_metadata_sha256":digest,
        "archived_local_unadjusted_CSV_sha256":csv_sha256,
        "broker_share_credit_verified":False,
        "broker_dividend_cash_credit_verified":False,
        "actual_ex_day_new_bonus_share_sellable_verified":False,
        "tax_net_received_not_proven":True,
        "non_Qlib_adjusted_prices_used":True,
        "cash_settlement_status":payment_source_status,
        "nominal_book":r,
    }


def run(catalog: Path, source_dir: Path, out: Path) -> dict:
    if out.exists():
        raise FileExistsError("No overwriting source entitlement experiments")
    source=json.loads(catalog.read_text("utf-8"))
    studied=[]
    for sym,ex in TARGETS:
        identity=_lookup(source,sym,ex)
        raw=source_dir/f"{sym}_{ex}_raw.csv"
        meta=source_dir/f"{sym}_{ex}_source.json"
        if not raw.is_file() or not meta.is_file():
            raise FileNotFoundError("Missing independently sourced raw daily price "+sym+" "+ex)
        bars=pd.read_csv(raw)
        evidence=json.loads(meta.read_text("utf-8"))
        result=audit_single(identity,bars,evidence,
                            csv_sha256=hashlib.sha256(raw.read_bytes()).hexdigest())
        studied.append(result)
        print("VERIFIED",sym,ex,"shares",result["nominal_shares_marked_on_ex_day"],
              "gross_cash",result["pretax_dividend_receivable"],
              "pretax_ex_return_mark",round(result["right_inclusive_mark_change"]*100,3),
              "actual_fill=False",flush=True)
    summary={
        "kind":"EXP007_ORIGINAL_ISSUER_CAPITAL_BALANCE_REAL_UNADJUSTED_NOMINAL_MARKS",
        "n_reconciled_publisher_rights_events":len(studied),
        "target_selection":"three issuer-original company-capital balanced positive stock-rights, chosen before raw price fetch",
        "broker_actual_execution_proven":False,
        "full_portfolio_total_return_proven":False,
        "issuer_scheduled_payment_is_not_broker_settlement":True,
        "historical_factor_release_vintage_proven":False,
        "original_quote_response_bodies_persisted":False,
        "vendor_response_sha256_recorded":True,
        "all_raw_quote_CSV_files_remain_gitignored":True,
        "results":studied,
    }
    out.mkdir(parents=True,exist_ok=False)
    (out/"audit.json").write_text(
        json.dumps(summary,indent=2,ensure_ascii=False)+"\n")
    return summary


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--rights-catalog",type=Path,required=True)
    p.add_argument("--source-daily-dir",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    x=p.parse_args()
    run(x.rights_catalog,x.source_daily_dir,x.out)


if __name__=="__main__":
    main()
