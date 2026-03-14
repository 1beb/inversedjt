"""Run inverse Trump strategy across multiple ETFs and compare results.

Uses real implied volatility from current options chains where available,
falling back to historical realized volatility otherwise.
"""
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import yfinance as yf

from src.backtester import get_prices, run_backtest
from src.claims import extract_signal
from src.config import BET_FRACTION, STARTING_CAPITAL

TICKERS = {
    # Broad market
    "SPY": "S&P 500",
    "IWM": "Russell 2000 (Small Caps)",
    # Sectors
    "XLF": "Financials",
    "XLE": "Energy",
    "XLI": "Industrials",
    "SMH": "Semiconductors",
    "KRE": "Regional Banks",
    "XHB": "Homebuilders",
    # International
    "EEM": "Emerging Markets",
    # Leveraged
    "TQQQ": "3x Nasdaq",
    "SPXL": "3x S&P 500",
    "TNA": "3x Russell 2000",
}


def get_current_iv(ticker_symbol: str) -> float | None:
    """Fetch current ATM implied volatility from yfinance options chain."""
    try:
        t = yf.Ticker(ticker_symbol)
        price = t.info.get("regularMarketPrice")
        if not price:
            return None
        exps = t.options
        if not exps:
            return None
        # Use nearest expiry for short-term IV
        chain = t.option_chain(exps[0])
        puts = chain.puts
        if puts.empty:
            return None
        # Find ATM put
        atm = puts.iloc[(puts["strike"] - price).abs().argsort()[:1]]
        iv = atm["impliedVolatility"].values[0]
        if iv and iv > 0:
            return float(iv)
    except Exception:
        pass
    return None


def load_speeches() -> list[dict]:
    speech_dir = Path("data/speeches")
    existing = sorted(f for f in speech_dir.glob("2026-*.json"))
    if not existing:
        print("No cached speeches found. Run scrape_transcripts.py first.")
        sys.exit(1)
    speeches = []
    for f in existing:
        with open(f) as fh:
            speeches.append(json.load(fh))
    return speeches


def extract_signals_from_speeches(speeches: list[dict], believe: bool = False) -> dict[str, str]:
    flip = {"put": "call", "call": "put"}
    signals = {}
    for speech in speeches:
        signal = extract_signal(speech["text"])
        if signal:
            if believe:
                signal = flip[signal]
            date = speech["date"]
            if date not in signals:
                signals[date] = signal
    return signals


def main():
    speeches = load_speeches()
    print(f"Loaded {len(speeches)} speeches")

    inverse_signals = extract_signals_from_speeches(speeches, believe=False)
    believe_signals = extract_signals_from_speeches(speeches, believe=True)
    print(f"{len(inverse_signals)} signal days")

    # Fetch implied volatilities
    print("\nFetching implied volatilities from options chains...")
    iv_map = {}
    for ticker in TICKERS:
        iv = get_current_iv(ticker)
        iv_map[ticker] = iv
        if iv:
            print(f"  {ticker}: IV = {iv*100:.0f}%")
        else:
            print(f"  {ticker}: IV unavailable, using historical vol")

    print()
    results = []

    for ticker, name in TICKERS.items():
        iv = iv_map.get(ticker)
        iv_label = f"IV={iv*100:.0f}%" if iv else "hist vol"
        print(f"Fetching {ticker} ({name}, {iv_label})...", end=" ", flush=True)
        try:
            prices = get_prices(ticker, "2026-01-01", "2026-12-31")
            if len(prices) < 10:
                print(f"SKIP (only {len(prices)} days)")
                continue
        except Exception as e:
            print(f"ERROR: {e}")
            continue

        inverse_trades = run_backtest(prices, inverse_signals, STARTING_CAPITAL, BET_FRACTION, iv_override=iv)
        believe_trades = run_backtest(prices, believe_signals, STARTING_CAPITAL, BET_FRACTION, iv_override=iv)

        for window in ["next_day", "end_of_week", "thirty_day"]:
            port_col = f"portfolio_{window}"
            pnl_col = f"pnl_{window}"
            comm_col = f"commission_{window}"

            if port_col not in inverse_trades.columns:
                continue

            inv_final = inverse_trades[port_col].iloc[-1]
            bel_final = believe_trades[port_col].iloc[-1]
            inv_return = (inv_final - STARTING_CAPITAL) / STARTING_CAPITAL * 100
            bel_return = (bel_final - STARTING_CAPITAL) / STARTING_CAPITAL * 100

            inv_wins = (inverse_trades[pnl_col] > 0).sum()
            inv_losses = (inverse_trades[pnl_col] < 0).sum()
            inv_commissions = inverse_trades[comm_col].sum() if comm_col in inverse_trades.columns else 0

            results.append({
                "ticker": ticker,
                "name": name,
                "iv_used": f"{iv*100:.0f}%" if iv else "hist",
                "window": window,
                "inverse_return": inv_return,
                "inverse_final": inv_final,
                "inverse_wins": inv_wins,
                "inverse_losses": inv_losses,
                "inverse_commissions": inv_commissions,
                "believe_return": bel_return,
                "believe_final": bel_final,
                "spread": inv_return - bel_return,
            })

        print("done")

    df = pd.DataFrame(results)
    df.to_csv("data/trades/multi_ticker_results.csv", index=False)

    # Print results table
    for window in ["next_day", "end_of_week", "thirty_day"]:
        wdf = df[df["window"] == window].sort_values("inverse_return", ascending=False)
        label = window.replace("_", " ").title()
        print(f"\n{'=' * 90}")
        print(f"  {label} Expiry (using real implied volatility for pricing)")
        print(f"{'=' * 90}")
        print(f"  {'Ticker':<6} {'Name':<25} {'IV':>6} {'Inverse':>10} {'Believe':>10} {'Spread':>10} {'W/L':>8}")
        print(f"  {'-'*6} {'-'*25} {'-'*6} {'-'*10} {'-'*10} {'-'*10} {'-'*8}")
        for _, row in wdf.iterrows():
            print(f"  {row['ticker']:<6} {row['name']:<25} {row['iv_used']:>6} {row['inverse_return']:>+9.1f}% {row['believe_return']:>+9.1f}% {row['spread']:>+9.1f}% {int(row['inverse_wins'])}W/{int(row['inverse_losses'])}L")

    # Chart
    fig, axes = plt.subplots(3, 1, figsize=(14, 12))

    for idx, window in enumerate(["next_day", "end_of_week", "thirty_day"]):
        wdf = df[df["window"] == window].sort_values("inverse_return", ascending=True)
        label = window.replace("_", " ").title()

        y = range(len(wdf))
        height = 0.35

        axes[idx].barh([i + height/2 for i in y], wdf["inverse_return"], height, label="Inverse Trump", color="steelblue")
        axes[idx].barh([i - height/2 for i in y], wdf["believe_return"], height, label="Believe Trump", color="coral")
        axes[idx].set_yticks(list(y))
        axes[idx].set_yticklabels([f"{row['ticker']} ({row['iv_used']})" for _, row in wdf.iterrows()])
        axes[idx].set_xlabel("Return (%)")
        axes[idx].set_title(f"{label} Expiry (Real IV Pricing)")
        axes[idx].axvline(x=0, color="black", linewidth=0.5)
        axes[idx].legend(loc="lower right")
        axes[idx].grid(True, alpha=0.3, axis="x")

    plt.tight_layout()
    plt.savefig("data/trades/multi_ticker_comparison.png", dpi=150)
    print(f"\nChart saved to data/trades/multi_ticker_comparison.png")
    print(f"Data saved to data/trades/multi_ticker_results.csv")


if __name__ == "__main__":
    main()
