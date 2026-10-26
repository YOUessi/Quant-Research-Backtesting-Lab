"""Corporate-action and trading-evidence coverage gate.

The 2026-10-26 public source snapshot cannot certify a full 393-name
historical portfolio's rights, intraday execution, or historical adjustments.
Do not convert this incompleteness into zero dividends, known no-suspension,
zero slippage or a market alpha claim.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def assess_csi300_pit_coverage(
    full: dict, issuer: dict, nominal: dict,
    *,
    full_sha256: str,
    issuer_sha256: str,
    nominal_sha256: str,
) -> dict:
    """Statically assert observed evidence coverage, without extrapolation."""
    if full["requested"] != 393:
        raise ValueError("Unexpected 2021-2022 CSI300 time-window symbol count")
    if full["complete_symbols"] + full["failed_symbols"] != full["requested"]:
        raise ValueError("Source failures not explicitly accounted for")
    if len(full["failures"]) != full["failed_symbols"]:
        raise ValueError("Missing individual failed-source reason")
    if full["implemented_events"] < 3:
        raise ValueError("Corporate event registry missing expected minimum source events")
    documents = issuer["verified_documents"]
    if len(documents) != 5:
        raise ValueError("Five specified original issuer PDFs have not been verified")
    issuer_divs = [d for d in documents if d["kind"] == "cash_dividend"
                   and d.get("cash_per_nominal_share_pre_tax_pdf_confirmed") is not None]
    if len(issuer_divs) != 3 or nominal["verified_events"] != 3:
        raise ValueError("Three nominal cash entitlement cases are not complete")
    urls = {d["primary_document_url"] for d in issuer_divs}
    if len(urls) != 3:
        raise ValueError("Source issuer PDF URLs repeated")
    for r in nominal["rights"]:
        matched = [
            d for d in issuer_divs
            if r["symbol"] == d["symbol"]
            and r["record_date"] == d["record_date_pdf_confirmed"]
            and r["ex_date"] == d["ex_date_pdf_confirmed"]
            and r["source_issuer_pdf_sha256"] == d["primary_document_sha256"]
        ]
        if len(matched) != 1:
            raise ValueError("Nominal event lacks a matching official original")
        if r["broker_cash_posting_confirmed"]:
            raise ValueError("Cannot certify brokerage cash posting from issuer PDF")
        if not r["no_open_auction_fill_claim"]:
            raise ValueError("Cannot claim actual fill from daily OHLCV")
    halt = issuer["halt_primary_secondary_corroboration"]
    if (halt["symbol"] != "SH600340"
            or halt["halted_exchange_sessions_confirmed"] != 10
            or halt["independent_daily_bar_during_halt"] != 0):
        raise ValueError("Original suspension PDF vs independent market-feed mismatch")

    state = {
        "stage": "PIT_EVENT_PROVENANCE_AND_EXECUTION_DATA_COVERAGE_AUDIT",
        "validation_status": "PARTIAL_SOURCE_EVIDENCE_NOT_FULL_PORTFOLIO_PIT",
        "period": ["2021-01-04", "2022-12-30"],
        "source_pit_ticker_scope": (
            "393 distinct CSI300 tickers present during 2021-2022; "
            "EXP002 includes 433 across 2020-06 warmup + study interval"
        ),
        "source_corporate_action_ticker_count_requested": full["requested"],
        "source_corporate_action_ticker_count_downloaded": full["complete_symbols"],
        "source_corporate_action_ticker_count_unavailable": full["failed_symbols"],
        "source_corporate_action_ticker_coverage_fraction": (
            full["complete_symbols"]/full["requested"]
        ),
        "eastmoney_implementation_events_with_historical_notice_calendar_day": (
            full["implemented_events"]
        ),
        "eastmoney_official_index_date_matches_for_targeted_symbols": (
            full["official_notice_crossmatched_events"]
        ),
        "official_original_issuer_pdf_verified": len(documents),
        "official_dividend_amount_and_record_ex_date_verified": len(issuer_divs),
        "one_sec_official_full_day_halt_span_exchange_sessions": (
            halt["halted_exchange_sessions_confirmed"]
        ),
        "original_halt_and_resume_pdf_dates_verified": True,
        "independent_daily_OHLCV_confirmed_no_bars_through_halt": True,
        "direct_nominal_share_cash_rights_1000_share_cases": [
            {"symbol": x["symbol"], "ex_date": x["ex_date"],
             "pretax_cash_receivable_for_1000_shares": (
                 x["pre_tax_dividend_receivable"]
             ), "source_verified": True, "broker_cash_posting_verified": False}
            for x in nominal["rights"]
        ],
        "source_consolidated_snapshot_has_historical_announcement_date_labels": True,
        "source_has_historical_versioned_field_revisions": False,
        "official_announcements_verified_for_all_implementation_events": False,
        "official_exchange_price_limits_complete_for_393_securities": False,
        "historical_opening_auction_depth_complete": False,
        "historical_broker_order_fills_complete": False,
        "actual_tradeability_certified_for_full_universe": False,
        "point_in_time_adjustment_factors_certified": False,
        "holdout_revaluation_recommended_now": False,
        "blockers": [
            "11 ticker source histories unavailable or uncertain; cannot infer zero events",
            "735 of 738 implementation events not PDF-confirmed in the audited pinned example",
            "latest vendor snapshot is not a series of historical publication-time snapshots",
            "Tushare stk_limit/suspend_d/anns_d endpoints require authorized credentials/permissions; no configured token on Mac",
            "BaoStock guest socket/API login timed out in the Mac environment",
            "only ten SH600340 halted sessions primary/secondary corroborated",
            "daily volume and official trading halt do not prove our order queue/fill",
            "full shareholder cash entitlements cannot be applied to Qlib adjusted-price proxy units without double-counting",
        ],
        "local_evidence_file_hashes": {
            "full_collection_summary_sha256": full_sha256,
            "issuer_primary_report_sha256": issuer_sha256,
            "nominal_rights_report_sha256": nominal_sha256,
        },
        "next_research_gate": (
            "Obtain licensed full-universe as-of dividend and split implementation "
            "snapshots + official daily suspension/price limit fields + order-book "
            "or broker fill records; run independent reconciliation before "
            "re-evaluating portfolio returns. No alpha/model selection yet."
        ),
    }
    return state


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--full-collection", type=Path, required=True)
    p.add_argument("--primary-pdfs", type=Path, required=True)
    p.add_argument("--nominal-rights", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    for f in (args.full_collection, args.primary_pdfs, args.nominal_rights):
        if not f.is_file():
            raise FileNotFoundError(f)
    def checksum(file):
        return hashlib.sha256(file.read_bytes()).hexdigest()
    summary = assess_csi300_pit_coverage(
        _load(args.full_collection), _load(args.primary_pdfs),
        _load(args.nominal_rights),
        full_sha256=checksum(args.full_collection),
        issuer_sha256=checksum(args.primary_pdfs),
        nominal_sha256=checksum(args.nominal_rights),
    )
    if args.out.exists():
        raise FileExistsError("Refusing to overwrite prior source coverage assessment")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False)+"\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "verified_ticker_source_records": summary["source_corporate_action_ticker_count_downloaded"],
        "missing_source_tickers": summary["source_corporate_action_ticker_count_unavailable"],
        "historical_implementation_date_event_rows": summary["eastmoney_implementation_events_with_historical_notice_calendar_day"],
        "issuer_PDF_cash_amount_checks": summary["official_dividend_amount_and_record_ex_date_verified"],
        "suspended_real_sessions_checked": summary["one_sec_official_full_day_halt_span_exchange_sessions"],
        "full_quant_certification": summary["validation_status"],
    },indent=2,ensure_ascii=False))


if __name__ == "__main__":
    main()
