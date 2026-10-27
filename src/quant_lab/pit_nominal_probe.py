"""Run 3 preselected primary-issuer dividend proofs through a nominal book.

This is a no-trading validation, NOT full historical portfolio revaluation.
Source: independently fetched *unadjusted* daily open/close volume, backed by
a current vendor snapshot hash, plus pre-audited original issuer PDF hash.
"""
from __future__ import annotations

import argparse
from datetime import timedelta
import json
from pathlib import Path

import pandas as pd
import requests

from .pit_nominal_book import simulate_nominal_right
from .pit_primary_audit import fetch_independent_unadjusted_bars


TARGETS={
    ("SH600000","2021-07-21"),
    ("SH600000","2022-07-21"),
    ("SZ000001","2022-07-22"),
}


def previously_collected_real_unadjusted_marks(earlier:dict, issuer_event:dict, *, shares:int):
    """Use frozen source-provenance daily marks only; no fabricated price bars."""
    lookup=[r for r in earlier.get("rights",[])
            if r["symbol"]==issuer_event["symbol"] and r["ex_date"]==issuer_event["ex_date"]]
    if len(lookup)!=1:
        raise ValueError("Prior 2026-10-26 unadjusted source mark unavailable")
    r=lookup[0]
    sha=r["source_unadjusted_ohlcv"].get("response_body_sha256")
    if (r["source_issuer_pdf_sha256"]!=issuer_event["issuer_pdf_sha256"]
        or not sha or len(sha)!=64
        or r["shares_registered_nominal"]!=shares
        or abs(float(r["pre_tax_dividend_receivable"])
               -shares*float(issuer_event["gross_cash_per_nominal_share"]))>1e-5):
        raise ValueError("Frozen original PDF, quote hash or payout disagrees")
    if issuer_event.get("payment_date")!=issuer_event["ex_date"]:
        raise ValueError("Prior marks insufficient for later pay date")
    bars=pd.DataFrame([
        {"date":issuer_event["record_date"],
         "close_raw":r["registered_share_nominal_price_close"]},
        {"date":issuer_event["ex_date"],
         "close_raw":r["ex_date_share_nominal_price_close"]},
    ])
    for value in bars["close_raw"]:
        if not pd.notna(value) or float(value)<=0:
            raise ValueError("Invalid previously sourced unadjusted day mark")
    source={
        **r["source_unadjusted_ohlcv"],
        "data_reused_not_fetched_this_run":True,
        "only_record_and_ex_close_marks_reconstructed_from_prior_audit":True,
        "whole_response_body_not_rearchived_in_this_stage":True,
    }
    return bars,source


def run(ledger_file:Path, output:Path, *, shares=1000, previous_audit:Path|None=None):
    if output.exists():
        raise FileExistsError("Prior source evidence must not be overwritten")
    book=json.loads(ledger_file.read_text("utf-8"))
    lookup={(x["symbol"],x["ex_date"]):x for x in book["events"]
            if (x["symbol"],x["ex_date"]) in TARGETS}
    if set(lookup)!=TARGETS:
        raise ValueError("Pinned three original issuer cash actions absent")
    output.mkdir(parents=True, exist_ok=False)
    items=[]
    prior=json.loads(previous_audit.read_text("utf-8")) if previous_audit else None
    if prior is not None and prior.get("stage")!="REAL_PRIMARY_PDF_AND_SECONDARY_NOMINAL_RIGHTS_RECONCILIATION":
        raise ValueError("Wrong offline source evidence type")
    with requests.Session() as session:
        for key in sorted(TARGETS):
            e=lookup[key]
            rec=pd.Timestamp(e["record_date"])
            ex=pd.Timestamp(e["ex_date"])
            pay=pd.Timestamp(e["payment_date"]) if e.get("payment_date") else ex
            end=max(ex,pay)+timedelta(days=4)
            if prior is not None:
                bars,source=previously_collected_real_unadjusted_marks(
                    prior,e,shares=shares
                )
            else:
                bars,source=fetch_independent_unadjusted_bars(
                    session,e["symbol"],
                    start=(rec-timedelta(days=3)).date().isoformat(),
                    end=end.date().isoformat(),
                )
            # Reuse the entire real daily bar; strictly no inferred missing
            # exchange sessions are filled and no Qlib adjusted price is used.
            mark=simulate_nominal_right(
                e,bars[["date","close_raw"]],
                original_shares=shares,
                share_bonus_ratio=(0.0 if e["share_bonus_and_transfer_verified_zero"] else None),
                share_bonus_terms_officially_verified=bool(
                    e["share_bonus_and_transfer_verified_zero"]
                ),
            )
            label=f"{e['symbol']}_{e['ex_date']}"
            bars.to_csv(output/f"{label}_unadjusted_daily_bars.csv",index=False)
            item={
                "issuer_proof_key":label,
                "issuer_pub_date":e["announcement_day"],
                "issuer_original_pdf_sha256":e["issuer_pdf_sha256"],
                "independent_unadjusted_source":source,
                "historical_nominal_ledger":mark,
                "share_distribution_verified_zero":bool(
                    e["share_bonus_and_transfer_verified_zero"]
                ),
                "post_ex_stock_rights_mark_censored":mark[
                    "post_ex_stock_mark_censored_unknown_issuer_rights"],
                "unknown_stock_rights_not_treated_as_zero":True,
                "price_only_and_gross_cash_double_count_avoided":True,
                "actual_trade_confirmed":False,
            }
            items.append(item)
            pct=mark["ex_close_total_mark_change"]
            print(label,"pretax_cash",mark["pretax_entitlement"],
                  "mark_change",("CENSORED_INCOMPLETE_STOCK_RIGHTS" if pct is None
                                 else round(pct*100,3)),
                  "cash_only_assumption=",not e["share_bonus_and_transfer_verified_zero"],
                  "broker_posting_verified=False",flush=True)
    result={
        "kind":"EXP005_ORIGINAL_PDF_NOMINAL_MARK_AND_CASH_ENTITLEMENT_PROBE",
        "source_ledger_identity":"EXP005_CANONICAL_ISSUER_CASH_ENTITLEMENT_LEDGER",
        "n_pinned_real_issuer_events":len(items),
        "hypothetical_initial_nominal_shares_per_event":shares,
        "only_pretax_cash_nominal_units":True,
        "n_full_share_terms_verified_zero":sum(
            x["share_distribution_verified_zero"] for x in items
        ),
        "Qlib_adjusted_prices_not_used":True,
        "unadjusted_day_marks_reused_from_earlier_SHA256_audit":prior is not None,
        "network_fetch_executed_this_run":prior is None,
        "realized_trade_returns_not_tested":True,
        "real_broker_cash_credit_not_verified":True,
        "net_of_investor_specific_tax_not_claimed":True,
        "cannot_generalize_to_all_393_tickers":True,
        "items":items,
    }
    (output/"EXP005_nominal_probe.json").write_text(
        json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"
    )
    return result


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--ledger",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--shares",type=int,default=1000)
    p.add_argument("--previous-audit",type=Path)
    args=p.parse_args()
    run(args.ledger,args.output,shares=args.shares,previous_audit=args.previous_audit)


if __name__=="__main__":
    main()
