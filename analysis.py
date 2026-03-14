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
    # Match files like 2026-01-05_slug.json, exclude listing.json
    existing = sorted(f for f in speech_dir.glob("2026-*.json"))

    if existing:
        print(f"Found {len(existing)} cached speeches")
        speeches = []
        for f in existing:
            with open(f) as fh:
                speeches.append(json.load(fh))
        return speeches

    print("No cached speeches found. Run scrape_transcripts.py first.")
    sys.exit(1)


def extract_signals(speeches: list[dict], believe: bool = False) -> dict[str, str]:
    """Extract trade signals from speeches.

    If believe=True, flip signals: trust Trump's claims instead of betting against them.
    """
    flip = {"put": "call", "call": "put"}
    signals = {}
    for speech in speeches:
        signal = extract_signal(speech["text"])
        if signal:
            if believe:
                signal = flip[signal]
            date = speech["date"]
            # Only one trade per day (first speech wins)
            if date not in signals:
                signals[date] = signal
                print(f"  {date}: {signal} (from: {speech.get('title', 'unknown')})")
    return signals


def print_summary(trades: pd.DataFrame, label: str = "INVERSE TRUMP"):
    """Print summary statistics."""
    print("\n" + "=" * 70)
    print(f"{label} OPTIONS STRATEGY - RESULTS")
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

        # Commissions
        comm_col = f"commission_{window}"
        total_commissions = trades[comm_col].sum() if comm_col in trades.columns else 0

        window_label = window.replace("_", " ").title()
        print(f"--- {window_label} Expiry ---")
        print(f"  Final portfolio: ${final_portfolio:,.0f}")
        print(f"  Total return:    {total_return:+.1f}%")
        print(f"  Win rate:        {win_rate:.0f}% ({wins}W / {losses}L / {flat}F)")
        print(f"  Max drawdown:    {max_dd:.1f}%")
        print(f"  Best trade:      ${trades[pnl_col].max():,.0f}")
        print(f"  Worst trade:     ${trades[pnl_col].min():,.0f}")
        print(f"  Total commissions: ${total_commissions:,.0f}")
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


def plot_comparison(inverse_trades: pd.DataFrame, believe_trades: pd.DataFrame, spy_prices: pd.DataFrame):
    """Generate comparison chart of both strategies."""
    fig, axes = plt.subplots(2, 1, figsize=(12, 8))

    for trades, style, prefix in [
        (inverse_trades, "-", "Inverse"),
        (believe_trades, "--", "Believe"),
    ]:
        for window, color, label in [
            ("next_day", "red", "Next-Day"),
            ("end_of_week", "blue", "End-of-Week"),
            ("thirty_day", "green", "30-Day"),
        ]:
            col = f"portfolio_{window}"
            if col in trades.columns:
                values = pd.concat([
                    pd.Series([STARTING_CAPITAL], index=[trades["trade_date"].iloc[0]]),
                    trades.set_index("trade_date")[col],
                ])
                axes[0].plot(values.index, values.values, color=color, linestyle=style,
                           label=f"{prefix} {label}", marker="o", markersize=2)

    spy_start = spy_prices["Close"].iloc[0]
    spy_baseline = (spy_prices["Close"] / spy_start) * STARTING_CAPITAL
    axes[0].plot(spy_baseline.index, spy_baseline.values, color="gray", linestyle=":", label="SPY Buy & Hold", alpha=0.7)
    axes[0].axhline(y=STARTING_CAPITAL, color="black", linestyle=":", alpha=0.3)
    axes[0].set_title("Inverse Trump (solid) vs Believe Trump (dashed) vs SPY")
    axes[0].set_ylabel("Portfolio Value ($)")
    axes[0].legend(fontsize=7, ncol=3)
    axes[0].grid(True, alpha=0.3)

    # Bar chart comparing final returns
    windows = ["next_day", "end_of_week", "thirty_day"]
    labels = ["Next-Day", "End-of-Week", "30-Day"]
    inverse_returns = [(inverse_trades[f"portfolio_{w}"].iloc[-1] - STARTING_CAPITAL) / STARTING_CAPITAL * 100 for w in windows]
    believe_returns = [(believe_trades[f"portfolio_{w}"].iloc[-1] - STARTING_CAPITAL) / STARTING_CAPITAL * 100 for w in windows]

    x = range(len(labels))
    width = 0.35
    axes[1].bar([i - width/2 for i in x], inverse_returns, width, label="Inverse Trump", color="steelblue")
    axes[1].bar([i + width/2 for i in x], believe_returns, width, label="Believe Trump", color="coral")
    axes[1].set_xticks(list(x))
    axes[1].set_xticklabels(labels)
    axes[1].set_ylabel("Total Return (%)")
    axes[1].set_title("Total Return Comparison")
    axes[1].legend()
    axes[1].grid(True, alpha=0.3, axis="y")
    axes[1].axhline(y=0, color="black", linewidth=0.5)

    plt.tight_layout()
    plt.savefig("data/trades/comparison.png", dpi=150)
    print("Comparison chart saved to data/trades/comparison.png")


def main():
    # 1. Get speeches
    speeches = load_or_scrape_speeches()
    print(f"\nLoaded {len(speeches)} speeches")

    # 2. Get SPY prices
    print("\nFetching SPY price data...")
    spy_prices = get_spy_prices("2026-01-01", "2026-12-31")
    print(f"Got {len(spy_prices)} trading days of SPY data")

    # 3. Inverse strategy (bet against Trump)
    print("\n--- INVERSE STRATEGY (bet against claims) ---")
    print("Extracting trade signals...")
    inverse_signals = extract_signals(speeches, believe=False)
    print(f"{len(inverse_signals)} trading days identified")

    inverse_trades = run_backtest(spy_prices, inverse_signals, STARTING_CAPITAL, BET_FRACTION)
    inverse_trades.to_csv("data/trades/trade_log_inverse.csv", index=False)
    print_summary(inverse_trades, label="INVERSE TRUMP")

    # 4. Believe strategy (trust Trump's claims)
    print("\n--- BELIEVE STRATEGY (trust claims) ---")
    print("Extracting trade signals...")
    believe_signals = extract_signals(speeches, believe=True)
    print(f"{len(believe_signals)} trading days identified")

    believe_trades = run_backtest(spy_prices, believe_signals, STARTING_CAPITAL, BET_FRACTION)
    believe_trades.to_csv("data/trades/trade_log_believe.csv", index=False)
    print_summary(believe_trades, label="BELIEVE TRUMP")

    # 5. Charts
    plot_results(inverse_trades, spy_prices)
    plot_comparison(inverse_trades, believe_trades, spy_prices)


if __name__ == "__main__":
    main()
