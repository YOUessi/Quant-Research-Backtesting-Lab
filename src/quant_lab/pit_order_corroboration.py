"""EXP-006: overlay issuer-proven stock halts on frozen EXP-002 attempts.

This is an independent evidence audit, not a rewritten/backfilled portfolio.
No new performance claims. Only exact original-PDF corroborated halt sessions
are marked as official issuer restrictions; remaining assumed next-open fills
are NOT upgraded to actual execution. No official daily price limits or
opening auction volume/queue are provided by the current source bundle.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


def official_halt_keys(rights: dict, prior_primary: dict, *,
                       calendar: list[str]) -> dict[tuple[str,str],dict]:
    if rights.get("kind")!="EXP005_ORIGINAL_ISSUER_RIGHTS_ISSUE_PDF_HALT_PERIOD_AUDIT":
        raise ValueError("Invalid rights-issue original-PDF evidence")
    dates=sorted({str(pd.Timestamp(x).date()) for x in calendar})
    halt={}
    for e in rights["recovered"]:
        if not e.get("full_period_Qlib_independently_corroborates_halt"):
            raise ValueError("Rights-issue halt proof contradicted by price source")
        if not e.get("issuer_pdf_sha256"):
            raise ValueError("Rights-issue original PDF SHA missing")
        for day in e["issuer_halted_exchange_sessions"]:
            key=(e["symbol"],day)
            if key in halt:
                raise ValueError("Overlapping distinct issuer halt evidence: "+str(key))
            halt[key]={
                "kind":"RIGHTS_SUBSCRIPTION_OR_CLEARING_STOCK_HALT",
                "effective_day":day,
                "source_pdf_sha256":e["issuer_pdf_sha256"],
                "source_url":e["issuer_original_document_url"],
                "prior_publication_day":e["issuer_release_calendar_day"],
                "issuer_original_pdf_verified":True,
            }
    docs=prior_primary.get("verified_documents",[])
    starts=[x for x in docs if x.get("suspended_from_open_pdf_confirmed")]
    ends=[x for x in docs if x.get("resumed_from_open_pdf_confirmed")]
    if len(starts)!=1 or len(ends)!=1:
        raise ValueError("Cannot identify unique SH600340 primary source")
    first,ending=(starts[0]["suspended_from_open_pdf_confirmed"],
                  ends[0]["resumed_from_open_pdf_confirmed"])
    if first>ending:
        raise ValueError("Invalid issuer halt span")
    those=[day for day in dates if first<=day<ending]
    if len(those)!=10:
        raise ValueError("First independent SH600340 issuer halt must cover 10 sessions")
    for day in those:
        key=("SH600340",day)
        if key in halt:raise ValueError("Duplicate halt issuer proof")
        halt[key]={
            "kind":"OFFICIAL_ISSUER_COMPANY_STOCK_SUSPENSION",
            "effective_day":day,
            "source_pdf_sha256":starts[0]["primary_document_sha256"],
            "source_url":starts[0]["primary_document_url"],
            "prior_publication_day":starts[0]["official_release_calendar_date"],
            "issuer_original_pdf_verified":True,
        }
    # Audit metadata is not necessarily knowable on the earlier signal day.
    # Only executions on the effective day are checked retrospectively.
    return halt


def corroborate_frozen_attempts(
    attempted: pd.DataFrame, issuer_halts: dict[tuple[str,str],dict],
) -> tuple[dict,list[dict]]:
    needed={"date","asset","side","gross_notional","status","signal_date"}
    if not needed.issubset(attempted.columns):
        raise ValueError("Missing archived prior trade-event ledger columns")
    models={"idealized_next_open_fill_unverified"}
    rows=[]
    for i,e in enumerate(attempted.itertuples(index=False)):
        day=str(pd.Timestamp(e.date).date())
        prior=str(pd.Timestamp(e.signal_date).date())
        if not prior<day:
            raise ValueError("Archived model event has invalid future signal date")
        key=(str(e.asset),day)
        matched=issuer_halts.get(key)
        old_fill=e.status in models
        if matched:
            status=("POTENTIAL_MODEL_FILL_CONTRADICTS_VERIFIED_ISSUER_HALT"
                    if old_fill else "PREVIOUSLY_BLOCKED_CORROBORATED_BY_ISSUER_HALT")
        elif old_fill:
            status="UNCERTIFIED_NEXT_OPEN_FILL_NO_ORDERBOOK_OR_DAILY_LIMIT_PROOF"
        else:
            status="ALREADY_BLOCKED_NON_ISSUER_REASON_NOT_INDEPENDENTLY_CERTIFIED"
        rows.append({
            "legacy_row_index":i,
            "symbol":str(e.asset),"trade_day":day,
            "signal_day":prior,"side":str(e.side),
            "previous_assumed_status":str(e.status),
            "old_event_notional_in_normalized_research_units":float(e.gross_notional),
            "issuer_halt_evidence_status":status,
            "issuer_pdf_sha256":matched["source_pdf_sha256"] if matched else None,
            "issuer_pdf_url":matched["source_url"] if matched else None,
            "official_limit_price_on_trade_day_available":False,
            "broker_order_fill_receipt_available":False,
        })
    frame=pd.DataFrame(rows)
    if frame.empty:raise ValueError("Cannot audit empty frozen event log")
    counts=frame["issuer_halt_evidence_status"].value_counts().to_dict()
    summary={
        "n_prior_frozen_attempts":len(frame),
        "n_legacy_assumed_next_open_fills":int(sum(
            attempted["status"]=="idealized_next_open_fill_unverified")),
        "issuer_halt_correlated_blocked_orders":int(
            counts.get("PREVIOUSLY_BLOCKED_CORROBORATED_BY_ISSUER_HALT",0)),
        "issuer_halt_contradictory_assumed_fills":int(
            counts.get("POTENTIAL_MODEL_FILL_CONTRADICTS_VERIFIED_ISSUER_HALT",0)),
        "uncertified_assumed_fills_no_auction_limits":int(
            counts.get("UNCERTIFIED_NEXT_OPEN_FILL_NO_ORDERBOOK_OR_DAILY_LIMIT_PROOF",0)),
        "old_model_blocked_without_independent_issuer_proof":int(
            counts.get("ALREADY_BLOCKED_NON_ISSUER_REASON_NOT_INDEPENDENTLY_CERTIFIED",0)),
        "all_realized_broker_fills_certified":False,
        "frozen_strategy_returns_recomputed_or_reoptimized":False,
        "requires_model_backtest_revision_if_contradiction":bool(
            counts.get("POTENTIAL_MODEL_FILL_CONTRADICTS_VERIFIED_ISSUER_HALT",0)),
        "warning":"Issuer dated halt PDF is a retrospective executable-day restriction, not a broker fill; absent daily exchange limit/auction records keep all assumed fills uncertified.",
    }
    return summary,rows


def run(roots: Path, rights: Path, primary: Path, calendar: Path,
        *, output: Path) -> dict:
    if output.exists():raise FileExistsError("Prior order evidence cannot be overwritten")
    info_rights=json.loads(rights.read_text("utf-8"))
    info_primary=json.loads(primary.read_text("utf-8"))
    days=pd.read_csv(calendar,header=None)[0].astype(str).tolist()
    official=official_halt_keys(info_rights,info_primary,calendar=days)
    results={}
    for name in (
        "momentum_daily_10bps",
        "momentum_every5_10bps",
        "pit_members_equal_10bps",
    ):
        path=roots/name/"events.csv"
        frame=pd.read_csv(path)
        summary,rows=corroborate_frozen_attempts(frame,official)
        results[name]=summary
    document={
        "kind":"EXP006_FROZEN_ORDER_EXECUTION_EVIDENCE_RECONCILIATION",
        "frozen_period":"2021-01-04 to 2022-12-30",
        "distinct_issuer_original_PDF_halt_stock_session_keys":len(official),
        "calendar_halt_evidence_ticker_count":len({x[0] for x in official}),
        "all_issuer_halt_sources_original_PDF_SHA_confirmed":True,
        "order_notional_is_normalized_research_unit_not_nominal_shares":True,
        "real_trading_broker_fills_certified":False,
        "all_stock_daily_official_limit_prices_collected":False,
        "full_auction_queue_observations_collected":False,
        "old_returns_changed":False,
        "results":results,
        "statement":"Retrospective status overlay; 40 issuer-proven halted stock-session keys do not certify all other dates as tradable or any hypothetical next-open fill.",
    }
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(document,ensure_ascii=False,indent=2)+"\n",
                      encoding="utf-8")
    return document


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--frozen-execution",type=Path,required=True)
    parser.add_argument("--rights-halt",type=Path,required=True)
    parser.add_argument("--original-primary-pdfs-report",type=Path,required=True)
    parser.add_argument("--exchange-calendar",type=Path,required=True)
    parser.add_argument("--out",type=Path,required=True)
    a=parser.parse_args()
    report=run(a.frozen_execution,a.rights_halt,
               a.original_primary_pdfs_report,a.exchange_calendar,
               output=a.out)
    print(json.dumps({
        "issuer_halted_security_sessions":report["distinct_issuer_original_PDF_halt_stock_session_keys"],
        "models":{name:{k:v for k,v in item.items() if k.startswith("issuer_halt_") or k.startswith("uncertified_") or k.startswith("n_prior_")}
                  for name,item in report["results"].items()}
    },indent=2))


if __name__=="__main__":
    main()
