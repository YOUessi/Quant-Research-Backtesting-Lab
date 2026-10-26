"""EXP-002 event-driven, trading-halt-aware *proxy* simulator.

Signals are decided using close(t) data, orders are first attempted at the
following open(t+1). No future orderability is used when ranking candidates.

Valuation uses Qlib adjusted price units, which implicitly assumes a
corporate-action total-return proxy and does not represent actual share/cash
entitlement. Missing execution prices/volumes never result in fills.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class ExecutionConfig:
    strategy: str = "momentum"
    rebalance_sessions: int = 1
    k: int = 10
    fee_bps: float = 10.0
    max_stale_sessions: int = 5
    price_limit_proxy: bool = False
    proxy_threshold: float = 0.098

    def __post_init__(self):
        if self.strategy not in ("momentum", "alphabetical", "full_equal"):
            raise ValueError("Unsupported strategy")
        if self.k < 1 or self.rebalance_sessions < 1 or self.max_stale_sessions < 0:
            raise ValueError("Invalid k/rebalance/staleness")
        if not 0 <= self.fee_bps < 10000:
            raise ValueError("Invalid fee_bps")
        if not 0 < self.proxy_threshold < 0.5:
            raise ValueError("Invalid proxy threshold")


def _positive(value) -> bool:
    return bool(pd.notna(value) and np.isfinite(value) and value > 0)


def _fillability(day: pd.DataFrame, asset: str, *, side: str,
                 cfg: ExecutionConfig) -> tuple[bool, str]:
    if asset not in day.index:
        return False, "asset_missing_on_exchange_calendar"
    x = day.loc[asset]
    if not bool(x["listed_asof"]):
        return False, "not_exchange_listed_asof_trade_day"
    if not _positive(x["adj_open"]) or not _positive(x["volume_adjusted"]):
        return False, "suspended_or_missing_open_or_volume"
    if cfg.price_limit_proxy:
        previous = x["prior_raw_close"]
        now = x["raw_open_estimate"]
        if not (_positive(previous) and _positive(now)):
            return False, "proxy_prev_raw_price_unavailable"
        change = now / previous - 1
        if side == "buy" and change >= cfg.proxy_threshold:
            return False, "PROXY_limit_up_open_not_verified_regulatory"
        if side == "sell" and change <= -cfg.proxy_threshold:
            return False, "PROXY_limit_down_open_not_verified_regulatory"
    return True, "idealized_next_open_fill_unverified"


def _choose(signal_day: pd.DataFrame, cfg: ExecutionConfig) -> list[str]:
    pool = signal_day.loc[signal_day["signal_eligible"]].copy()
    if len(pool) < cfg.k:
        raise ValueError(f"Only {len(pool)} eligible as-of close assets, need {cfg.k}")
    if cfg.strategy == "momentum":
        pool = pool.sort_values(["momentum_5", "asset"],
                                ascending=[False, True])
        return pool["asset"].iloc[:cfg.k].to_list()
    if cfg.strategy == "alphabetical":
        return sorted(pool["asset"].to_list())[:cfg.k]
    return sorted(pool["asset"].to_list())


def simulate(
    panel: pd.DataFrame, *,
    first_test: str,
    last_test: str,
    cfg: ExecutionConfig,
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Accounting for a fully specified *model* portfolio, never broker fills.

    At each open(d), uses selection from close(previous_exchange_session).
    If a needed bar has no open or positive volume, keeps the pending holding
    or cash. If held closing value is unavailable for >cfg.max_stale_sessions
    or there is an unresolved delisting, the run is explicitly CENSORED.

    A stale mark-to-market day is flagged and makes the run non-certifiable
    even if the missing bar returns later.
    """
    required = {"asset", "date", "adj_open", "adj_close",
                "volume_adjusted", "signal_eligible", "index_member_asof",
                "listed_asof",
                "momentum_5", "prior_raw_close", "raw_open_estimate",
                "factor_step_ratio"}
    if not required.issubset(panel.columns):
        raise ValueError(f"Missing input columns: {required - set(panel.columns)}")
    if panel.duplicated(["asset", "date"]).any():
        raise ValueError("Non-unique ticker/date input")
    grouped = dict(tuple(panel.groupby("date", sort=True)))
    dates = sorted(pd.to_datetime(list(grouped.keys())))
    first, last = pd.Timestamp(first_test), pd.Timestamp(last_test)
    study_dates = [d for d in dates if first <= d <= last]
    if not study_dates or dates.index(study_dates[0]) < 1:
        raise ValueError("Need study sessions and preceding signal session")
    index_map = {d: i for i, d in enumerate(dates)}
    positions: dict[str, float] = {}
    cash = 1.0
    last_close: dict[str, float] = {}
    stale: dict[str, int] = {}
    event_rows: list[dict] = []
    daily_rows: list[dict] = []
    stopped: dict | None = None
    previous_value = 1.0
    stale_valuation_days = 0
    corporate_action_proxy_position_days = 0
    forced_exits = 0
    blocked_attempts: dict[str, int] = {}
    total_fee = 0.0

    for i, daydate in enumerate(study_dates):
        di = index_map[daydate]
        signal_date = dates[di - 1]
        trade_day = grouped[daydate].set_index("asset", drop=False)
        signal_day = grouped[signal_date]
        # Mark-to-open holdings conservatively; last available adjusted close
        # is a stale valuation proxy, not an assertion that a halted stock sells.
        def price_for(a: str, column: str) -> float | None:
            if a in trade_day.index and _positive(trade_day.at[a, column]):
                return float(trade_day.at[a, column])
            return last_close.get(a)

        for a in list(positions):
            if a not in trade_day.index or not _positive(trade_day.at[a, "adj_open"]):
                blocked_attempts["held_open_missing_or_suspended"] = blocked_attempts.get(
                    "held_open_missing_or_suspended", 0) + 1
        if any(price_for(a, "adj_open") is None for a in positions):
            stopped = {"date": str(daydate.date()),
                       "reason": "held_asset_no_price_for_open_valuation",
                       "assets": sorted(a for a in positions
                                        if price_for(a, "adj_open") is None)}
            break
        # The listing history is independent of index membership. Do not
        # invent a last-close liquidation when a holding has been delisted.
        delisted_held = sorted(a for a in positions if (
            a not in trade_day.index or not bool(trade_day.at[a, "listed_asof"])
        ))
        if delisted_held:
            stopped = {
                "date": str(daydate.date()),
                "reason": "DELISTING_SETTLEMENT_UNKNOWN_FAIL_CLOSED",
                "assets": delisted_held,
            }
            break
        trading_fee = 0.0
        equity_open = cash + sum(positions[a] * price_for(a, "adj_open")
                                 for a in positions)
        if not np.isfinite(equity_open) or equity_open <= 0:
            stopped = {"date": str(daydate.date()), "reason": "nonpositive_account_value"}
            break

        # Always attempt to exit a name that was not an index constituent at
        # the previous decision close, even between weekly rebalance events.
        active_asof = set(signal_day.loc[
            signal_day["index_member_asof"], "asset"].to_list())
        forced = sorted(set(positions) - active_asof)
        if i % cfg.rebalance_sessions == 0:
            target = _choose(signal_day, cfg)
        else:
            target = sorted(positions)
        target_set = set(target) - set(forced)
        if forced:
            forced_exits += len(forced)
        is_rebalance = (i % cfg.rebalance_sessions == 0) or bool(forced)
        if is_rebalance:
            # For a dynamic full-universe equal-weight benchmark the k is
            # the number of eligible names, otherwise it is the frozen top-k.
            denominator = len(target_set)
            if denominator < 1:
                stopped = {"date": str(daydate.date()),
                           "reason": "zero_target_candidates"}
                break
            target_value = equity_open / denominator
            desired = {a: target_value for a in target_set}

            def record(side: str, symbol: str, value: float, status: str):
                event_rows.append({
                    "date": daydate, "signal_date": signal_date, "side": side,
                    "asset": symbol, "gross_notional": float(value),
                    "status": status,
                })
                if status != "idealized_next_open_fill_unverified":
                    blocked_attempts[status] = blocked_attempts.get(status, 0) + 1

            # Sell first; an untradeable holding remains in the account.
            for asset in sorted(list(positions)):
                held = positions[asset] * price_for(asset, "adj_open")
                wanted = desired.get(asset, 0.0)
                sell_amount = max(0.0, held - wanted)
                if sell_amount <= 1e-12:
                    continue
                okay, reason = _fillability(trade_day, asset, side="sell", cfg=cfg)
                if not okay:
                    record("sell", asset, sell_amount, reason)
                    continue
                unit_price = float(trade_day.at[asset, "adj_open"])
                shares_to_sell = min(positions[asset], sell_amount / unit_price)
                actual = shares_to_sell * unit_price
                fee = actual * cfg.fee_bps / 10000
                cash += actual - fee
                trading_fee += fee
                positions[asset] -= shares_to_sell
                if positions[asset] <= 1e-12:
                    del positions[asset]
                    stale.pop(asset, None)
                record("sell", asset, actual, reason)
            # Buy second. Insufficient cash stays cash, never borrow.
            for asset in sorted(target_set):
                opening = price_for(asset, "adj_open")
                held = positions.get(asset, 0.0) * (opening or 0)
                need = max(0.0, desired[asset] - held)
                if need <= 1e-12:
                    continue
                okay, reason = _fillability(trade_day, asset, side="buy", cfg=cfg)
                if not okay:
                    record("buy", asset, need, reason)
                    continue
                actual = min(need, cash / (1 + cfg.fee_bps / 10000))
                if actual <= 1e-12:
                    continue
                p = float(trade_day.at[asset, "adj_open"])
                shares = actual / p
                fee = actual * cfg.fee_bps / 10000
                cash -= actual + fee
                trading_fee += fee
                positions[asset] = positions.get(asset, 0.0) + shares
                record("buy", asset, actual, reason)
            if cash < -1e-8:
                raise AssertionError("Portfolio borrowed cash")

        # Mark-to-close and classify missing close. Never discard holdings.
        equity_close = cash
        had_stale = False
        for asset in sorted(list(positions)):
            x = trade_day.loc[asset] if asset in trade_day.index else None
            pclose = x["adj_close"] if x is not None else np.nan
            if not _positive(pclose):
                stale[asset] = stale.get(asset, 0) + 1
                had_stale = True
                if stale[asset] > cfg.max_stale_sessions or asset not in last_close:
                    stopped = {
                        "date": str(daydate.date()),
                        "reason": "unresolved_halt_or_delisting_held_position",
                        "assets": [asset], "stale_sessions": stale[asset],
                    }
                    break
                pclose = last_close[asset]
            else:
                stale[asset] = 0
            if x is not None and _positive(x["factor_step_ratio"]):
                if abs(float(x["factor_step_ratio"]) - 1) > 0.01:
                    corporate_action_proxy_position_days += 1
            equity_close += positions[asset] * float(pclose)
        if stopped:
            break
        if had_stale:
            stale_valuation_days += 1
        # Only after PnL accounting update yesterday's known mark reference.
        for asset, x in trade_day.iterrows():
            if _positive(x["adj_close"]):
                last_close[asset] = float(x["adj_close"])
        if equity_close <= 0 or not np.isfinite(equity_close):
            stopped = {"date": str(daydate.date()), "reason": "invalid_mark_to_market"}
            break
        total_fee += trading_fee
        daily_rows.append({
            "date": daydate, "signal_date": signal_date,
            "equity_close_proxy": float(equity_close),
            "daily_return_proxy": float(equity_close / previous_value - 1),
            "cash_close": float(cash), "held_positions": len(positions),
            "fee_paid": float(trading_fee),
            "mark_to_market_stale": bool(had_stale),
            "forced_delisted_or_ex_member_exit_orders": len(forced),
        })
        previous_value = equity_close

    daily = pd.DataFrame(daily_rows)
    events = pd.DataFrame(event_rows)
    status = "CENSORED_UNRESOLVED_POSITION" if stopped else (
        "COMPLETED_PROXY_WITH_STALE_MARKS" if stale_valuation_days else
        "COMPLETED_ADJUSTED_PRICE_PROXY"
    )
    report = {
        "status": status, "configuration": asdict(cfg),
        "n_requested_study_sessions": len(study_dates),
        "n_completed_sessions": len(daily),
        "n_events": len(events),
        "n_model_filled_attempts": int(
            (events["status"] == "idealized_next_open_fill_unverified").sum()
        ) if len(events) else 0,
        "blocked_attempts": blocked_attempts,
        "n_stale_close_days": stale_valuation_days,
        "n_forced_membership_exits": forced_exits,
        "n_factor_shock_held_position_days": corporate_action_proxy_position_days,
        "fees_total_initial_equity_units": float(total_fee),
        "terminal_net_value_proxy": float(daily["equity_close_proxy"].iloc[-1]) if len(daily) else None,
        "terminal_total_return_proxy": float(daily["equity_close_proxy"].iloc[-1] - 1) if len(daily) and not stopped else None,
        "stop_event": stopped,
        "actual_exchange_limit_prices_used": False,
        "price_limit_gate_is_proxy_stress_not_regulatory": cfg.price_limit_proxy,
        "corporate_action_pit_audited": False,
        "corporate_action_cash_and_share_entitlements_reconciled": False,
        "open_auction_fills_observed": False,
        "delisting_settlement_mode": "abort-if-unvalued; never fictitiously liquidate",
        "profitability_claim_supported": False,
        "valuation_warning": (
            "Qlib adjusted-price shares are total-return PROXY UNITS, not original "
            "tradeable shares. Closing marks may be stale during suspension. "
            "Order fills assume full quantities at observed opening prices and are "
            "not backed by order book or historical broker records."
        ),
    }
    return daily, events, report
