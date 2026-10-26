"""EXP-006: crosscheck issuer cash/transfer and the current Qlib factor step.

A post-hoc adjusted-factor arithmetic consistency check is NOT evidence that
the factor was released in its historical decision-day vintage. It is also
NOT the issuer's or broker's actual cash/share settlement certificate.

Requires a separately sourced UNADJUSTED close and an issuer-original event
with fully known share rights. Do not infer split rights from Qlib factor.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd


SYMBOL="SZ300751"
EX_DAY="2022-04-14"


def audit(cash:dict,share:dict, qlib:pd.DataFrame,
          independent:pd.DataFrame, *, quote_sha256:str) -> dict:
    events=[x for x in cash["events"]
            if x["symbol"]==SYMBOL and x["ex_date"]==EX_DAY]
    if len(events)!=1:
        raise ValueError("Unique original cash event not found")
    e=events[0]
    rights=[x for x in share["audit"] if x["event_id"]==e["event_id"]]
    if len(rights)!=1 or rights[0]["issuer_pdf_sha256"]!=e["issuer_pdf_sha256"]:
        raise ValueError("Rights proof missing or inconsistent")
    r=rights[0]
    if not r["known_complete"] or not r["known_positive_stock_rights"]:
        raise ValueError("This crosscheck requires source-verified stock right multiplier")
    if r["independent_transfer_ratio_crosscheck"]!="MATCH":
        raise ValueError("Transfer ratio lacks secondary aggregator match")
    if not quote_sha256 or len(quote_sha256)!=64:
        raise ValueError("Independent quote response SHA missing")
    q=qlib.copy()
    z=independent.copy()
    for df in (q,z):
        df["date"]=pd.to_datetime(df["date"]).dt.normalize()
    q=q[q["asset"].eq(SYMBOL)]
    if q.duplicated("date").any() or z.duplicated("date").any():
        raise ValueError("Duplicate historical daily price date")
    combined=q.merge(z,on="date",how="inner",validate="one_to_one")
    record=pd.Timestamp(e["record_date"])
    ex=pd.Timestamp(EX_DAY)
    if len(combined.loc[combined.date.eq(record)])!=1 or len(combined.loc[combined.date.eq(ex)])!=1:
        raise ValueError("Cannot align original/ex Qlib and independent raw prices")
    pre=combined.loc[combined.date.eq(record)].iloc[0]
    xd=combined.loc[combined.date.eq(ex)].iloc[0]
    previous_close=float(pre["close_raw"])
    ex_close=float(xd["close_raw"])
    if previous_close<=0 or ex_close<=0:
        raise ValueError("Invalid real original-price closes")
    cash_per_share=float(e["gross_cash_per_nominal_share"])
    mult=float(r["full_nominal_share_multiplier_issuer_verified"])
    if not (mult>1 and cash_per_share>0 and previous_close>cash_per_share):
        raise ValueError("Invalid source-verified corporate factor assumptions")
    predicted_xd_ref=(previous_close-cash_per_share)/mult
    predicted_factor_jump=previous_close/predicted_xd_ref
    observed_jump=float(xd["factor_step_ratio"])
    if not np.isfinite(observed_jump) or observed_jump<=0:
        raise ValueError("Invalid Qlib adjusted factor step")
    price_errors=[abs(float(row["raw_close_estimate"])-float(row["close_raw"]))
                  for _,row in combined.iterrows()]
    max_price_error=max(price_errors)
    if max_price_error>0.0051:
        raise ValueError("Cross-source nominal price mismatch beyond tick half-cent")
    relative_factor_diff=observed_jump/predicted_factor_jump-1.0
    return {
        "kind":"EXP006_ISSUER_CORPORATE_ACTION_VS_2026_QLIB_FACTOR_ARITHMETIC_CHECK",
        "symbol":SYMBOL,
        "ex_date":EX_DAY,
        "issuer_original_pdf_sha256":e["issuer_pdf_sha256"],
        "issuer_original_url":e["issuer_pdf_url"],
        "last_cum_rights_nominal_close":previous_close,
        "ex_date_nominal_close":ex_close,
        "issuer_cash_per_old_share_pre_tax":cash_per_share,
        "issuer_stock_transfer_nominal_share_multiplier":mult,
        "theoretical_ex_reference_price_from_prior_close":predicted_xd_ref,
        "theoretical_backward_factor_step_from_source_rights":predicted_factor_jump,
        "qlib_2026_snapshot_observed_factor_step":observed_jump,
        "relative_qlib_factor_step_minus_theoretical":relative_factor_diff,
        "max_abs_price_difference_Qlib_reconstructed_vs_independent_raw":max_price_error,
        "source_quote_2026_http_response_sha256":quote_sha256,
        "factor_arithmetic_consistent_with_simple_corporate_formula_within_0_05pct":
            abs(relative_factor_diff)<0.0005,
        "independent_raw_prices_correspond_on_global_trading_days":True,
        "issuer_rights_are_checked_independently_of_qlib_factor":True,
        "historical_decision_day_adjustment_factor_version_proven":False,
        "broker_corporate_action_credit_proven":False,
        "full_investment_portfolio_return_proven":False,
        "reconciliation_scope":"Single issuer, known dividend/transfer ex-day; retrospective 2026 source snapshots only",
    }


def run(cash_file:Path,share_file:Path,qlib_file:Path,
        raw_file:Path,source_file:Path,out:Path):
    if out.exists():
        raise FileExistsError("Refusing to overwrite source factor audit")
    cash=json.loads(cash_file.read_text("utf-8"))
    share=json.loads(share_file.read_text("utf-8"))
    src=json.loads(source_file.read_text("utf-8"))
    q=pd.read_parquet(qlib_file,columns=[
        "date","asset","raw_close_estimate","factor_step_ratio"])
    independent=pd.read_csv(raw_file)
    report=audit(cash,share,q,independent,
                 quote_sha256=src["response_body_sha256"])
    report["independent_unadjusted_daily_csv_sha256"]=hashlib.sha256(
        raw_file.read_bytes()).hexdigest()
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",
                   encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2))


def main():
    p=argparse.ArgumentParser()
    for name in ("cash-ledger","share-audit","qlib-parquet",
                 "raw-bars","raw-source","out"):
        p.add_argument("--"+name,type=Path,required=True)
    a=p.parse_args()
    run(a.cash_ledger,a.share_audit,a.qlib_parquet,a.raw_bars,
        a.raw_source,a.out)


if __name__=="__main__":
    main()
