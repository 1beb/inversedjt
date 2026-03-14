"""Mark-to-market analysis using inverse ETF pairs with daily portfolio tracking."""
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from src.backtester import get_prices
from src.claims import extract_signal
from src.config import BET_FRACTION, STARTING_CAPITAL
from src.mtm_backtester import run_mtm_backtest

ETF_PAIRS = {
    "XLF/SKF": {"long": "XLF", "inverse": "SKF", "name": "Financials / 2x Inv"},
    "QQQ/SQQQ": {"long": "QQQ", "inverse": "SQQQ", "name": "Nasdaq / 3x Inv"},
    "IWM/TZA": {"long": "IWM", "inverse": "TZA", "name": "Russell / 3x Inv"},
    "SPY/SH": {"long": "SPY", "inverse": "SH", "name": "S&P 500 / Inv"},
    "SPY/SPXU": {"long": "SPY", "inverse": "SPXU", "name": "S&P 500 / 3x Inv"},
    "TNA/TZA": {"long": "TNA", "inverse": "TZA", "name": "3x Russell / 3x Inv"},
    "TQQQ/SQQQ": {"long": "TQQQ", "inverse": "SQQQ", "name": "3x Nasdaq / 3x Inv"},
}

HOLD_WINDOWS = ["next_day", "end_of_week", "thirty_day"]


def load_speeches() -> list[dict]:
    speech_dir = Path("data/speeches")
    existing = sorted(f for f in speech_dir.glob("2026-*.json"))
    if not existing:
        print("No cached speeches found.")
        sys.exit(1)
    return [json.load(open(f)) for f in existing]


def extract_signals_from_speeches(speeches: list[dict]) -> dict[str, str]:
    signals = {}
    for speech in speeches:
        signal = extract_signal(speech["text"])
        if signal:
            date = speech["date"]
            if date not in signals:
                signals[date] = signal
    return signals


def calculate_stats(daily_curve: pd.DataFrame, trade_df: pd.DataFrame) -> dict:
    """Calculate summary statistics from MTM results."""
    total_value = daily_curve["total_value"]
    final = total_value.iloc[-1]
    ret = (final - STARTING_CAPITAL) / STARTING_CAPITAL * 100

    # Max drawdown from daily curve
    peak = total_value.cummax()
    drawdown = (total_value - peak) / peak * 100
    max_dd = drawdown.min()

    # Worst single-day drop
    daily_returns = total_value.pct_change().dropna()
    worst_day = daily_returns.min() * 100 if len(daily_returns) > 0 else 0

    # Trade stats
    if len(trade_df) > 0:
        wins = (trade_df["realized_pnl"] > 0).sum()
        losses = (trade_df["realized_pnl"] <= 0).sum()
        total_commission = trade_df["commission"].sum()
        avg_pnl = trade_df["realized_pnl"].mean()
    else:
        wins = losses = 0
        total_commission = avg_pnl = 0

    # Max concurrent positions
    max_positions = daily_curve["num_open_positions"].max()

    return {
        "final": final,
        "return": ret,
        "max_dd": max_dd,
        "worst_day": worst_day,
        "wins": wins,
        "losses": losses,
        "total_trades": wins + losses,
        "total_commission": total_commission,
        "avg_pnl": avg_pnl,
        "max_concurrent": max_positions,
    }


def main():
    speeches = load_speeches()
    signals = extract_signals_from_speeches(speeches)
    puts = sum(1 for s in signals.values() if s == "put")
    print(f"Loaded {len(speeches)} speeches, {len(signals)} signal days ({puts} put / {len(signals)-puts} call)\n")

    all_results = []

    for pair_key, pair in ETF_PAIRS.items():
        print(f"Fetching {pair_key}...", end=" ", flush=True)
        try:
            long_prices = get_prices(pair["long"], "2025-12-01", "2026-04-30")
            inv_prices = get_prices(pair["inverse"], "2025-12-01", "2026-04-30")
            if len(long_prices) < 10 or len(inv_prices) < 10:
                print("SKIP")
                continue
        except Exception as e:
            print(f"ERROR: {e}")
            continue
        print("ok")

        for window in HOLD_WINDOWS:
            daily_curve, trade_df = run_mtm_backtest(
                long_prices, inv_prices, signals,
                STARTING_CAPITAL, BET_FRACTION, window,
            )

            stats = calculate_stats(daily_curve, trade_df)
            stats["pair"] = pair_key
            stats["name"] = pair["name"]
            stats["window"] = window
            all_results.append(stats)

            # Save daily curves for the best candidates
            daily_curve.to_csv(f"data/trades/mtm_{pair['long']}_{pair['inverse']}_{window}.csv")

    # Print results
    df = pd.DataFrame(all_results)

    for window in HOLD_WINDOWS:
        wdf = df[df["window"] == window].sort_values("return", ascending=False)
        label = window.replace("_", " ").title()
        print(f"\n{'=' * 95}")
        print(f"  {label} Hold — MARK-TO-MARKET (daily valuation, realistic sizing)")
        print(f"{'=' * 95}")
        print(f"  {'Pair':<14} {'Name':<22} {'Return':>8} {'MaxDD':>8} {'WorstDay':>9} {'W/L':>7} {'MaxOpen':>8} {'Comm':>7}")
        print(f"  {'-'*14} {'-'*22} {'-'*8} {'-'*8} {'-'*9} {'-'*7} {'-'*8} {'-'*7}")
        for _, row in wdf.iterrows():
            print(f"  {row['pair']:<14} {row['name']:<22} {row['return']:>+7.1f}% {row['max_dd']:>+7.1f}% {row['worst_day']:>+8.1f}% {int(row['wins'])}W/{int(row['losses'])}L {int(row['max_concurrent']):>7} ${row['total_commission']:>5.0f}")

    # Plot daily equity curves for 30-day hold (most interesting)
    fig, axes = plt.subplots(3, 1, figsize=(14, 12), sharex=True)

    for idx, window in enumerate(HOLD_WINDOWS):
        label = window.replace("_", " ").title()

        for pair_key, pair in ETF_PAIRS.items():
            csv_path = f"data/trades/mtm_{pair['long']}_{pair['inverse']}_{window}.csv"
            try:
                curve = pd.read_csv(csv_path, index_col="date", parse_dates=True)
            except FileNotFoundError:
                continue
            axes[idx].plot(curve.index, curve["total_value"], label=pair_key, linewidth=1)

        axes[idx].axhline(y=STARTING_CAPITAL, color="black", linestyle=":", alpha=0.3)
        axes[idx].set_title(f"{label} Hold — Daily Portfolio Value")
        axes[idx].set_ylabel("Portfolio Value ($)")
        axes[idx].legend(fontsize=7, ncol=4)
        axes[idx].grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig("data/trades/mtm_equity_curves.png", dpi=150)
    print(f"\nEquity curves saved to data/trades/mtm_equity_curves.png")

    # Plot drawdown chart for 30-day
    fig, axes = plt.subplots(3, 1, figsize=(14, 12), sharex=True)

    for idx, window in enumerate(HOLD_WINDOWS):
        label = window.replace("_", " ").title()

        for pair_key, pair in ETF_PAIRS.items():
            csv_path = f"data/trades/mtm_{pair['long']}_{pair['inverse']}_{window}.csv"
            try:
                curve = pd.read_csv(csv_path, index_col="date", parse_dates=True)
            except FileNotFoundError:
                continue
            peak = curve["total_value"].cummax()
            dd = (curve["total_value"] - peak) / peak * 100
            axes[idx].plot(curve.index, dd, label=pair_key, linewidth=1)

        axes[idx].axhline(y=0, color="black", linewidth=0.5)
        axes[idx].set_title(f"{label} Hold — Drawdown from Peak")
        axes[idx].set_ylabel("Drawdown (%)")
        axes[idx].legend(fontsize=7, ncol=4)
        axes[idx].grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig("data/trades/mtm_drawdowns.png", dpi=150)
    print(f"Drawdown chart saved to data/trades/mtm_drawdowns.png")


if __name__ == "__main__":
    main()
