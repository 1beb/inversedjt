"""Portfolio simulation engine for the contrarian options strategy."""
import math
from datetime import timedelta

import pandas as pd
import yfinance as yf

from src.config import RISK_FREE_RATE, SPY_TICKER
from src.options_pricer import black_scholes_price, calculate_option_pnl


def get_spy_prices(start: str = "2026-01-01", end: str = "2026-12-31") -> pd.DataFrame:
    """Fetch SPY OHLC data from yfinance."""
    ticker = yf.Ticker(SPY_TICKER)
    df = ticker.history(start=start, end=end)
    # Remove timezone info to avoid tz-naive vs tz-aware comparison issues
    df.index = df.index.tz_localize(None)
    return df


def estimate_volatility(prices: pd.DataFrame, window: int = 20) -> pd.Series:
    """Calculate rolling annualized volatility from daily returns."""
    returns = prices["Close"].pct_change()
    return returns.rolling(window).std() * math.sqrt(252)


def days_to_expiry(trade_date: pd.Timestamp, window_name: str, prices: pd.DataFrame) -> int:
    """Calculate days to expiration based on window type."""
    if window_name == "next_day":
        return 1
    elif window_name == "end_of_week":
        # Days until Friday
        days_until_friday = 4 - trade_date.weekday()
        if days_until_friday <= 0:
            days_until_friday += 5
        return max(days_until_friday, 1)
    elif window_name == "thirty_day":
        return 30
    return 1


def find_expiry_price(prices: pd.DataFrame, trade_date: pd.Timestamp, dte: int) -> float | None:
    """Find the closing price at or near the expiry date."""
    target = trade_date + timedelta(days=dte)
    # Find nearest trading day at or after target
    future_dates = prices.index[prices.index >= target]
    if len(future_dates) == 0:
        # If expiry is past our data, use last available price
        return prices["Close"].iloc[-1] if len(prices) > 0 else None
    return prices["Close"].loc[future_dates[0]]


def run_backtest(
    prices: pd.DataFrame,
    signals: dict[str, str],
    starting_capital: float,
    bet_fraction: float,
) -> pd.DataFrame:
    """Run the backtest simulation across all 3 expiry windows.

    Args:
        prices: SPY OHLC DataFrame indexed by date
        signals: dict mapping date strings to "put" or "call"
        starting_capital: initial portfolio value
        bet_fraction: fraction of portfolio to bet per trade
    """
    vol = estimate_volatility(prices)

    portfolios = {
        "next_day": starting_capital,
        "end_of_week": starting_capital,
        "thirty_day": starting_capital,
    }

    trades = []

    for date_str, signal in sorted(signals.items()):
        trade_date = pd.Timestamp(date_str)

        # Find this date in prices (must be a trading day)
        if trade_date not in prices.index:
            # Find next trading day
            future = prices.index[prices.index >= trade_date]
            if len(future) == 0:
                continue
            trade_date = future[0]

        spot = prices.loc[trade_date, "Open"]
        current_vol = vol.loc[:trade_date].dropna().iloc[-1] if len(vol.loc[:trade_date].dropna()) > 0 else 0.20
        strike = round(spot)  # ATM

        trade_row = {
            "date": date_str,
            "trade_date": trade_date,
            "signal": signal,
            "spot": spot,
            "strike": strike,
            "volatility": current_vol,
        }

        for window_name in ["next_day", "end_of_week", "thirty_day"]:
            dte = days_to_expiry(trade_date, window_name, prices)
            T = dte / 365

            option_price = black_scholes_price(
                S=spot, K=strike, T=T, r=RISK_FREE_RATE,
                sigma=current_vol, option_type=signal,
            )

            # How much to spend
            budget = portfolios[window_name] * bet_fraction
            # Each contract costs option_price * 100
            cost_per_contract = option_price * 100
            if cost_per_contract <= 0:
                num_contracts = 0
            else:
                num_contracts = max(1, int(budget / cost_per_contract))

            total_cost = num_contracts * cost_per_contract

            # Find expiry price
            expiry_price = find_expiry_price(prices, trade_date, dte)
            if expiry_price is None:
                pnl = 0
            else:
                pnl = calculate_option_pnl(
                    entry_price=option_price,
                    spot_at_entry=spot,
                    spot_at_expiry=expiry_price,
                    strike=strike,
                    option_type=signal,
                    num_contracts=num_contracts,
                )

            portfolios[window_name] += pnl

            trade_row[f"option_price_{window_name}"] = option_price
            trade_row[f"num_contracts_{window_name}"] = num_contracts
            trade_row[f"dte_{window_name}"] = dte
            trade_row[f"expiry_price_{window_name}"] = expiry_price
            trade_row[f"pnl_{window_name}"] = pnl
            trade_row[f"portfolio_{window_name}"] = portfolios[window_name]

        trades.append(trade_row)

    return pd.DataFrame(trades)
