"""Mark-to-market backtester with daily portfolio valuation and proper position sizing.

Fixes from the original backtester:
- Tracks all open positions daily with mark-to-market
- Sizes new trades based on actual free capital (cash not locked in positions)
- Produces a daily equity curve, not just trade-to-trade snapshots
- Handles overlapping 30-day positions correctly
"""
from dataclasses import dataclass, field
from datetime import timedelta

import pandas as pd

from src.backtester import days_to_expiry, get_prices
from src.config import MIN_TRADE_SIZE


STOCK_COMMISSION = 4.95  # per trade


@dataclass
class Position:
    open_date: pd.Timestamp
    close_date: pd.Timestamp
    signal: str
    ticker: str
    entry_price: float
    shares: int
    committed_capital: float

    def mtm_value(self, current_price: float) -> float:
        return self.shares * current_price

    def close(self, exit_price: float) -> float:
        """Close position, return proceeds after commission."""
        proceeds = self.shares * exit_price
        return proceeds - STOCK_COMMISSION


def find_close_date(trade_date: pd.Timestamp, hold_window: str, prices: pd.DataFrame) -> pd.Timestamp:
    """Find the actual trading day to close on."""
    dte = days_to_expiry(trade_date, hold_window, prices)
    target = trade_date + timedelta(days=dte)
    future = prices.index[prices.index >= target]
    if len(future) == 0:
        return prices.index[-1]
    return future[0]


def run_mtm_backtest(
    long_prices: pd.DataFrame,
    inverse_prices: pd.DataFrame,
    signals: dict[str, str],
    starting_capital: float,
    bet_fraction: float,
    hold_window: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Run mark-to-market backtest using inverse ETF pairs.

    On "put" signals: buy inverse ETF.
    On "call" signals: buy long ETF.
    Always long-only, no shorting.

    Returns:
        daily_curve: DataFrame with daily portfolio values
        trade_log: DataFrame with per-trade details
    """
    # Merge both price series to get a common trading day index
    all_dates = long_prices.index.union(inverse_prices.index).sort_values()

    cash = starting_capital
    open_positions: list[Position] = []
    daily_snapshots = []
    trade_log = []

    for day in all_dates:
        # 1. Close positions that have reached their close date
        still_open = []
        for pos in open_positions:
            if day >= pos.close_date:
                # Get exit price from the appropriate ETF
                if pos.ticker in long_prices.columns or pos.ticker == "long":
                    prices_for_pos = long_prices if pos.signal == "call" else inverse_prices
                else:
                    prices_for_pos = inverse_prices if pos.signal == "put" else long_prices

                if day in prices_for_pos.index:
                    exit_price = prices_for_pos.loc[day, "Close"]
                elif len(prices_for_pos.index[prices_for_pos.index >= pos.close_date]) > 0:
                    actual_close = prices_for_pos.index[prices_for_pos.index >= pos.close_date][0]
                    if actual_close == day:
                        exit_price = prices_for_pos.loc[day, "Close"]
                    else:
                        still_open.append(pos)
                        continue
                else:
                    exit_price = pos.entry_price  # fallback

                proceeds = pos.close(exit_price)
                realized_pnl = proceeds - pos.committed_capital
                cash += proceeds

                trade_log.append({
                    "open_date": pos.open_date,
                    "close_date": day,
                    "signal": pos.signal,
                    "entry_price": pos.entry_price,
                    "exit_price": exit_price,
                    "shares": pos.shares,
                    "committed_capital": pos.committed_capital,
                    "proceeds": proceeds,
                    "realized_pnl": realized_pnl,
                    "commission": STOCK_COMMISSION * 2,
                })
            else:
                still_open.append(pos)
        open_positions = still_open

        # 2. Open new position if this is a signal day
        date_str = day.strftime("%Y-%m-%d")
        if date_str in signals:
            signal = signals[date_str]
            bet_amount = cash * bet_fraction

            if bet_amount >= MIN_TRADE_SIZE:
                # Pick the right ETF
                if signal == "put":
                    prices_for_entry = inverse_prices
                else:
                    prices_for_entry = long_prices

                if day in prices_for_entry.index:
                    entry_price = prices_for_entry.loc[day, "Open"]
                    shares = int(bet_amount / entry_price)

                    if shares > 0:
                        committed = shares * entry_price + STOCK_COMMISSION
                        cash -= committed

                        close_date = find_close_date(day, hold_window, prices_for_entry)

                        pos = Position(
                            open_date=day,
                            close_date=close_date,
                            signal=signal,
                            ticker=signal,  # "put" or "call" to track which ETF
                            entry_price=entry_price,
                            shares=shares,
                            committed_capital=committed,
                        )
                        open_positions.append(pos)

        # 3. Mark-to-market all open positions
        positions_mtm = 0
        for pos in open_positions:
            if pos.signal == "put":
                p = inverse_prices
            else:
                p = long_prices

            if day in p.index:
                current_price = p.loc[day, "Close"]
            else:
                current_price = pos.entry_price
            positions_mtm += pos.mtm_value(current_price)

        # 4. Record daily snapshot
        total_value = cash + positions_mtm
        daily_snapshots.append({
            "date": day,
            "cash": cash,
            "positions_mtm": positions_mtm,
            "total_value": total_value,
            "num_open_positions": len(open_positions),
        })

    daily_curve = pd.DataFrame(daily_snapshots).set_index("date")
    trade_df = pd.DataFrame(trade_log) if trade_log else pd.DataFrame()

    return daily_curve, trade_df
