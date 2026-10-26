"""Package minimal public-auditable proof, without copying vendor market data.

PIT source-grade flags must survive aggregation. This intentionally refuses
to relabel metadata-only events as issuer-original amount verification.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def read_and_hash(path: Path) -> tuple[dict,str]:
    if not path.is_file():
        raise FileNotFoundError(path)
    payload=path.read_bytes()
    return json.loads(payload), hashlib.sha256(payload).hexdigest()


def package(*, audited_batch:Path, recovered_events:Path,
            recovered_gap:Path, independent_missing:Path,
            official_halt:Path, output:Path) -> dict:
    if output.exists():
        raise FileExistsError("Refuse overwrite of historical evidence package")
    issuer,ih=read_and_hash(audited_batch)
    event,eh=read_and_hash(recovered_events)
    gap,gh=read_and_hash(recovered_gap)
    market,mh=read_and_hash(independent_missing)
    halt,hh=read_and_hash(official_halt)
    if issuer["kind"]!="OFFLINE_RECHECK_OF_PINNED_ISSUER_PDF_BYTES":
        raise ValueError("Unrecognized original issuer PDF audit")
    if issuer["n_document_bytes_reverified"]<25:
        raise ValueError("Insufficient official document sources")
    if event["n_events_from_missing_thirdparty_sources"] != 11:
        raise ValueError("Expected 11 originally missing issuer events")
    if gap["original_missing_tickers"] != 11:
        raise ValueError("Original 11 vendor failures were lost")
    if market["qlib_missing_member_days"] != 139:
        raise ValueError("Historic gap count changed; review frozen source")
    if market["tickers_audited"] != market["qlib_missing_distinct_tickers"]:
        raise ValueError("Not all missing-bar tickers independently audited")
    verified=sum(
        x["status"]=="PDF_CASH_MATCHED_TO_THIRDPARTY"
        for x in issuer["documents"]
    )
    official_events=event["issuer_cash_dates_directly_parsed_events"]
    pdfs=[
        {
            "symbol":x["symbol"],
            "official_announcement_day":x["official_notice_day"],
            "issuer_pdf_url":x["issuer_pdf_url"],
            "issuer_pdf_sha256":x["issuer_pdf_sha256"],
            "status":x["status"],
            "gross_per_nominal_share":x["cash_per_share_verified"],
            "third_party_exdate_literal_verified":
                x["issuer_pdf_ex_record_date_literals_both_present"],
            "third_party_date":x["thirdparty_ex_date"],
            "tax_inclusive_explicit_candidates":
                x.get("issuer_pdf_explicit_tax_inclusive_cash_candidates",[]),
        }
        for x in issuer["documents"]
    ]
    recovered=[
        {
            "symbol":x["symbol"],
            "announcement_day":x["published_calendar_day"],
            "issuer_pdf_sha256":x["issuer_pdf_sha256"],
            "issuer_pdf_url":x["issuer_pdf_url"],
            "record_date":x["record_date"],
            "ex_date":x["ex_date"],
            "pay_date":x["payment_date"],
            "gross_cash_per_nominal_share_verified":
                x["cash_pre_tax_per_nominal_share_recovered"],
            "status":x["status"],
        }
        for x in official_events
    ]
    market_gaps=[
        {
            "symbol":x["symbol"],
            "qlib_missing_member_days":x["n_qlib_member_day_gaps"],
            "independent_raw_daily_trade_present_during_qlib_missing":
                x["cross_source_presence_discrepancies"],
            "two_daily_sources_absent_NOT_HALT_PROOF":
                x["both_daily_sources_absent_not_official_halt_certificate"],
            "independent_response_sha256":
                x["independent_source"]["source_response_sha256"],
        }
        for x in market["audits"]
    ]
    summary={
        "kind":"EXP004_INDEPENDENT_CORPORATE_ACTION_AND_MARKET_DATA_SOURCE_PROOFS",
        "date_scope":"historical 2021–2022, fetched 2026-10-26",
        "source_report_sha256":{
            "original_issuer_pdf_rerate":ih,
            "issuer_direct_date_recovery":eh,
            "11_missing_provider_recovery":gh,
            "independent_daily_bar_crosscheck":mh,
            "official_halt_order_ledger":hh,
        },
        "original_issuer_pdf_documents_hashed":len(pdfs),
        "issuer_amount_ex_record_vendor_triple_confirmed":verified,
        "missing_vendor_events_recovered_with_issuer_gross_and_dates":
            event["n_unique_original_cash_and_dates_explicit_gross"],
        "missing_vendor_events_still_cash_ambiguous":
            event["n_amount_unresolved"],
        "prior_missing_thirdparty_tickers":gap["original_missing_tickers"],
        "prior_missing_with_official_impl_notices":
            gap["official_implementation_notice_tickers"],
        "independent_market_gap_tickers":market["tickers_audited"],
        "independent_market_gap_member_days":market["qlib_missing_member_days"],
        "missed_daily_bars_found_in_independent_feed":
            market["missing_member_days_with_independent_positive_trade_bars"],
        "both_daily_feeds_absent_days_not_certified_halts":
            market["missing_member_days_both_sources_absent_NOT_OFFICIAL_HALT"],
        "SH600340_frozen_baseline_official_halt_attempts_blocked":
            halt["models"]["pit_members_equal_10bps"][
                "frozen_old_blocked_attempts_during_official_halt"
            ],
        "cash_tax_aftertax_confusion_fixed_by_explicit_gross_context":True,
        "q_lib_adjustment_revisions_asof_certified":False,
        "complete_393_stock_actions_officially_verified":False,
        "complete_official_daily_limits_available":False,
        "broker_queue_position_or_fills_observed":False,
        "recommend_portfolio_backtest_revaluation_now":False,
        "source_pdf_records":pdfs,
        "recovered_original_issuer_events":recovered,
        "independent_market_ticker_crosscheck":market_gaps,
        "original_vendor_missing_gap_statuses":gap["ticker_findings"],
        "official_halt_order_replay":halt["models"],
        "limitations":[
            "Official issuer publication calendar days are not exact intraday timestamps.",
            "31 targeted original PDFs and independent-source market days are audit examples, not a full universe company-action PIT archive.",
            "139 missing daily bars in both vendors do not prove 139 officially suspended sessions.",
            "Actual auction fills and volume are not inferable from end-of-day traded volume.",
            "Historical adjustment-factor vendor vintages and payments/rights remain incomplete.",
        ],
    }
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n")
    return summary


def main():
    p=argparse.ArgumentParser()
    for n in ("audited_batch","recovered_events","recovered_gap",
              "independent_missing","official_halt"):
        p.add_argument("--"+n.replace("_","-"),type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    result=package(
        audited_batch=a.audited_batch,recovered_events=a.recovered_events,
        recovered_gap=a.recovered_gap, independent_missing=a.independent_missing,
        official_halt=a.official_halt,output=a.out,
    )
    print(json.dumps({
        k:result[k] for k in (
            "original_issuer_pdf_documents_hashed",
            "issuer_amount_ex_record_vendor_triple_confirmed",
            "missing_vendor_events_recovered_with_issuer_gross_and_dates",
            "independent_market_gap_member_days",
            "missed_daily_bars_found_in_independent_feed",
            "SH600340_frozen_baseline_official_halt_attempts_blocked",
        )
    },indent=2))


if __name__=="__main__":
    main()
