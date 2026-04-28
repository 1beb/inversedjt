"""Mark-to-market backtester for Polymarket binary positions.

Mechanics:
- Buy NO on "put" signals (Trump bullish → bet his claim doesn't come true).
- Buy YES on "call" signals (Trump bearish → bet his pessimism is wrong).
- Per signal day: allocate (cash * bet_fraction), split equally across selected markets.
- No commissions on Polymarket (USDC on Polygon).
- Forced exit at hold-window end OR market resolution, whichever comes first.
- Daily MTM uses the last-quoted side price on or before each calendar day.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Callable

import pandas as pd

from src.polymarket import Market

MIN_TRADE = 1.0  # $1 minimum per market position


def _close_date(open_date: pd.Timestamp, hold_window: str) -> pd.Timestamp:
    if hold_window == "next_day":
        return open_date + timedelta(days=1)
    if hold_window == "end_of_week":
        # Friday of the open_date's week
        days_to_fri = (4 - open_date.weekday()) % 7
        if days_to_fri == 0:
            days_to_fri = 7
        return open_date + timedelta(days=days_to_fri)
    if hold_window == "thirty_day":
        return open_date + timedelta(days=30)
    raise ValueError(f"unknown hold window: {hold_window}")


@dataclass
class PolyPosition:
    market_id: str
    side: str           # "YES" or "NO"
    open_date: pd.Timestamp
    target_close: pd.Timestamp  # before forced-resolution clamp
    market_end: pd.Timestamp
    entry_price: float
    shares: float
    committed: float

    @property
    def effective_close(self) -> pd.Timestamp:
        return min(self.target_close, self.market_end)


def run_polymarket_backtest(
    markets: dict[str, Market],
    selector: Callable[[pd.Timestamp, str], list[str]],
    signals: dict[str, str],
    starting_capital: float,
    bet_fraction: float,
    hold_window: str,
    calendar_start: str = "2025-12-15",
    calendar_end: str = "2026-05-31",
    mode: str = "inverse",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    selector(date, signal) -> list of market_ids to trade that day.
    signals: {YYYY-MM-DD: "put" | "call"}
    mode: "inverse" → bet against Trump (NO on put, YES on call).
          "believe" → bet with Trump (YES on put, NO on call).
    """
    cash = starting_capital
    open_positions: list[PolyPosition] = []
    daily_snaps = []
    trade_log = []

    # Build calendar from union of all market quote dates
    all_dates = pd.DatetimeIndex([])
    for m in markets.values():
        all_dates = all_dates.union(m.yes_series.index).union(m.no_series.index)
    cal = all_dates[(all_dates >= calendar_start) & (all_dates <= calendar_end)].sort_values()

    for day in cal:
        # 1) Close positions whose effective close is today or earlier
        still_open = []
        for pos in open_positions:
            if day >= pos.effective_close:
                m = markets[pos.market_id]
                exit_p = m.price_on(pos.effective_close, pos.side)
                if exit_p is None:
                    exit_p = pos.entry_price  # extreme fallback
                proceeds = pos.shares * exit_p
                realized = proceeds - pos.committed
                cash += proceeds
                trade_log.append({
                    "open_date": pos.open_date,
                    "close_date": pos.effective_close,
                    "market_id": pos.market_id,
                    "question": m.question,
                    "topic": m.topic,
                    "side": pos.side,
                    "entry_price": pos.entry_price,
                    "exit_price": exit_p,
                    "shares": pos.shares,
                    "committed": pos.committed,
                    "proceeds": proceeds,
                    "realized_pnl": realized,
                    "forced_exit": pos.market_end < pos.target_close,
                })
            else:
                still_open.append(pos)
        open_positions = still_open

        # 2) Open new positions on signal days
        date_str = day.strftime("%Y-%m-%d")
        sig = signals.get(date_str)
        if sig is not None:
            if mode == "inverse":
                side = "NO" if sig == "put" else "YES"
            else:  # believe
                side = "YES" if sig == "put" else "NO"
            candidate_ids = selector(day, sig)
            # Filter to markets active today with a quote, and not yet resolved
            tradable = []
            for mid in candidate_ids:
                m = markets.get(mid)
                if m is None: continue
                if not m.is_active_on(day): continue
                p = m.price_on(day, side)
                if p is None or p <= 0 or p >= 1: continue
                tradable.append((mid, p))

            if tradable:
                day_budget = cash * bet_fraction
                per_market = day_budget / len(tradable)
                if per_market >= MIN_TRADE:
                    for mid, p in tradable:
                        m = markets[mid]
                        shares = per_market / p
                        committed = shares * p
                        cash -= committed
                        open_positions.append(PolyPosition(
                            market_id=mid,
                            side=side,
                            open_date=day,
                            target_close=_close_date(day, hold_window),
                            market_end=m.end_date,
                            entry_price=p,
                            shares=shares,
                            committed=committed,
                        ))

        # 3) Mark-to-market
        positions_mtm = 0.0
        for pos in open_positions:
            m = markets[pos.market_id]
            cur = m.price_on(day, pos.side)
            if cur is None:
                cur = pos.entry_price
            positions_mtm += pos.shares * cur

        daily_snaps.append({
            "date": day,
            "cash": cash,
            "positions_mtm": positions_mtm,
            "total_value": cash + positions_mtm,
            "num_open": len(open_positions),
        })

    # Force-close any remaining open positions at end of calendar
    for pos in open_positions:
        m = markets[pos.market_id]
        last_day = cal[-1]
        exit_p = m.price_on(min(last_day, pos.market_end), pos.side) or pos.entry_price
        proceeds = pos.shares * exit_p
        cash += proceeds
        trade_log.append({
            "open_date": pos.open_date,
            "close_date": last_day,
            "market_id": pos.market_id,
            "question": m.question,
            "topic": m.topic,
            "side": pos.side,
            "entry_price": pos.entry_price,
            "exit_price": exit_p,
            "shares": pos.shares,
            "committed": pos.committed,
            "proceeds": proceeds,
            "realized_pnl": proceeds - pos.committed,
            "forced_exit": True,
        })

    daily_curve = pd.DataFrame(daily_snaps).set_index("date")
    trade_df = pd.DataFrame(trade_log) if trade_log else pd.DataFrame()
    return daily_curve, trade_df
