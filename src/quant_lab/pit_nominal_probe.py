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


def run(ledger_file:Path, output:Path, *, shares=1000):
    if output.exists():
        raise FileExistsError("Prior source evidence must not be overwritten")
    book=json.loads(ledger_file.read_text("utf-8"))
    lookup={(x["symbol"],x["ex_date"]):x for x in book["events"]
            if (x["symbol"],x["ex_date"]) in TARGETS}
    if set(lookup)!=TARGETS:
        raise ValueError("Pinned three original issuer cash actions absent")
    output.mkdir(parents=True, exist_ok=False)
    items=[]
    with requests.Session() as session:
        for key in sorted(TARGETS):
            e=lookup[key]
            rec=pd.Timestamp(e["record_date"])
            ex=pd.Timestamp(e["ex_date"])
            pay=pd.Timestamp(e["payment_date"]) if e.get("payment_date") else ex
            end=max(ex,pay)+timedelta(days=4)
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
                "price_only_and_gross_cash_double_count_avoided":True,
                "actual_trade_confirmed":False,
            }
            items.append(item)
            print(label,"pretax_cash",mark["pretax_entitlement"],
                  "mark_change",round(mark["ex_close_total_mark_change"]*100,3),
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
    args=p.parse_args()
    run(args.ledger,args.output,shares=args.shares)


if __name__=="__main__":
    main()
