"""Run inverse Trump strategy using direct ETF buy/sell instead of options.

On each signal day:
- Bullish claim -> short the ETF (or buy inverse)
- Bearish claim -> buy the ETF
Hold for 1 day, end of week, or 30 days, then close.
Bet 10% of portfolio per trade.
"""
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from src.backtester import get_prices, estimate_volatility, days_to_expiry, find_expiry_price
from src.claims import extract_signal
from src.config import BET_FRACTION, STARTING_CAPITAL, COMMISSION_BASE

TICKERS = {
    "SPY": "S&P 500",
    "IWM": "Russell 2000 (Small Caps)",
    "XLF": "Financials",
    "XLE": "Energy",
    "XLI": "Industrials",
    "SMH": "Semiconductors",
    "KRE": "Regional Banks",
    "XHB": "Homebuilders",
    "EEM": "Emerging Markets",
    "TQQQ": "3x Nasdaq",
    "SPXL": "3x S&P 500",
    "TNA": "3x Russell 2000",
}

# Questrade stock/ETF commission
STOCK_COMMISSION = 4.95  # per trade, min $4.95


def load_speeches() -> list[dict]:
    speech_dir = Path("data/speeches")
    existing = sorted(f for f in speech_dir.glob("2026-*.json"))
    if not existing:
        print("No cached speeches found.")
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


def run_direct_backtest(
    prices: pd.DataFrame,
    signals: dict[str, str],
    starting_capital: float,
    bet_fraction: float,
) -> pd.DataFrame:
    """Direct buy/sell backtest across 3 hold windows."""
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

        entry_price = prices.loc[trade_date, "Open"]

        trade_row = {
            "date": date_str,
            "trade_date": trade_date,
            "signal": signal,
            "entry_price": entry_price,
        }

        for window in ["next_day", "end_of_week", "thirty_day"]:
            dte = days_to_expiry(trade_date, window, prices)
            exit_price = find_expiry_price(prices, trade_date, dte)

            if exit_price is None:
                pnl = 0
                pct_move = 0
            else:
                pct_move = (exit_price - entry_price) / entry_price

                # "put" signal = we think market goes down = short position
                # "call" signal = we think market goes up = long position
                if signal == "put":
                    direction = -1  # short
                else:
                    direction = 1  # long

                position_size = portfolios[window] * bet_fraction
                pnl = position_size * pct_move * direction

            # Commissions: buy + sell
            commission = STOCK_COMMISSION * 2
            net_pnl = pnl - commission
            portfolios[window] += net_pnl

            trade_row[f"exit_price_{window}"] = exit_price
            trade_row[f"pct_move_{window}"] = pct_move * 100
            trade_row[f"pnl_{window}"] = net_pnl
            trade_row[f"commission_{window}"] = commission
            trade_row[f"portfolio_{window}"] = portfolios[window]

        trades.append(trade_row)

    return pd.DataFrame(trades)


def main():
    speeches = load_speeches()
    print(f"Loaded {len(speeches)} speeches")

    inverse_signals = extract_signals_from_speeches(speeches, believe=False)
    believe_signals = extract_signals_from_speeches(speeches, believe=True)
    print(f"{len(inverse_signals)} signal days\n")

    results = []

    for ticker, name in TICKERS.items():
        print(f"  {ticker} ({name})...", end=" ", flush=True)
        try:
            prices = get_prices(ticker, "2026-01-01", "2026-12-31")
            if len(prices) < 10:
                print(f"SKIP")
                continue
        except Exception as e:
            print(f"ERROR: {e}")
            continue

        inverse_trades = run_direct_backtest(prices, inverse_signals, STARTING_CAPITAL, BET_FRACTION)
        believe_trades = run_direct_backtest(prices, believe_signals, STARTING_CAPITAL, BET_FRACTION)

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
    df.to_csv("data/trades/direct_results.csv", index=False)

    for window in ["next_day", "end_of_week", "thirty_day"]:
        wdf = df[df["window"] == window].sort_values("inverse_return", ascending=False)
        label = window.replace("_", " ").title()
        print(f"\n{'=' * 85}")
        print(f"  {label} Hold — DIRECT BUY/SELL (no options)")
        print(f"{'=' * 85}")
        print(f"  {'Ticker':<6} {'Name':<25} {'Inverse':>10} {'Believe':>10} {'Spread':>10} {'W/L':>8}")
        print(f"  {'-'*6} {'-'*25} {'-'*10} {'-'*10} {'-'*10} {'-'*8}")
        for _, row in wdf.iterrows():
            print(f"  {row['ticker']:<6} {row['name']:<25} {row['inverse_return']:>+9.1f}% {row['believe_return']:>+9.1f}% {row['spread']:>+9.1f}% {int(row['inverse_wins'])}W/{int(row['inverse_losses'])}L")

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
        axes[idx].set_yticklabels([f"{row['ticker']}" for _, row in wdf.iterrows()])
        axes[idx].set_xlabel("Return (%)")
        axes[idx].set_title(f"{label} Hold — Direct Buy/Sell")
        axes[idx].axvline(x=0, color="black", linewidth=0.5)
        axes[idx].legend(loc="lower right")
        axes[idx].grid(True, alpha=0.3, axis="x")

    plt.tight_layout()
    plt.savefig("data/trades/direct_comparison.png", dpi=150)
    print(f"\nChart saved to data/trades/direct_comparison.png")
    print(f"Data saved to data/trades/direct_results.csv")


if __name__ == "__main__":
    main()
