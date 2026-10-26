"""Real issuer-dividend/ex-date nominal-share accounting evidence.

Three corporate actions are independently confirmed against original public
issuer PDFs. Reconcile pretax cash entitlements with independent historical
unadjusted Eastmoney daily prices; compare one-day *valuation changes*, not
model profits, and do not double count pre-adjusted Qlib security positions.

Strictly a spot record/ex-date unit test using dated public source data.
Official limit prices, order queue, realized brokerage tax and issuer
release-time snapshot history remain unavailable.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import requests

from .pit_events import (
    normalise_eastmoney_dividends, settle_nominal_action, implementation_known_on
)
from .pit_primary_audit import fetch_independent_unadjusted_bars


def reconcile(
    issuer_audit: dict,
    firstparty_collector_dir: Path,
    session: requests.Session,
    *,
    shares: int = 1000,
) -> dict:
    if shares < 1:
        raise ValueError("Need positive nominal share quantity")
    pdfs = [
        doc for doc in issuer_audit["verified_documents"]
        if doc["kind"] == "cash_dividend"
        and doc.get("cash_per_nominal_share_pre_tax_pdf_confirmed") is not None
    ]
    if len(pdfs) != 3:
        raise ValueError("Exactly three pinned PDFs must be independently verified")
    results = []
    for proof in pdfs:
        symbol = proof["symbol"]
        record_date = proof["record_date_pdf_confirmed"]
        ex = proof["ex_date_pdf_confirmed"]
        cash_per_share = proof["cash_per_nominal_share_pre_tax_pdf_confirmed"]
        raw = json.loads((firstparty_collector_dir / f"{symbol}.json").read_text("utf-8"))
        events, rejects = normalise_eastmoney_dividends(
            raw["raw_eastmoney_records"], first_ex=ex, last_ex=ex
        )
        candidates = [
            x for x in events if x["symbol"] == symbol and
            x["record_date"] == record_date and
            abs(x["cash_per_share_pre_tax"] - cash_per_share) < 1e-8
        ]
        if len(candidates) != 1:
            raise ValueError(f"Third party dividend does not match official PDF: {symbol}/{ex}")
        event = candidates[0]
        if not implementation_known_on(event, record_date):
            raise ValueError("Implementation announcement was not known before record-day close")
        bars, quote_source = fetch_independent_unadjusted_bars(
            session, symbol, start=str((pd.Timestamp(record_date) -
                                       pd.Timedelta(days=9)).date()),
            end=str((pd.Timestamp(ex) +
                     pd.Timedelta(days=9)).date()),
        )
        record = bars[bars["date"] == record_date]
        ex_row = bars[bars["date"] == ex]
        if len(record) != 1 or len(ex_row) != 1:
            raise ValueError("Record/ex date lacks exactly one unadjusted daily bar")
        rec_price = float(record["close_raw"].iloc[0])
        ex_price = float(ex_row["close_raw"].iloc[0])
        if rec_price <= 0 or ex_price <= 0:
            raise ValueError("Bad unadjusted stock price")
        record_volume = float(record["volume_lots"].iloc[0])
        ex_volume = float(ex_row["volume_lots"].iloc[0])
        if min(record_volume,ex_volume) <= 0:
            raise ValueError("Missing actual traded daily volume; reject nominal quote")
        rights = settle_nominal_action(
            shares_at_record_close=shares, event=event
        )
        pre = shares * rec_price
        # Even when cash is paid later, it is a receivable after the record
        # date. This value ignores tax, default and timing of actual payment.
        after_claim = rights["shares_ex_date_nominal"] * ex_price + (
            rights["dividend_receivable_pre_tax"]
        )
        results.append({
            "symbol": symbol, "record_date": record_date, "ex_date": ex,
            "implementation_announcement_date": event["implementation_announcement_date"],
            "source_issuer_pdf_sha256": proof["primary_document_sha256"],
            "source_issuer_pdf_url": proof["primary_document_url"],
            "source_unadjusted_ohlcv": quote_source,
            "shares_registered_nominal": shares,
            "registered_share_nominal_price_close": rec_price,
            "ex_date_share_nominal_price_close": ex_price,
            "record_day_traded_volume_lots": record_volume,
            "ex_day_traded_volume_lots": ex_volume,
            "pre_tax_dividend_receivable": rights["dividend_receivable_pre_tax"],
            "stock_bonus_and_transfer_after_ex": rights["shares_ex_date_nominal"],
            "record_day_mark_nominal": pre,
            "ex_close_mark_plus_dividend_claim_pre_tax": after_claim,
            "one_day_price_only_change": ex_price / rec_price - 1,
            "one_day_entitlement_aware_mark_change": after_claim / pre - 1,
            "difference_in_change_due_to_dividend_claim": cash_per_share / rec_price,
            "no_open_auction_fill_claim": True,
            "not_added_to_qlib_adjusted_price_backtest": True,
            "official_daily_limit_prices_available": False,
            "broker_cash_posting_confirmed": False,
            "tax_treatment_confirmed": False,
            "source_snapshot_retroactive_corrections_audited": False,
        })
    return {
        "stage": "REAL_PRIMARY_PDF_AND_SECONDARY_NOMINAL_RIGHTS_RECONCILIATION",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "verified_events": len(results), "nominal_shares_per_event": shares,
        "cash_price_share_units_reconciled": True,
        "historical_publication_day_crossmatched": True,
        "source_availability_rule": "implementation announced by earlier calendar date",
        "market_auction_and_broker_fills_verified": False,
        "factor_history_point_in_time_certified": False,
        "full_CSI300_company_actions_verified": False,
        "rights": results,
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--issuer-audit", type=Path, required=True)
    p.add_argument("--collected-events", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--shares", type=int, default=1000)
    args = p.parse_args()
    if args.out.exists():
        raise FileExistsError("Refusing to overwrite nominal reconciliation")
    audit = json.loads(args.issuer_audit.read_text("utf-8"))
    with requests.Session() as s:
        result = reconcile(audit, args.collected_events, s,
                           shares=args.shares)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n",
                        encoding="utf-8")
    for row in result["rights"]:
        print(row["symbol"], row["record_date"], "→", row["ex_date"],
              "cash_receivable_pre_tax", row["pre_tax_dividend_receivable"],
              "nominal_entitlement_change",
              round(100*row["one_day_entitlement_aware_mark_change"],3), "%",
              "broker_fills_verified=False")


if __name__ == "__main__":
    main()
