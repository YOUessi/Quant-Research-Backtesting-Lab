"""Historical corporate-action events with explicit *information availability*.

Two independent concepts:
  - ex/record/pay dates: when securities and money change
  - publication date/time: when a strategy could have known the implementation

Daily public announcement metadata does not certify a precise intraday upload.
We conservatively grant it at the NEXT exchange session, never on announcement
day. Do not mix these nominal share/cash actions with Qlib adjusted-price units.
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Iterable
import math

import pandas as pd

_CN = ZoneInfo("Asia/Shanghai")


def qlib_symbol(code: str) -> str:
    text = str(code).upper().strip()
    if len(text) == 8 and text[:2] in ("SH", "SZ", "BJ") and text[2:].isdigit():
        return text
    parts = text.split(".")
    if len(parts) == 2 and len(parts[0]) == 6 and parts[0].isdigit():
        if parts[1] in ("SH", "SZ", "BJ"):
            return parts[1] + parts[0]
    raise ValueError(f"Unrecognized A-share code {code!r}")


def date_only(value, *, field: str):
    if value is None or str(value).strip() in ("", "None", "NaT", "nan"):
        return None
    ts = pd.to_datetime(value, errors="raise")
    if pd.isna(ts):
        return None
    return pd.Timestamp(ts).normalize().date().isoformat()


def _nonnegative_number(value, *, field: str) -> float:
    if value is None or str(value).strip() in ("", "None", "NaT", "nan"):
        return 0.0
    result = float(value)
    if not math.isfinite(result) or result < 0:
        raise ValueError(f"Negative/nonfinite corporate action amount: {field}")
    return result


def normalise_eastmoney_dividends(rows: list[dict], *,
                                 first_ex: str, last_ex: str) -> tuple[list[dict], list[dict]]:
    """Return implemented events + explicitly rejected records.

    Eastmoney shares/cash ratios are PER TEN SHARES. For example
    PRETAX_BONUS_RMB=4.10 -> 0.410 nominal currency per registered share.
    BONUS_RATIO and IT_RATIO are nonnegative bonus/transfer shares per TEN.

    NOTICE_DATE is a *latest implementation announcement date* in this API,
    not a historical feed snapshot. It may be later than an earlier plan.
    The latter is not proof the implementation terms were known earlier.
    """
    accepted, excluded = [], []
    for raw in rows:
        code = raw.get("SECUCODE")
        if not code:
            excluded.append({"reason": "symbol_missing"})
            continue
        symbol = qlib_symbol(code)
        ex = date_only(raw.get("EX_DIVIDEND_DATE"), field="EX_DIVIDEND_DATE")
        if not ex or not first_ex <= ex <= last_ex:
            continue
        source_date = date_only(raw.get("NOTICE_DATE"), field="NOTICE_DATE")
        plan = date_only(raw.get("PLAN_NOTICE_DATE"), field="PLAN_NOTICE_DATE")
        register = date_only(raw.get("EQUITY_RECORD_DATE"), field="EQUITY_RECORD_DATE")
        progress = str(raw.get("ASSIGN_PROGRESS") or "")
        try:
            if "实施" not in progress or not source_date or not plan or not register:
                raise ValueError("No dated implementation stage and record")
            if not (plan <= source_date <= register < ex):
                raise ValueError("Announcement/record/ex chronology is invalid")
            cash_per_10 = _nonnegative_number(raw.get("PRETAX_BONUS_RMB"), field="cash")
            stock_per_10 = _nonnegative_number(raw.get("BONUS_RATIO"), field="bonus")
            transfer_per_10 = _nonnegative_number(raw.get("IT_RATIO"), field="transfer")
            pay = date_only(raw.get("DIVIDEND_DATE"), field="DIVIDEND_DATE")
            if pay and pay < ex:
                raise ValueError("Payment before ex date")
        except ValueError as exc:
            excluded.append({"symbol": symbol, "ex_date": ex,
                             "reason": str(exc), "source_notice": source_date})
            continue
        accepted.append({
            "symbol": symbol, "record_date": register, "ex_date": ex,
            "payment_date": pay, "plan_announcement_date": plan,
            "implementation_announcement_date": source_date,
            "cash_per_share_pre_tax": cash_per_10 / 10.0,
            "stock_bonus_per_share": stock_per_10 / 10.0,
            "capital_transfer_per_share": transfer_per_10 / 10.0,
            "implementation_status": progress,
            "origin": "eastmoney_RPT_SHAREBONUS_DET",
            "source_notice_date_only": True,
            "requires_official_announcement_crosscheck": True,
            "earliest_use": "next_exchange_session_after_implementation_notice",
            "nominal_shares_and_currency_only": True,
            "never_double_count_with_adjusted_qlib_prices": True,
        })
    uniq = set()
    for item in accepted:
        key = (item["symbol"], item["ex_date"], item["record_date"])
        if key in uniq:
            raise ValueError(f"Duplicate event identity from source: {key}")
        uniq.add(key)
    return sorted(accepted, key=lambda r: (r["ex_date"], r["symbol"])), excluded


def normalise_cninfo_announcements(announcements: list[dict]) -> list[dict]:
    """Capture official *calendar day* metadata, not an exact market dissemination time."""
    collected = []
    for item in announcements:
        sec = item.get("secCode")
        epoch_ms = item.get("announcementTime")
        adjunct = item.get("adjunctUrl")
        if not sec or epoch_ms is None or not adjunct:
            continue
        if not (str(adjunct).startswith("finalpage/") and
                str(adjunct).lower().endswith(".pdf") and
                ".." not in str(adjunct)):
            continue
        exchange = "SH" if str(sec).startswith("6") else "SZ"
        symbol = qlib_symbol(str(sec)+f".{exchange}")
        published_date = datetime.fromtimestamp(
            float(epoch_ms) / 1000.0, tz=_CN
        ).date().isoformat()
        title = str(item.get("announcementTitle") or "")
        # cninfo's search result may wrap highlights in <em>; do not
        # copy search markup to event-matching semantics.
        for part in ("<em>", "</em>"):
            title = title.replace(part, "")
        collected.append({
            "symbol": symbol,
            "published_calendar_date": published_date,
            "source_epoch_milliseconds": int(epoch_ms),
            "actual_intraday_publication_certified": False,
            "announcement_title": title,
            "pdf_url": "https://static.cninfo.com.cn/" + adjunct,
            "announcement_id": str(item.get("announcementId") or ""),
            "publisher": "cninfo_official_disclosure_index",
        })
    return collected


def attach_official_announcement(events: list[dict],
                                 official: list[dict]) -> list[dict]:
    """Tie Eastmoney event to official announcement metadata by symbol/day/type.

    A title/day match proves that official disclosure was indexed on that
    calendar date, NOT that we parsed/confirmed the per-share amounts in PDF.
    """
    attached = []
    for event in events:
        clone = dict(event)
        matches = [
            a for a in official
            if a["symbol"] == event["symbol"]
            and a["published_calendar_date"] == event["implementation_announcement_date"]
            and ("实施" in a["announcement_title"])
            and any(term in a["announcement_title"] for term in
                    ("分红", "派息", "权益分派", "利润分配"))
        ]
        clone["official_announcement_metadata_matches"] = len(matches)
        clone["official_announcement_pdf_urls"] = sorted({
            x["pdf_url"] for x in matches
        })
        clone["amount_verified_against_official_pdf"] = False
        clone["evidence_grade"] = (
            "OFFICIAL_PUBLICATION_DAY_MATCHED_AMOUNTS_UNCHECKED"
            if matches else "THIRD_PARTY_DATE_ONLY_NOT_OFFICIALLY_MATCHED"
        )
        attached.append(clone)
    return attached


def first_usable_exchange_session(publication_date: str,
                                  exchange_calendar: Iterable) -> str:
    """Conservative PIT time rule: information usable at next trading session."""
    d = pd.Timestamp(publication_date).normalize()
    calendar = sorted(pd.Timestamp(x).normalize() for x in exchange_calendar)
    dates = [x for x in calendar if x > d]
    if not dates:
        raise ValueError("No later exchange session available")
    return dates[0].date().isoformat()


def implementation_known_on(event: dict, decision_day: str) -> bool:
    """At close of date D, use implementation only when announcement date < D."""
    return pd.Timestamp(decision_day) > pd.Timestamp(
        event["implementation_announcement_date"]
    )


def settle_nominal_action(
    *, shares_at_record_close: float,
    event: dict,
) -> dict:
    """Nominal share/cash entitlement from a known implementation event.

    Not a trading simulator: shares and cash *owed* are computed, and cash
    must be posted on the independently verified pay date. If payment date
    is absent, the cash remains pending. Adjusted-series shares are forbidden.
    """
    if not math.isfinite(shares_at_record_close) or shares_at_record_close < 0:
        raise ValueError("Invalid nominal share quantity")
    if not event.get("nominal_shares_and_currency_only"):
        raise ValueError("Event is not validated for nominal entitlement accounting")
    multiplier = (
        1
        + float(event["stock_bonus_per_share"])
        + float(event["capital_transfer_per_share"])
    )
    if multiplier < 1:
        raise ValueError("Invalid bonus share multiplier")
    return {
        "shares_before": float(shares_at_record_close),
        "shares_ex_date_nominal": float(shares_at_record_close * multiplier),
        "dividend_receivable_pre_tax": float(
            shares_at_record_close * float(event["cash_per_share_pre_tax"])
        ),
        "payment_date": event.get("payment_date"),
        "payment_posted": False,
        "cash_tax_and_broker_entitlement_verification_pending": True,
        "source_announcement_date": event["implementation_announcement_date"],
    }
