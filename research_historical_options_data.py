"""
Research: Historical Options Data Sources for TNA & TQQQ (Jan-Mar 2026)
========================================================================
Summary of findings and working code examples for each source.

BOTTOM LINE: True historical options *chains* (full snapshots of all strikes
on a past date) are essentially unavailable for free. What IS available:
  1. Historical OHLCV for individual option contracts (yoptions, Tradier, Polygon)
  2. Current/live option chains with IV and Greeks (yfinance, Tradier)
  3. Weekly free IV summary data (optionstrategist.com)
  4. CBOE volume data (free download, but no pricing/IV)
  5. Calculate your own IV from historical underlying prices + known strikes
"""

# =============================================================================
# 1. YFINANCE — Current options only, NOT historical
# =============================================================================
"""
yfinance can pull CURRENT option chains but CANNOT retrieve historical
options data from past dates. The option_chain() method always returns
the latest available snapshot.

VERDICT: Useful for capturing today's chain. Useless for Jan-Feb 2026 data
that has already passed.
"""

import yfinance as yf

def yfinance_current_chain(ticker_symbol: str):
    """Get current options chain — works only for live/current data."""
    tk = yf.Ticker(ticker_symbol)

    # List all available expiration dates
    print(f"Available expirations for {ticker_symbol}:")
    print(tk.options)  # tuple of date strings like ('2026-03-20', '2026-04-17', ...)

    # Get chain for a specific expiration
    if tk.options:
        exp = tk.options[0]
        chain = tk.option_chain(exp)
        calls = chain.calls  # DataFrame with columns:
        # contractSymbol, lastTradeDate, strike, lastPrice, bid, ask,
        # change, percentChange, volume, openInterest, impliedVolatility
        puts = chain.puts

        print(f"\nCalls for {exp}:")
        print(calls[['strike', 'lastPrice', 'bid', 'ask', 'impliedVolatility', 'volume']].head(10))
        return calls, puts
    return None, None


# =============================================================================
# 2. YOPTIONS — Historical OHLCV for specific option contracts
# =============================================================================
"""
yoptions scrapes Yahoo Finance for historical price data of INDIVIDUAL
option contracts. You must know the exact contract (ticker, expiry, strike,
type). It does NOT give you a full chain snapshot for a past date.

pip install yoptions
"""

def yoptions_historical(ticker: str, expiry: str, strike: float, opt_type: str):
    """
    Get historical OHLCV for a specific option contract.
    opt_type: 'c' for call, 'p' for put
    """
    try:
        import yoptions as yo
        # Returns DataFrame with Date, Open, High, Low, Close, Volume
        df = yo.get_historical_option(ticker, expiry, strike, opt_type)
        print(f"Historical data for {ticker} {expiry} {strike}{opt_type}:")
        print(df.head(10))
        return df
    except Exception as e:
        print(f"yoptions error: {e}")
        return None

# Example usage:
# yoptions_historical('TQQQ', '2026-03-20', 60.0, 'c')


# =============================================================================
# 3. TRADIER SANDBOX API — Best free option for historical options data
# =============================================================================
"""
Tradier's sandbox API is FREE (sign up at developer.tradier.com).
It provides:
  - Current option chains with IV and Greeks (via ORATS)
  - Historical OHLCV for individual option contracts using OCC symbols
  - Delayed data (~15 min)

OCC Symbol format: TQQQ260320C00060000
  = TQQQ, expiry 2026-03-20, Call, strike $60.00 (multiplied by 1000, zero-padded)

VERDICT: Best free source. Can get historical pricing for specific contracts.
"""
import requests

TRADIER_SANDBOX_TOKEN = "YOUR_SANDBOX_TOKEN"  # Free from developer.tradier.com
TRADIER_SANDBOX_URL = "https://sandbox.tradier.com/v1"


def tradier_option_chain(symbol: str, expiration: str):
    """Get current option chain with IV and Greeks."""
    url = f"{TRADIER_SANDBOX_URL}/markets/options/chains"
    headers = {
        "Authorization": f"Bearer {TRADIER_SANDBOX_TOKEN}",
        "Accept": "application/json",
    }
    params = {
        "symbol": symbol,
        "expiration": expiration,
        "greeks": "true",  # Include IV and Greeks courtesy of ORATS
    }
    resp = requests.get(url, headers=headers, params=params)
    data = resp.json()
    # data['options']['option'] is a list of dicts with:
    #   symbol, description, exch, type, last, change, volume, open, high, low,
    #   close, bid, ask, strike, greeks (delta, gamma, theta, vega, rho, mid_iv, ...)
    return data


def tradier_historical_option(occ_symbol: str, start: str, end: str):
    """
    Get historical daily OHLCV for a specific option contract.

    occ_symbol: e.g. 'TQQQ260320C00060000'
    start/end: 'YYYY-MM-DD'
    """
    url = f"{TRADIER_SANDBOX_URL}/markets/history"
    headers = {
        "Authorization": f"Bearer {TRADIER_SANDBOX_TOKEN}",
        "Accept": "application/json",
    }
    params = {
        "symbol": occ_symbol,
        "interval": "daily",
        "start": start,
        "end": end,
    }
    resp = requests.get(url, headers=headers, params=params)
    data = resp.json()
    # data['history']['day'] is a list of {date, open, high, low, close, volume}
    return data


def tradier_option_expirations(symbol: str):
    """Get available option expiration dates for a symbol."""
    url = f"{TRADIER_SANDBOX_URL}/markets/options/expirations"
    headers = {
        "Authorization": f"Bearer {TRADIER_SANDBOX_TOKEN}",
        "Accept": "application/json",
    }
    params = {"symbol": symbol}
    resp = requests.get(url, headers=headers, params=params)
    return resp.json()


def build_occ_symbol(underlying: str, expiry_date: str, opt_type: str, strike: float) -> str:
    """
    Build OCC option symbol.
    underlying: 'TQQQ'
    expiry_date: '2026-03-20'
    opt_type: 'C' or 'P'
    strike: 60.0
    """
    from datetime import datetime
    dt = datetime.strptime(expiry_date, "%Y-%m-%d")
    date_part = dt.strftime("%y%m%d")
    # Strike price * 1000, zero-padded to 8 digits
    strike_part = f"{int(strike * 1000):08d}"
    # Underlying padded to 6 chars (left-justified, space padded — but usually just used as-is)
    return f"{underlying}{date_part}{opt_type.upper()}{strike_part}"


# Example workflow for Tradier:
# 1. Get expirations: tradier_option_expirations('TQQQ')
# 2. Get chain:       tradier_option_chain('TQQQ', '2026-03-20')
# 3. Get history:     tradier_historical_option('TQQQ260320C00060000', '2026-01-01', '2026-03-13')


# =============================================================================
# 4. POLYGON.IO — Historical options data (free tier very limited)
# =============================================================================
"""
Polygon.io has comprehensive options data going back to 2014.
FREE tier: 5 API calls/min, EOD data only, 2-year lookback.
Options data may require a PAID plan ($29/mo Stocks Starter or higher).

pip install polygon-api-client
"""

def polygon_option_history(api_key: str, option_ticker: str, start: str, end: str):
    """
    Get historical aggregate bars for an option contract.

    option_ticker format: O:TQQQ260320C00060000
    """
    from polygon import RESTClient

    client = RESTClient(api_key)
    # Get daily bars for an option contract
    aggs = client.get_aggs(
        ticker=option_ticker,
        multiplier=1,
        timespan="day",
        from_=start,
        to=end,
    )
    # Each agg has: open, high, low, close, volume, vwap, timestamp
    for agg in aggs:
        print(f"Date: {agg.timestamp}, O:{agg.open} H:{agg.high} L:{agg.low} C:{agg.close} V:{agg.volume}")
    return aggs


def polygon_option_contracts(api_key: str, underlying: str):
    """List available option contracts for an underlying."""
    from polygon import RESTClient

    client = RESTClient(api_key)
    contracts = client.list_options_contracts(
        underlying_ticker=underlying,
        expiration_date_gte="2026-01-01",
        expiration_date_lte="2026-03-31",
        limit=100,
    )
    for c in contracts:
        print(f"{c.ticker} | {c.expiration_date} | {c.strike_price} | {c.contract_type}")
    return contracts


# =============================================================================
# 5. CBOE — Volume data only (free), full data via DataShop (paid)
# =============================================================================
"""
CBOE Historical Data Download (free):
  https://www.cboe.com/us/options/market_statistics/historical_data/
  - Download historical options VOLUME by symbol, month, or year
  - Does NOT include pricing or IV data in the free download

CBOE DataShop (paid):
  https://datashop.cboe.com/
  - End-of-day option quotes with optional IV and Greeks
  - Tick-level trade data
  - Expensive for individual use

VERDICT: Free CBOE data is volume-only. Not useful for pricing/IV.
"""


# =============================================================================
# 6. FREE IV DATA — Option Strategist weekly summaries
# =============================================================================
"""
https://www.optionstrategist.com/calculators/free-volatility-data

Provides weekly snapshots of:
  - Current implied volatility
  - Historical volatility (20-day, 50-day, 100-day)
  - IV percentile

Free but only weekly updates, and you'd need to scrape or manually check.
May or may not cover leveraged ETFs like TNA/TQQQ.
"""


# =============================================================================
# 7. DIY: Calculate IV from historical underlying prices
# =============================================================================
"""
If you can't get historical IV directly, you can:
  1. Get historical underlying prices (easy, free via yfinance)
  2. Use a known option pricing model (Black-Scholes)
  3. Back-solve for IV given the option price you have

pip install py_vollib
"""

def calculate_iv_from_price(option_price: float, underlying_price: float,
                            strike: float, days_to_expiry: int,
                            risk_free_rate: float = 0.05,
                            option_type: str = 'c'):
    """
    Calculate implied volatility from an option's market price.
    Uses py_vollib (Black-Scholes).
    """
    from py_vollib.black_scholes.implied_volatility import implied_volatility
    import py_vollib.black_scholes as bs

    T = days_to_expiry / 365.0
    flag = option_type  # 'c' or 'p'

    try:
        iv = implied_volatility(option_price, underlying_price, strike, T, risk_free_rate, flag)
        print(f"Implied Volatility: {iv:.4f} ({iv*100:.2f}%)")
        return iv
    except Exception as e:
        print(f"IV calculation error: {e}")
        return None


def historical_realized_volatility(ticker: str, start: str, end: str, window: int = 20):
    """
    Calculate historical realized volatility from underlying prices.
    This is NOT implied volatility, but useful as a proxy.
    """
    import numpy as np

    tk = yf.Ticker(ticker)
    hist = tk.history(start=start, end=end)
    hist['log_return'] = np.log(hist['Close'] / hist['Close'].shift(1))
    hist['realized_vol'] = hist['log_return'].rolling(window=window).std() * np.sqrt(252)

    print(f"\nRealized Volatility for {ticker} ({window}-day window):")
    print(hist[['Close', 'realized_vol']].tail(20))
    return hist


# =============================================================================
# 8. PRACTICAL STRATEGY: Build your own dataset going forward
# =============================================================================
"""
Since free historical options chain snapshots don't exist, the pragmatic
approach is to start collecting daily snapshots now.
"""

def daily_options_snapshot(tickers: list, output_dir: str = "options_data"):
    """
    Save daily option chain snapshots to CSV files.
    Run this daily via cron to build your own historical dataset.
    """
    import os
    from datetime import datetime

    os.makedirs(output_dir, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")

    for symbol in tickers:
        tk = yf.Ticker(symbol)
        for exp in tk.options:
            chain = tk.option_chain(exp)
            for opt_type, df in [("calls", chain.calls), ("puts", chain.puts)]:
                df['snapshot_date'] = today
                df['underlying'] = symbol
                filename = f"{output_dir}/{symbol}_{exp}_{opt_type}_{today}.csv"
                df.to_csv(filename, index=False)
                print(f"Saved: {filename}")


# =============================================================================
# SUMMARY TABLE
# =============================================================================
"""
Source              | Free? | Historical Chains? | Historical Contract Prices? | IV Data?
--------------------|-------|--------------------|-----------------------------|----------
yfinance            | Yes   | NO                 | NO                          | Current only
yoptions            | Yes   | NO                 | YES (individual contracts)  | NO
Tradier Sandbox     | Yes   | NO (current only)  | YES (individual contracts)  | Current chains only
Polygon.io Free     | Yes*  | NO                 | YES* (may need paid plan)   | NO
CBOE Free Download  | Yes   | NO                 | NO (volume only)            | NO
CBOE DataShop       | No    | YES                | YES                         | YES
OptionMetrics       | No    | YES                | YES                         | YES
optionstrategist    | Yes   | NO                 | NO                          | Weekly summary
DIY (py_vollib)     | Yes   | N/A                | N/A                         | Calculate from prices

* Polygon free tier may not include options — check current plan details.

RECOMMENDATION for your use case (TNA/TQQQ, Jan-Mar 2026):
1. Sign up for Tradier sandbox (free, 30 seconds)
2. Use tradier_historical_option() to pull daily OHLCV for specific contracts
3. Use yfinance to get historical underlying prices
4. Use py_vollib to calculate IV from the option prices + underlying prices
5. Start saving daily snapshots with daily_options_snapshot() for future use
"""


if __name__ == "__main__":
    print("=== DEMO: yfinance current chain ===")
    # Uncomment to run:
    # yfinance_current_chain('TQQQ')

    print("\n=== DEMO: Historical realized volatility ===")
    # historical_realized_volatility('TQQQ', '2026-01-01', '2026-03-13')
    # historical_realized_volatility('TNA', '2026-01-01', '2026-03-13')

    print("\n=== DEMO: Tradier historical option ===")
    # occ = build_occ_symbol('TQQQ', '2026-03-20', 'C', 60.0)
    # print(f"OCC Symbol: {occ}")
    # tradier_historical_option(occ, '2026-01-01', '2026-03-13')

    print("\nSee code comments above for full usage instructions.")
