"""Replay issuer-verified halt evidence over frozen EXP-002 attempted orders.

This is an evidence overlay, NOT a rewritten portfolio simulation. A verified
halt is known for an entire exchange session after the issuer's original
document gives an effective opening date. The event is applied on trade date,
never inserted as a future feature on an earlier decision date.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


def _official_halt_dates(issuer_audit: dict,
                         exchange_calendar: pd.DatetimeIndex) -> tuple[str, str, set[str]]:
    proofs=issuer_audit.get("verified_documents",[])
    start=[x for x in proofs if
           x.get("symbol")=="SH600340"
           and x.get("suspended_from_open_pdf_confirmed")]
    resume=[x for x in proofs if
            x.get("symbol")=="SH600340"
            and x.get("resumed_from_open_pdf_confirmed")]
    if len(start)!=1 or len(resume)!=1:
        raise ValueError("Missing unique issuer-original halt/resumption evidence")
    if not (start[0].get("primary_document_sha256")
            and resume[0].get("primary_document_sha256")):
        raise ValueError("Primary issuer PDF hash missing")
    begin=start[0]["suspended_from_open_pdf_confirmed"]
    end=resume[0]["resumed_from_open_pdf_confirmed"]
    if begin>=end:
        raise ValueError("Invalid official halt chronology")
    exchange_dates={x.date().isoformat() for x in exchange_calendar
                    if pd.Timestamp(begin)<=x<pd.Timestamp(end)}
    if len(exchange_dates)!=10:
        raise ValueError("Unexpected count vs original 10-session halt proof")
    return begin,end,exchange_dates


def replay_halt_events(
    events: pd.DataFrame, issuer_audit: dict,
    calendar: pd.DatetimeIndex,
) -> dict:
    if not {"date","asset","side","status"}.issubset(events.columns):
        raise ValueError("Event ledger missing attempted-trade fields")
    begin,end,halt_days=_official_halt_dates(issuer_audit,calendar)
    subset=events.loc[
        events["asset"].eq("SH600340")
        & events["date"].astype(str).isin(halt_days)
    ].copy()
    old_filled=subset.loc[
        subset["status"].eq("idealized_next_open_fill_unverified")
    ]
    blocked=subset.loc[
        ~subset["status"].eq("idealized_next_open_fill_unverified")
    ]
    return {
        "ticker":"SH600340",
        "start_official_halt":begin,
        "resume_official_open":end,
        "number_exchange_sessions_halted":len(halt_days),
        "frozen_old_attempts_during_official_halt":int(len(subset)),
        "frozen_old_blocked_attempts_during_official_halt":int(len(blocked)),
        "frozen_old_idealized_fills_conflicting_with_official_halt":int(len(old_filled)),
        "primary_pdf_halt_dates_certified_for_this_ticker":True,
        "primary_issuer_snapshot_asof_history_for_whole_universe":False,
        "full_orderbook_or_broker_execution_certified":False,
        "no_retroactive_strategy_selection_or_return_recalculation":True,
        "review_of_original_attempts":[{
            "date":str(x.date),"side":str(x.side),
            "old_status":str(x.status),
            "new_official_evidence":"ISSUER_PDF_EFFECTIVE_FULL_SESSION_HALT",
        } for x in subset.itertuples(index=False)],
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--issuer-evidence",type=Path,required=True)
    p.add_argument("--calendar",type=Path,required=True)
    p.add_argument("--execution-root",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    evidence=json.loads(a.issuer_evidence.read_text("utf8"))
    cal=pd.DatetimeIndex(pd.read_csv(a.calendar,header=None,names=["date"]).date)
    names=["momentum_daily_10bps","momentum_every5_10bps",
           "pit_members_equal_10bps"]
    records={}
    for name in names:
        events=pd.read_csv(a.execution_root/name/"events.csv")
        records[name]=replay_halt_events(events,evidence,cal)
    combined={
        "kind":"EXP002_FROZEN_EXECUTION_OFFICIAL_HALT_EVENT_OVERLAY",
        "issuer_pdf_provenance":"2021-01-29 and 2021-02-19 original announcement PDFs",
        "ticker_level_official_halt_verified":True,
        "portfolio_results_rewritten":False,
        "status":"PARTIAL_OFFICIAL_HALT_EVIDENCE_NO_FULL_BROKER_FILLS",
        "models":records,
    }
    if a.out.exists():
        raise FileExistsError("Cannot overwrite past event audit")
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(combined,ensure_ascii=False,indent=2)+"\n")
    for name,r in records.items():
        print(name,"official blocked",r["frozen_old_blocked_attempts_during_official_halt"],
              "contradictory previously filled",
              r["frozen_old_idealized_fills_conflicting_with_official_halt"])


if __name__=="__main__":
    main()
