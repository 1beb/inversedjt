"""Run inverse Trump strategy using inverse ETFs instead of short selling.

When signal = "put" (bearish on market), buy the inverse ETF.
When signal = "call" (bullish on market), buy the regular ETF.
No short selling, no borrowing fees.
"""
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from src.backtester import get_prices, days_to_expiry, find_expiry_price
from src.claims import extract_signal
from src.config import BET_FRACTION, STARTING_CAPITAL

# Pairs: when signal is "put", buy the inverse ETF; when "call", buy the regular ETF
ETF_PAIRS = {
    "SPY/SH": {"long": "SPY", "inverse": "SH", "name": "S&P 500 / Short S&P"},
    "SPY/SPXU": {"long": "SPY", "inverse": "SPXU", "name": "S&P 500 / 3x Inv S&P"},
    "QQQ/SQQQ": {"long": "QQQ", "inverse": "SQQQ", "name": "Nasdaq / 3x Inv Nasdaq"},
    "IWM/TZA": {"long": "IWM", "inverse": "TZA", "name": "Russell 2000 / 3x Inv Russell"},
    "IWM/RWM": {"long": "IWM", "inverse": "RWM", "name": "Russell 2000 / Inv Russell"},
    "XLF/SKF": {"long": "XLF", "inverse": "SKF", "name": "Financials / 2x Inv Financials"},
    "XLE/ERY": {"long": "XLE", "inverse": "ERY", "name": "Energy / 2x Inv Energy"},
    "SMH/SOXS": {"long": "SMH", "inverse": "SOXS", "name": "Semiconductors / 3x Inv Semis"},
    # Also test leveraged long + inverse pairs
    "TQQQ/SQQQ": {"long": "TQQQ", "inverse": "SQQQ", "name": "3x Nasdaq / 3x Inv Nasdaq"},
    "TNA/TZA": {"long": "TNA", "inverse": "TZA", "name": "3x Russell / 3x Inv Russell"},
    "SPXL/SPXU": {"long": "SPXL", "inverse": "SPXU", "name": "3x S&P / 3x Inv S&P"},
}

STOCK_COMMISSION = 4.95


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


def run_inverse_etf_backtest(
    long_prices: pd.DataFrame,
    inverse_prices: pd.DataFrame,
    signals: dict[str, str],
    starting_capital: float,
    bet_fraction: float,
) -> pd.DataFrame:
    """Buy inverse ETF on put signals, buy regular ETF on call signals."""
    portfolios = {
        "next_day": starting_capital,
        "end_of_week": starting_capital,
        "thirty_day": starting_capital,
    }
    trades = []

    for date_str, signal in sorted(signals.items()):
        trade_date = pd.Timestamp(date_str)

        # Use whichever ETF matches the signal
        if signal == "put":
            prices = inverse_prices  # bearish -> buy inverse ETF
        else:
            prices = long_prices  # bullish -> buy regular ETF

        if trade_date not in prices.index:
            future = prices.index[prices.index >= trade_date]
            if len(future) == 0:
                continue
            trade_date = future[0]

        entry_price = prices.loc[trade_date, "Open"]

        trade_row = {
            "date": date_str,
            "trade_date": trade_date,
            "signal": signal,
            "etf_direction": "inverse" if signal == "put" else "long",
            "entry_price": entry_price,
        }

        for window in ["next_day", "end_of_week", "thirty_day"]:
            dte = days_to_expiry(trade_date, window, prices)
            exit_price = find_expiry_price(prices, trade_date, dte)

            if exit_price is None:
                pnl = 0
            else:
                # Always long — we buy the ETF and sell later
                pct_return = (exit_price - entry_price) / entry_price
                position_size = portfolios[window] * bet_fraction
                pnl = position_size * pct_return

            commission = STOCK_COMMISSION * 2  # buy + sell
            net_pnl = pnl - commission
            portfolios[window] += net_pnl

            trade_row[f"exit_price_{window}"] = exit_price
            trade_row[f"pnl_{window}"] = net_pnl
            trade_row[f"commission_{window}"] = commission
            trade_row[f"portfolio_{window}"] = portfolios[window]

        trades.append(trade_row)

    return pd.DataFrame(trades)


def main():
    speeches = load_speeches()
    print(f"Loaded {len(speeches)} speeches")

    signals = extract_signals_from_speeches(speeches)
    # Count signal types
    puts = sum(1 for s in signals.values() if s == "put")
    calls = sum(1 for s in signals.values() if s == "call")
    print(f"{len(signals)} signal days ({puts} put / {calls} call)")
    print(f"Since {puts}/{len(signals)} signals are puts, we're mostly buying inverse ETFs\n")

    results = []

    for pair_key, pair in ETF_PAIRS.items():
        print(f"  {pair_key} ({pair['name']})...", end=" ", flush=True)
        try:
            long_prices = get_prices(pair["long"], "2026-01-01", "2026-12-31")
            inv_prices = get_prices(pair["inverse"], "2026-01-01", "2026-12-31")
            if len(long_prices) < 10 or len(inv_prices) < 10:
                print("SKIP (insufficient data)")
                continue
        except Exception as e:
            print(f"ERROR: {e}")
            continue

        trades = run_inverse_etf_backtest(long_prices, inv_prices, signals, STARTING_CAPITAL, BET_FRACTION)

        for window in ["next_day", "end_of_week", "thirty_day"]:
            port_col = f"portfolio_{window}"
            pnl_col = f"pnl_{window}"

            if port_col not in trades.columns:
                continue

            final = trades[port_col].iloc[-1]
            ret = (final - STARTING_CAPITAL) / STARTING_CAPITAL * 100
            wins = (trades[pnl_col] > 0).sum()
            losses = (trades[pnl_col] < 0).sum()
            total_comm = trades[f"commission_{window}"].sum()

            results.append({
                "pair": pair_key,
                "name": pair["name"],
                "long_etf": pair["long"],
                "inverse_etf": pair["inverse"],
                "window": window,
                "return": ret,
                "final": final,
                "wins": wins,
                "losses": losses,
                "commissions": total_comm,
            })

        print("done")

    df = pd.DataFrame(results)
    df.to_csv("data/trades/inverse_etf_results.csv", index=False)

    for window in ["next_day", "end_of_week", "thirty_day"]:
        wdf = df[df["window"] == window].sort_values("return", ascending=False)
        label = window.replace("_", " ").title()
        print(f"\n{'=' * 80}")
        print(f"  {label} Hold — INVERSE ETF STRATEGY (buy only, no shorting)")
        print(f"{'=' * 80}")
        print(f"  {'Pair':<14} {'Name':<32} {'Return':>9} {'W/L':>8} {'Comm':>8}")
        print(f"  {'-'*14} {'-'*32} {'-'*9} {'-'*8} {'-'*8}")
        for _, row in wdf.iterrows():
            print(f"  {row['pair']:<14} {row['name']:<32} {row['return']:>+8.1f}% {int(row['wins'])}W/{int(row['losses'])}L ${row['commissions']:>5.0f}")

    # Chart
    fig, axes = plt.subplots(3, 1, figsize=(14, 12))
    for idx, window in enumerate(["next_day", "end_of_week", "thirty_day"]):
        wdf = df[df["window"] == window].sort_values("return", ascending=True)
        label = window.replace("_", " ").title()
        y = range(len(wdf))
        colors = ["green" if r > 0 else "red" for r in wdf["return"]]
        axes[idx].barh(list(y), wdf["return"], color=colors, alpha=0.7)
        axes[idx].set_yticks(list(y))
        axes[idx].set_yticklabels([f"{row['pair']}" for _, row in wdf.iterrows()])
        axes[idx].set_xlabel("Return (%)")
        axes[idx].set_title(f"{label} Hold — Inverse ETF (Buy Only)")
        axes[idx].axvline(x=0, color="black", linewidth=0.5)
        axes[idx].grid(True, alpha=0.3, axis="x")

    plt.tight_layout()
    plt.savefig("data/trades/inverse_etf_comparison.png", dpi=150)
    print(f"\nChart saved to data/trades/inverse_etf_comparison.png")


if __name__ == "__main__":
    main()
