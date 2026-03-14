"""Run inverse Trump strategy using debit spreads to reduce IV cost.

Bear put spread on "put" signals, bull call spread on "call" signals.
Tests multiple spread widths to find the sweet spot.
"""
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from src.backtester import (
    get_prices, estimate_volatility, days_to_expiry, find_expiry_price,
    calculate_commission,
)
from src.claims import extract_signal
from src.config import BET_FRACTION, STARTING_CAPITAL, RISK_FREE_RATE
from src.options_pricer import calculate_spread_price, calculate_spread_pnl

TICKERS = {
    "SPY": {"name": "S&P 500", "iv": 0.21, "widths": [2, 5, 10]},
    "IWM": {"name": "Russell 2000", "iv": 0.30, "widths": [2, 5, 10]},
    "XLF": {"name": "Financials", "iv": 0.31, "widths": [1, 2, 5]},
    "TQQQ": {"name": "3x Nasdaq", "iv": 0.85, "widths": [2, 5, 10]},
    "TNA": {"name": "3x Russell", "iv": 1.07, "widths": [2, 5, 10]},
    "SPXL": {"name": "3x S&P", "iv": 0.78, "widths": [2, 5, 10]},
    "SMH": {"name": "Semiconductors", "iv": 0.50, "widths": [5, 10, 20]},
    "KRE": {"name": "Regional Banks", "iv": 0.45, "widths": [2, 5, 10]},
}

SPREAD_WIDTHS_DEFAULT = [2, 5, 10]


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


def run_spread_backtest(
    prices: pd.DataFrame,
    signals: dict[str, str],
    starting_capital: float,
    bet_fraction: float,
    iv: float,
    spread_width: float,
) -> pd.DataFrame:
    """Backtest using debit spreads instead of naked options."""
    vol = estimate_volatility(prices)

    portfolios = {
        "next_day": starting_capital,
        "end_of_week": starting_capital,
        "thirty_day": starting_capital,
    }
    trades = []

    for date_str, signal in sorted(signals.items()):
        trade_date = pd.Timestamp(date_str)

        if trade_date not in prices.index:
            future = prices.index[prices.index >= trade_date]
            if len(future) == 0:
                continue
            trade_date = future[0]

        spot = prices.loc[trade_date, "Open"]
        strike = round(spot)

        # Determine spread strikes
        if signal == "put":
            # Bear put spread: buy ATM put, sell OTM put
            K_long = strike
            K_short = strike - spread_width
            spread_type = "bear_put"
        else:
            # Bull call spread: buy ATM call, sell OTM call
            K_long = strike
            K_short = strike + spread_width
            spread_type = "bull_call"

        trade_row = {
            "date": date_str,
            "trade_date": trade_date,
            "signal": signal,
            "spot": spot,
            "K_long": K_long,
            "K_short": K_short,
            "spread_type": spread_type,
        }

        for window in ["next_day", "end_of_week", "thirty_day"]:
            dte = days_to_expiry(trade_date, window, prices)
            T = dte / 365

            net_debit = calculate_spread_price(
                S=spot, K_long=K_long, K_short=K_short,
                T=T, r=RISK_FREE_RATE, sigma=iv,
                spread_type=spread_type,
            )

            if net_debit <= 0:
                net_debit = 0.01  # floor

            budget = portfolios[window] * bet_fraction
            cost_per_contract = net_debit * 100
            num_contracts = max(1, int(budget / cost_per_contract))

            expiry_price = find_expiry_price(prices, trade_date, dte)
            if expiry_price is None:
                pnl = 0
            else:
                pnl = calculate_spread_pnl(
                    net_debit=net_debit,
                    spot_at_expiry=expiry_price,
                    K_long=K_long,
                    K_short=K_short,
                    spread_type=spread_type,
                    num_contracts=num_contracts,
                )

            # Commissions: 2 legs open + 2 legs close (if any value)
            open_comm = calculate_commission(num_contracts * 2)  # 2 legs
            close_comm = calculate_commission(num_contracts * 2) if pnl > -net_debit * 100 * num_contracts else 0
            commission = open_comm + close_comm

            net_pnl = pnl - commission
            portfolios[window] += net_pnl

            trade_row[f"net_debit_{window}"] = net_debit
            trade_row[f"num_contracts_{window}"] = num_contracts
            trade_row[f"pnl_{window}"] = net_pnl
            trade_row[f"commission_{window}"] = commission
            trade_row[f"portfolio_{window}"] = portfolios[window]

        trades.append(trade_row)

    return pd.DataFrame(trades)


def main():
    speeches = load_speeches()
    signals = extract_signals_from_speeches(speeches)
    puts = sum(1 for s in signals.values() if s == "put")
    print(f"Loaded {len(speeches)} speeches, {len(signals)} signal days ({puts} put / {len(signals)-puts} call)\n")

    results = []

    for ticker, cfg in TICKERS.items():
        name = cfg["name"]
        iv = cfg["iv"]
        widths = cfg["widths"]

        print(f"{ticker} ({name}, IV={iv*100:.0f}%):")
        try:
            prices = get_prices(ticker, "2026-01-01", "2026-12-31")
            if len(prices) < 10:
                print("  SKIP")
                continue
        except Exception as e:
            print(f"  ERROR: {e}")
            continue

        for width in widths:
            trades = run_spread_backtest(prices, signals, STARTING_CAPITAL, BET_FRACTION, iv, width)

            for window in ["next_day", "end_of_week", "thirty_day"]:
                port_col = f"portfolio_{window}"
                pnl_col = f"pnl_{window}"
                if port_col not in trades.columns:
                    continue

                final = trades[port_col].iloc[-1]
                ret = (final - STARTING_CAPITAL) / STARTING_CAPITAL * 100
                wins = (trades[pnl_col] > 0).sum()
                losses = (trades[pnl_col] < 0).sum()
                avg_debit = trades[f"net_debit_{window}"].mean()

                results.append({
                    "ticker": ticker,
                    "name": name,
                    "iv": f"{iv*100:.0f}%",
                    "width": f"${width}",
                    "window": window,
                    "return": ret,
                    "wins": wins,
                    "losses": losses,
                    "avg_debit": avg_debit,
                })

            print(f"  ${width} wide: next-day {results[-3]['return']:+.1f}%, eow {results[-2]['return']:+.1f}%, 30d {results[-1]['return']:+.1f}%")

    df = pd.DataFrame(results)
    df.to_csv("data/trades/spread_results.csv", index=False)

    # Print best results per window
    for window in ["next_day", "end_of_week", "thirty_day"]:
        wdf = df[df["window"] == window].sort_values("return", ascending=False)
        label = window.replace("_", " ").title()
        print(f"\n{'=' * 90}")
        print(f"  {label} — DEBIT SPREADS (reduced IV cost)")
        print(f"{'=' * 90}")
        print(f"  {'Ticker':<6} {'Name':<18} {'IV':>5} {'Width':>6} {'Return':>9} {'W/L':>8} {'Avg Debit':>10}")
        print(f"  {'-'*6} {'-'*18} {'-'*5} {'-'*6} {'-'*9} {'-'*8} {'-'*10}")
        for _, row in wdf.iterrows():
            print(f"  {row['ticker']:<6} {row['name']:<18} {row['iv']:>5} {row['width']:>6} {row['return']:>+8.1f}% {int(row['wins'])}W/{int(row['losses'])}L ${row['avg_debit']:>8.2f}")

    # Chart: best spread per ticker for 30-day
    fig, axes = plt.subplots(3, 1, figsize=(14, 12))
    for idx, window in enumerate(["next_day", "end_of_week", "thirty_day"]):
        wdf = df[df["window"] == window]
        # Pick best width per ticker
        best = wdf.loc[wdf.groupby("ticker")["return"].idxmax()].sort_values("return", ascending=True)
        label = window.replace("_", " ").title()

        y = range(len(best))
        colors = ["green" if r > 0 else "red" for r in best["return"]]
        axes[idx].barh(list(y), best["return"], color=colors, alpha=0.7)
        axes[idx].set_yticks(list(y))
        axes[idx].set_yticklabels([f"{row['ticker']} {row['width']} wide" for _, row in best.iterrows()])
        axes[idx].set_xlabel("Return (%)")
        axes[idx].set_title(f"{label} — Best Debit Spread per Ticker")
        axes[idx].axvline(x=0, color="black", linewidth=0.5)
        axes[idx].grid(True, alpha=0.3, axis="x")

    plt.tight_layout()
    plt.savefig("data/trades/spread_comparison.png", dpi=150)
    print(f"\nChart saved to data/trades/spread_comparison.png")


if __name__ == "__main__":
    main()
