# analysis.py
"""Main runner: scrape, extract signals, backtest, and produce analysis."""
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # non-interactive backend for headless environments
import matplotlib.pyplot as plt
import pandas as pd

from src.backtester import get_spy_prices, run_backtest
from src.claims import extract_signal
from src.config import BET_FRACTION, STARTING_CAPITAL
from src.scraper import scrape_all


def load_or_scrape_speeches() -> list[dict]:
    """Load cached speeches or scrape fresh."""
    speech_dir = Path("data/speeches")
    existing = sorted(speech_dir.glob("*.json"))

    if existing:
        print(f"Found {len(existing)} cached speeches")
        speeches = []
        for f in existing:
            with open(f) as fh:
                speeches.append(json.load(fh))
        return speeches

    print("Scraping speeches from Rev.com...")
    return scrape_all(2026)


def extract_signals(speeches: list[dict]) -> dict[str, str]:
    """Extract trade signals from speeches."""
    signals = {}
    for speech in speeches:
        signal = extract_signal(speech["text"])
        if signal:
            date = speech["date"]
            # Only one trade per day (first speech wins)
            if date not in signals:
                signals[date] = signal
                print(f"  {date}: {signal} (from: {speech.get('title', 'unknown')})")
    return signals


def print_summary(trades: pd.DataFrame):
    """Print summary statistics."""
    print("\n" + "=" * 70)
    print("INVERSE TRUMP OPTIONS STRATEGY - RESULTS")
    print("=" * 70)
    print(f"Total signal days: {len(trades)}")
    print(f"Starting capital: ${STARTING_CAPITAL:,.0f}")
    print()

    for window in ["next_day", "end_of_week", "thirty_day"]:
        pnl_col = f"pnl_{window}"
        port_col = f"portfolio_{window}"

        if pnl_col not in trades.columns:
            continue

        total_pnl = trades[pnl_col].sum()
        wins = (trades[pnl_col] > 0).sum()
        losses = (trades[pnl_col] < 0).sum()
        flat = (trades[pnl_col] == 0).sum()
        win_rate = wins / max(wins + losses, 1) * 100
        final_portfolio = trades[port_col].iloc[-1] if len(trades) > 0 else STARTING_CAPITAL
        total_return = (final_portfolio - STARTING_CAPITAL) / STARTING_CAPITAL * 100

        # Max drawdown
        portfolio_series = pd.concat([
            pd.Series([STARTING_CAPITAL]),
            trades[port_col].reset_index(drop=True),
        ])
        peak = portfolio_series.cummax()
        drawdown = (portfolio_series - peak) / peak * 100
        max_dd = drawdown.min()

        label = window.replace("_", " ").title()
        print(f"--- {label} Expiry ---")
        print(f"  Final portfolio: ${final_portfolio:,.0f}")
        print(f"  Total return:    {total_return:+.1f}%")
        print(f"  Win rate:        {win_rate:.0f}% ({wins}W / {losses}L / {flat}F)")
        print(f"  Max drawdown:    {max_dd:.1f}%")
        print(f"  Best trade:      ${trades[pnl_col].max():,.0f}")
        print(f"  Worst trade:     ${trades[pnl_col].min():,.0f}")
        print()


def plot_results(trades: pd.DataFrame, spy_prices: pd.DataFrame):
    """Generate portfolio value chart."""
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))

    # Portfolio value over time
    for window, color, label in [
        ("next_day", "red", "Next-Day Expiry"),
        ("end_of_week", "blue", "End-of-Week Expiry"),
        ("thirty_day", "green", "30-Day Expiry"),
    ]:
        col = f"portfolio_{window}"
        if col in trades.columns:
            values = pd.concat([
                pd.Series([STARTING_CAPITAL], index=[trades["trade_date"].iloc[0]]),
                trades.set_index("trade_date")[col],
            ])
            ax1.plot(values.index, values.values, color=color, label=label, marker="o", markersize=3)

    # SPY buy-and-hold baseline
    spy_start = spy_prices["Close"].iloc[0]
    spy_baseline = (spy_prices["Close"] / spy_start) * STARTING_CAPITAL
    ax1.plot(spy_baseline.index, spy_baseline.values, color="gray", linestyle="--", label="SPY Buy & Hold", alpha=0.7)

    ax1.axhline(y=STARTING_CAPITAL, color="black", linestyle=":", alpha=0.3)
    ax1.set_title("Inverse Trump Strategy vs SPY Buy & Hold")
    ax1.set_ylabel("Portfolio Value ($)")
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    # Trade P&L distribution
    for window, color, label in [
        ("next_day", "red", "Next-Day"),
        ("end_of_week", "blue", "End-of-Week"),
        ("thirty_day", "green", "30-Day"),
    ]:
        col = f"pnl_{window}"
        if col in trades.columns:
            ax2.hist(trades[col], bins=20, alpha=0.5, color=color, label=label)

    ax2.axvline(x=0, color="black", linestyle="-", alpha=0.5)
    ax2.set_title("Trade P&L Distribution")
    ax2.set_xlabel("P&L ($)")
    ax2.set_ylabel("Count")
    ax2.legend()
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig("data/trades/results.png", dpi=150)
    print("Chart saved to data/trades/results.png")


def main():
    # 1. Get speeches
    speeches = load_or_scrape_speeches()
    print(f"\nLoaded {len(speeches)} speeches")

    # 2. Extract signals
    print("\nExtracting trade signals...")
    signals = extract_signals(speeches)
    print(f"\n{len(signals)} trading days identified")

    if not signals:
        print("No trade signals found. Check speech data and claim categories.")
        sys.exit(1)

    # 3. Get SPY prices
    print("\nFetching SPY price data...")
    spy_prices = get_spy_prices("2026-01-01", "2026-12-31")
    print(f"Got {len(spy_prices)} trading days of SPY data")

    # 4. Run backtest
    print("\nRunning backtest...")
    trades = run_backtest(spy_prices, signals, STARTING_CAPITAL, BET_FRACTION)

    # 5. Save trade log
    trades.to_csv("data/trades/trade_log.csv", index=False)
    print("Trade log saved to data/trades/trade_log.csv")

    # 6. Print summary
    print_summary(trades)

    # 7. Plot
    plot_results(trades, spy_prices)


if __name__ == "__main__":
    main()
