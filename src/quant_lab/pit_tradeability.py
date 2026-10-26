"""Historical exchange-status evidence and fillability audit (not broker fills).

Authoritative point-of-trade checks require official *historical* daily
up/down limit levels and suspension/resumption status. Qlib historical bars
alone do not provide those records. Historical opening volume means shares
*traded somewhere that session* but cannot prove that our order would fill
at the opening auction at the observed price or size.

Optional schemas match Tushare Pro suspend_d/stk_limit/daily (each may require
2000-point/paid authorization) and verified official exchange notices.
This module never silently substitutes a guessed ±10% band.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any
import math

import pandas as pd

from .pit_events import qlib_symbol


def standard_date(x, field: str) -> str:
    if x is None or str(x).strip() == "":
        raise ValueError(f"Missing {field}")
    t = pd.to_datetime(x, errors="raise")
    if pd.isna(t):
        raise ValueError(f"Bad {field}")
    return t.date().isoformat()


def _price(x, field: str, *, optional=False) -> float | None:
    if x is None or str(x).strip() in ("", "nan", "None"):
        if optional:
            return None
        raise ValueError(f"Missing required {field}")
    y = float(x)
    if not math.isfinite(y) or y <= 0:
        raise ValueError(f"Invalid {field}")
    return y


def normalise_tushare_limits(rows: list[dict]) -> pd.DataFrame:
    """Tushare stk_limit: actual historical up/down price *levels*.

    Official-source quality still depends on data provider accuracy.
    Values are limits applicable at attempted trade day's opening.
    A stock may trade *at* a limit; conservative gate blocks without queue data.
    """
    result = []
    for row in rows:
        symbol = qlib_symbol(row["ts_code"])
        date = standard_date(row["trade_date"], "trade_date")
        up = _price(row.get("up_limit"), "up_limit")
        down = _price(row.get("down_limit"), "down_limit")
        if down >= up:
            raise ValueError("down_limit must be below up_limit")
        result.append({
            "symbol": symbol, "trade_date": date,
            "up_limit_raw": up, "down_limit_raw": down,
            "source": "TUSHARE_STK_LIMIT_AUTHENTICATED",
            "availability": "session_morning_before_open_not_previous_close",
        })
    frame = pd.DataFrame(result)
    if not frame.empty and frame.duplicated(["symbol", "trade_date"]).any():
        raise ValueError("Duplicate official daily stock limit key")
    return frame


def normalise_tushare_suspensions(rows: list[dict]) -> pd.DataFrame:
    """Tushare suspend_d: S/R, partial intraday interval distinguished."""
    items = []
    for row in rows:
        symbol = qlib_symbol(row["ts_code"])
        date = standard_date(row["trade_date"], "trade_date")
        typ = str(row.get("suspend_type") or "").strip().upper()
        if typ not in ("S", "R"):
            raise ValueError("Expected suspend_type S/R")
        timing = str(row.get("suspend_timing") or "").strip()
        items.append({
            "symbol": symbol, "trade_date": date,
            "suspend_type": typ, "intraday_timing": timing,
            "full_day_suspension": typ == "S" and not timing,
            "source": "TUSHARE_SUSPEND_D_AUTHENTICATED",
        })
    frame = pd.DataFrame(items)
    if not frame.empty and frame.duplicated(["symbol", "trade_date", "suspend_type", "intraday_timing"]).any():
        raise ValueError("Duplicate historical suspension record")
    return frame


def normalise_daily_ohlcv(rows: list[dict]) -> pd.DataFrame:
    """Tushare daily: unadjusted bar/turnover for retrospective market audit."""
    items = []
    for row in rows:
        symbol = qlib_symbol(row["ts_code"])
        date = standard_date(row["trade_date"], "trade_date")
        opening = _price(row.get("open"), "daily.open")
        closing = _price(row.get("close"), "daily.close")
        volume = float(row.get("vol", 0))
        if not math.isfinite(volume) or volume < 0:
            raise ValueError("Invalid daily volume")
        items.append({
            "symbol": symbol, "trade_date": date,
            "open_raw": opening, "close_raw": closing,
            "traded_volume_lots": volume,
            "volume_unit": "100_shares_if_standard_A_share_lots",
            "source": "TUSHARE_DAILY_AUTHENTICATED",
        })
    result = pd.DataFrame(items)
    if not result.empty and result.duplicated(["symbol", "trade_date"]).any():
        raise ValueError("Duplicate OHLCV key")
    return result


@dataclass(frozen=True)
class TradeEvidence:
    symbol: str
    trade_date: str
    exchange_listed_asof: bool
    bar_open_raw: float | None
    bar_volume_positive: bool | None
    source_trading_status: str | None = None
    full_day_suspension: bool | None = None
    intraday_suspension: bool | None = None
    official_up_limit_raw: float | None = None
    official_down_limit_raw: float | None = None
    official_limits_source: str | None = None
    official_halt_source: str | None = None
    opening_auction_executable_quantity: float | None = None
    # Auction order-book queue priority, and brokerage execution reports,
    # are unavailable from these public OHLCV feeds.


def audit_execution(evidence: TradeEvidence, *,
                    side: str, intended_order_shares: float,
                    decision_day: str) -> dict[str, Any]:
    """Fail closed on known halts/limit-lock and expose unresolved fills.

    LOOKAHEAD: decision_day must precede trade_date, and the target ranking
    may NEVER use this function's trade-date inputs. This is a post-signal
    execution audit, not a model feature.
    """
    if side not in ("buy", "sell"):
        raise ValueError("Order side must be buy/sell")
    if not math.isfinite(intended_order_shares) or intended_order_shares <= 0:
        raise ValueError("Order quantity must be positive and finite")
    trade_date = standard_date(evidence.trade_date, "trade_date")
    decision_date = standard_date(decision_day, "decision_day")
    if not decision_date < trade_date:
        raise ValueError("Attempted to use trade-day evidence on prior/same decision")
    symbol = qlib_symbol(evidence.symbol)
    base = {
        "symbol": symbol, "decision_day": decision_date,
        "attempted_trade_date": trade_date,
        "order_side": side, "intended_shares": intended_order_shares,
        "is_verified_broker_fill": False,
        "observed_transaction_id": None,
        "auction_depth_verified": evidence.opening_auction_executable_quantity is not None,
        "limit_source": evidence.official_limits_source,
        "halt_source": evidence.official_halt_source,
    }
    if not evidence.exchange_listed_asof:
        return {**base, "status": "BLOCKED_DELISTED", "would_simulator_fill": False}
    if evidence.full_day_suspension is True:
        return {**base, "status": "BLOCKED_OFFICIALLY_SUSPENDED",
                "would_simulator_fill": False}
    if evidence.intraday_suspension is True:
        # Without exact interval at auction, do not assume the opening was
        # available. Another source would be needed to clear this.
        return {**base, "status": "BLOCKED_INTRADAY_TIME_UNRESOLVED",
                "would_simulator_fill": False}
    if evidence.source_trading_status in ("HALTED", "SUSPENDED", "0"):
        return {**base, "status": "BLOCKED_HISTORICAL_TRADING_STATUS",
                "would_simulator_fill": False}
    if (evidence.bar_open_raw is None
            or not math.isfinite(evidence.bar_open_raw)
            or evidence.bar_open_raw <= 0
            or evidence.bar_volume_positive is not True):
        return {**base, "status": "BLOCKED_NO_CONFIRMED_OPEN_AND_VOLUME",
                "would_simulator_fill": False}
    has_limits = (
        evidence.official_up_limit_raw is not None
        and evidence.official_down_limit_raw is not None
        and evidence.official_limits_source is not None
    )
    if has_limits:
        up = _price(evidence.official_up_limit_raw, "official_up_limit_raw")
        down = _price(evidence.official_down_limit_raw, "official_down_limit_raw")
        if down >= up:
            raise ValueError("Official daily limits inverted")
        if side == "buy" and evidence.bar_open_raw >= up - 0.005:
            return {**base, "status": "BLOCKED_CONSERVATIVE_BUY_AT_PRICE_LIMIT",
                    "would_simulator_fill": False}
        if side == "sell" and evidence.bar_open_raw <= down + 0.005:
            return {**base, "status": "BLOCKED_CONSERVATIVE_SELL_AT_PRICE_LIMIT",
                    "would_simulator_fill": False}
    else:
        return {**base, "status": "UNCERTIFIED_NO_DAILY_OFFICIAL_LIMIT_LEVELS",
                "would_simulator_fill": False}
    if (evidence.full_day_suspension is None
            and evidence.source_trading_status is None
            and evidence.official_halt_source is None):
        return {**base, "status": "UNCERTIFIED_NO_HISTORICAL_HALT_STATUS",
                "would_simulator_fill": False}
    auction_depth = evidence.opening_auction_executable_quantity
    if auction_depth is None or not math.isfinite(auction_depth):
        return {**base, "status": "UNCERTIFIED_ORDERBOOK_QUEUE_NOT_AVAILABLE",
                "would_simulator_fill": False}
    if auction_depth < intended_order_shares:
        return {**base, "status": "BLOCKED_AUCTION_DEPTH_INSUFFICIENT",
                "would_simulator_fill": False}
    # Even estimated depth does not certify queue position / true broker fill.
    return {**base, "status": "MODEL_ELIGIBLE_FILL_NOT_BROKER_VERIFIED",
            "would_simulator_fill": True}
