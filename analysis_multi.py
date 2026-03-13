"""Run inverse Trump strategy across multiple ETFs and compare results."""
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

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
    print(f"{len(inverse_signals)} signal days\n")

    results = []

    for ticker, name in TICKERS.items():
        print(f"Fetching {ticker} ({name})...", end=" ", flush=True)
        try:
            prices = get_prices(ticker, "2026-01-01", "2026-12-31")
            if len(prices) < 10:
                print(f"SKIP (only {len(prices)} days)")
                continue
        except Exception as e:
            print(f"ERROR: {e}")
            continue

        inverse_trades = run_backtest(prices, inverse_signals, STARTING_CAPITAL, BET_FRACTION)
        believe_trades = run_backtest(prices, believe_signals, STARTING_CAPITAL, BET_FRACTION)

        for window in ["next_day", "end_of_week", "thirty_day"]:
            port_col = f"portfolio_{window}"
            pnl_col = f"pnl_{window}"

            if port_col not in inverse_trades.columns:
                continue

            inv_final = inverse_trades[port_col].iloc[-1]
            bel_final = believe_trades[port_col].iloc[-1]
            inv_return = (inv_final - STARTING_CAPITAL) / STARTING_CAPITAL * 100
            bel_return = (bel_final - STARTING_CAPITAL) / STARTING_CAPITAL * 100

            inv_wins = (inverse_trades[pnl_col] > 0).sum()
            inv_losses = (inverse_trades[pnl_col] < 0).sum()

            results.append({
                "ticker": ticker,
                "name": name,
                "window": window,
                "inverse_return": inv_return,
                "inverse_final": inv_final,
                "inverse_wins": inv_wins,
                "inverse_losses": inv_losses,
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
        print(f"\n{'=' * 80}")
        print(f"  {label} Expiry")
        print(f"{'=' * 80}")
        print(f"  {'Ticker':<8} {'Name':<28} {'Inverse':>10} {'Believe':>10} {'Spread':>10} {'W/L':>8}")
        print(f"  {'-'*8} {'-'*28} {'-'*10} {'-'*10} {'-'*10} {'-'*8}")
        for _, row in wdf.iterrows():
            print(f"  {row['ticker']:<8} {row['name']:<28} {row['inverse_return']:>+9.1f}% {row['believe_return']:>+9.1f}% {row['spread']:>+9.1f}% {int(row['inverse_wins'])}W/{int(row['inverse_losses'])}L")

    # Chart: comparison bar chart for next-day expiry
    fig, axes = plt.subplots(3, 1, figsize=(14, 12))

    for idx, window in enumerate(["next_day", "end_of_week", "thirty_day"]):
        wdf = df[df["window"] == window].sort_values("inverse_return", ascending=True)
        label = window.replace("_", " ").title()

        y = range(len(wdf))
        height = 0.35

        axes[idx].barh([i + height/2 for i in y], wdf["inverse_return"], height, label="Inverse Trump", color="steelblue")
        axes[idx].barh([i - height/2 for i in y], wdf["believe_return"], height, label="Believe Trump", color="coral")
        axes[idx].set_yticks(list(y))
        axes[idx].set_yticklabels([f"{row['ticker']}" for _, row in wdf.iterrows()])
        axes[idx].set_xlabel("Return (%)")
        axes[idx].set_title(f"{label} Expiry")
        axes[idx].axvline(x=0, color="black", linewidth=0.5)
        axes[idx].legend(loc="lower right")
        axes[idx].grid(True, alpha=0.3, axis="x")

    plt.tight_layout()
    plt.savefig("data/trades/multi_ticker_comparison.png", dpi=150)
    print(f"\nChart saved to data/trades/multi_ticker_comparison.png")
    print(f"Data saved to data/trades/multi_ticker_results.csv")


if __name__ == "__main__":
    main()
