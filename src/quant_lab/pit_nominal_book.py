"""EXP-005 nominal-share dividends & cash receivable accounting.

Not a trading strategy. The investor is hypothetically already holding
nominal shares at record-date CLOSE. It deliberately books a declared cash
right at EX-date, not twice in the cum-dividend record-date mark.

Issuer pay-day events are *scheduled* payments, not verified broker credits.
A current Qlib adjusted-price series is strictly forbidden here.
"""
from __future__ import annotations

from decimal import Decimal
import math

import pandas as pd


def dec(value, name):
    try:
        v = Decimal(str(value))
    except Exception as e:
        raise ValueError(f"Invalid Decimal {name}") from e
    if not v.is_finite():
        raise ValueError(f"Nonfinite {name}")
    return v


def simulate_nominal_right(event: dict, bars: pd.DataFrame, *,
                           original_shares=1000,
                           share_bonus_ratio=None,
                           share_bonus_terms_officially_verified=False,
                           broker_payment_verified=False) -> dict:
    """Returns a *single-event* no-trade issuer-rights price-mark illustration.

    We do not sell or buy, and we never claim observed opening auction fills.
    The nominal share count remains unchanged unless explicit source-audited
    bonus/share-transfer terms were passed. Unknown terms => scenario-only.
    """
    if event.get("earliest_usable_exchange_day") is None:
        raise ValueError("Event has no verifiable PIT public-availability day")
    if event.get("issuer_pdf_sha256") is None or not event.get("gross_cash_per_nominal_share"):
        raise ValueError("Event lacks primary issuer cash evidence")
    if event["earliest_usable_exchange_day"] > event["record_date"]:
        raise ValueError("Event not knowable by record date")
    record, ex = pd.Timestamp(event["record_date"]), pd.Timestamp(event["ex_date"])
    pay = pd.Timestamp(event["payment_date"]) if event.get("payment_date") else None
    if not record < ex or (pay is not None and pay < ex):
        raise ValueError("Bad record/ex/payment chronology")
    if not {"date","close_raw"}.issubset(bars.columns):
        raise ValueError("Unadjusted nominal-market close prices required")
    if any("adjust" in x.lower() for x in bars.columns):
        raise ValueError("Adjusted-price columns not allowed in nominal book")
    source = bars.copy()
    source["date"] = pd.to_datetime(source["date"]).dt.normalize()
    if source["date"].duplicated().any():
        raise ValueError("Duplicate trade-day price")
    source = source.sort_values("date")
    source = source[source["date"] >= record]
    if source.empty or not (source["date"]==record).any():
        raise ValueError("No record-date price")
    if not (source["date"]==ex).any():
        raise ValueError("No ex-date raw price: CENSOR rather than stale mark")
    if pay is not None and not (source["date"] >= pay).any():
        raise ValueError("Payment date not reached in supplied price history")
    shares = dec(original_shares,"original_shares")
    if shares <= 0:raise ValueError("Original shares must be positive")
    amount = dec(event["gross_cash_per_nominal_share"],"cash")
    if amount <= 0:raise ValueError("Cash dividend must be positive")
    if share_bonus_ratio is None:
        bonus = Decimal(0)
        rights_scope = "CASH_ONLY_ASSUMPTION_STOCK_BONUS_UNVERIFIED"
    else:
        bonus = dec(share_bonus_ratio,"share bonus ratio")
        if bonus < 0:raise ValueError("Negative stock bonus ratio")
        if not share_bonus_terms_officially_verified:
            raise ValueError("Do not apply unaudited share-distribution term")
        rights_scope = "STOCK_BONUS_RATIO_EXPLICITLY_SOURCE_VERIFIED"
    if broker_payment_verified:
        raise ValueError("Broker cash payment requires a separate actual credit record")
    claim_shares=shares
    receivable=Decimal(0)
    cash=Decimal(0)
    pending_record=False
    rows=[]
    for row in source.itertuples(index=False):
        dt=pd.Timestamp(row.date)
        if pay is not None and dt>pay:break
        px=dec(row.close_raw,"close_raw")
        if px<=0:raise ValueError(f"Unpriceable nominal close {dt.date()}")
        actions=[]
        if dt==record:
            pending_record=True
            actions.append("RECORD_ENTITLEMENT_KNOWN_BUT_STILL_EMBEDDED_IN_CUM_DIVIDEND_PRICE")
        if dt==ex:
            if not pending_record:raise ValueError("No record-date entitlement")
            shares=claim_shares*(Decimal(1)+bonus)
            receivable=claim_shares*amount
            actions.append("EX_TRANSFER_CUM_DIVIDEND_PRICE_TO_NOMINAL_SHARES_AND_PRETAX_RECEIVABLE")
        if pay is not None and dt==pay:
            cash+=receivable
            receivable=Decimal(0)
            actions.append("PAY_DATE_ASSUMED_PER_ISSUER_SCHEDULE_NOT_BROKER_CONFIRMED")
        total=shares*px+cash+receivable
        rows.append({
            "date":dt.date().isoformat(),
            "nominal_shares":str(shares),
            "unadjusted_nominal_close":str(px),
            "share_mark":str(shares*px),
            "pretax_receivable":str(receivable),
            "cash_schedule_only":str(cash),
            "equity_gross_scenario":str(total),
            "events":actions,
        })
    rec = next(x for x in rows if x["date"]==str(record.date()))
    exrow = next(x for x in rows if x["date"]==str(ex.date()))
    base=dec(rec["equity_gross_scenario"],"record value")
    result={
        "kind":"SINGLE_EVENT_ISSUER_RIGHTS_UNADJUSTED_NOMINAL_BOOK",
        "symbol":event["symbol"],"issuer_event_id":event["event_id"],
        "issuer_original_pdf_sha256":event["issuer_pdf_sha256"],
        "event_grade":event["evidence_grade"],
        "record_date":str(record.date()),"ex_date":str(ex.date()),
        "scheduled_payment_date":str(pay.date()) if pay is not None else None,
        "nominal_shares_initial":str(claim_shares),
        "pretax_entitlement":str(claim_shares*amount),
        "record_close_nominal_mark":rec["equity_gross_scenario"],
        "ex_close_including_gross_receivable_scenario":exrow["equity_gross_scenario"],
        "ex_close_total_mark_change":float(dec(exrow["equity_gross_scenario"],"exmark")/base-1),
        "records":rows,
        "corporate_share_terms_status":rights_scope,
        "cash_payment_broker_confirmed":False,
        "effective_cash_is_gross_before_holder_specific_taxes":True,
        "trade_fills_or_auction_orderbook_verified":False,
        "Qlib_adjusted_total_return_price_used":False,
        "only_a_no_trade_accounting_validation":True,
        "completed_actual_portfolio_revaluation":False,
    }
    if pay is None:result["source_payment_day_unverified"]=True
    return result
