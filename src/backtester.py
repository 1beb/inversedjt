"""Portfolio simulation engine for the contrarian options strategy."""
import math
from datetime import timedelta

import pandas as pd
import yfinance as yf

from src.config import (
    COMMISSION_BASE, COMMISSION_MIN, COMMISSION_PER_CONTRACT,
    RISK_FREE_RATE, SPY_TICKER,
)
from src.options_pricer import black_scholes_price, calculate_option_pnl


def calculate_commission(num_contracts: int) -> float:
    """Calculate Questrade options commission for a single order."""
    if num_contracts <= 0:
        return 0
    return max(COMMISSION_MIN, COMMISSION_BASE + num_contracts * COMMISSION_PER_CONTRACT)


def option_type_is_itm(option_type: str, strike: float, expiry_price: float | None) -> bool:
    """Check if option expires in the money (needs closing trade)."""
    if expiry_price is None:
        return False
    if option_type == "call":
        return expiry_price > strike
    return expiry_price < strike


def get_prices(ticker_symbol: str = SPY_TICKER, start: str = "2026-01-01", end: str = "2026-12-31") -> pd.DataFrame:
    """Fetch OHLC data from yfinance for any ticker."""
    ticker = yf.Ticker(ticker_symbol)
    df = ticker.history(start=start, end=end)
    # Remove timezone info to avoid tz-naive vs tz-aware comparison issues
    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)
    return df


def get_spy_prices(start: str = "2026-01-01", end: str = "2026-12-31") -> pd.DataFrame:
    """Fetch SPY OHLC data from yfinance."""
    return get_prices(SPY_TICKER, start, end)


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
    iv_override: float | None = None,
) -> pd.DataFrame:
    """Run the backtest simulation across all 3 expiry windows.

    Args:
        prices: SPY OHLC DataFrame indexed by date
        signals: dict mapping date strings to "put" or "call"
        starting_capital: initial portfolio value
        bet_fraction: fraction of portfolio to bet per trade
        iv_override: if set, use this implied volatility instead of historical vol
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
        if iv_override is not None:
            current_vol = iv_override
        else:
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

            # Commissions: pay on open, pay on close (unless expires worthless)
            open_commission = calculate_commission(num_contracts)
            if option_type_is_itm(signal, strike, expiry_price):
                close_commission = calculate_commission(num_contracts)
            else:
                close_commission = 0  # expires worthless, no closing trade
            total_commission = open_commission + close_commission

            net_pnl = pnl - total_commission
            portfolios[window_name] += net_pnl

            trade_row[f"option_price_{window_name}"] = option_price
            trade_row[f"num_contracts_{window_name}"] = num_contracts
            trade_row[f"dte_{window_name}"] = dte
            trade_row[f"expiry_price_{window_name}"] = expiry_price
            trade_row[f"pnl_gross_{window_name}"] = pnl
            trade_row[f"commission_{window_name}"] = total_commission
            trade_row[f"pnl_{window_name}"] = net_pnl
            trade_row[f"portfolio_{window_name}"] = portfolios[window_name]

        trades.append(trade_row)

    return pd.DataFrame(trades)
