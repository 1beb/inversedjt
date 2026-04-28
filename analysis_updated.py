"""Updated MTM analysis: full-period rerun through Apr 19, 2026 + out-of-sample slice.

In-sample:     2026-01-05 to 2026-03-12 (13 signals — original analysis)
Out-of-sample: 2026-03-13 to 2026-04-19 (new signals)
Full-period:   2026-01-05 to 2026-04-19 (in + OOS combined)
"""
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
    "XLF/SKF":   {"long": "XLF",  "inverse": "SKF"},
    "QQQ/SQQQ":  {"long": "QQQ",  "inverse": "SQQQ"},
    "IWM/TZA":   {"long": "IWM",  "inverse": "TZA"},
    "SPY/SH":    {"long": "SPY",  "inverse": "SH"},
    "SPY/SPXU":  {"long": "SPY",  "inverse": "SPXU"},
    "TNA/TZA":   {"long": "TNA",  "inverse": "TZA"},
    "TQQQ/SQQQ": {"long": "TQQQ", "inverse": "SQQQ"},
}

HOLD_WINDOWS = ["next_day", "end_of_week", "thirty_day"]

IS_CUTOFF = "2026-03-12"
OOS_START = "2026-03-13"
OOS_END = "2026-04-19"


def load_signals() -> dict[str, str]:
    signals = {}
    for f in sorted(Path("data/speeches").glob("2026-*.json")):
        with open(f) as fh:
            s = json.load(fh)
        sig = extract_signal(s["text"])
        if sig and s["date"] not in signals:
            signals[s["date"]] = sig
    return signals


def calc_stats(daily_curve: pd.DataFrame, trade_df: pd.DataFrame) -> dict:
    total_value = daily_curve["total_value"]
    final = total_value.iloc[-1]
    ret = (final - STARTING_CAPITAL) / STARTING_CAPITAL * 100

    peak = total_value.cummax()
    dd = (total_value - peak) / peak * 100
    max_dd = dd.min()

    daily_rets = total_value.pct_change().dropna()
    worst_day = daily_rets.min() * 100 if len(daily_rets) > 0 else 0

    if len(trade_df) > 0:
        wins = int((trade_df["realized_pnl"] > 0).sum())
        losses = int((trade_df["realized_pnl"] <= 0).sum())
    else:
        wins = losses = 0

    return {
        "return": ret,
        "max_dd": max_dd,
        "worst_day": worst_day,
        "wins": wins,
        "losses": losses,
        "trades": wins + losses,
        "max_open": int(daily_curve["num_open_positions"].max()),
    }


def run_backtest_set(signals: dict[str, str], label: str,
                     price_start: str, price_end: str) -> pd.DataFrame:
    rows = []
    for pair_key, pair in ETF_PAIRS.items():
        try:
            long_p = get_prices(pair["long"], price_start, price_end)
            inv_p = get_prices(pair["inverse"], price_start, price_end)
            if len(long_p) < 10 or len(inv_p) < 10:
                continue
        except Exception as e:
            print(f"[{label}] {pair_key} price err: {e}")
            continue

        for window in HOLD_WINDOWS:
            daily, trades = run_mtm_backtest(
                long_p, inv_p, signals, STARTING_CAPITAL, BET_FRACTION, window,
            )
            stats = calc_stats(daily, trades)
            stats.update({"pair": pair_key, "window": window, "period": label})
            rows.append(stats)
            daily.to_csv(f"data/trades/mtm_{label}_{pair['long']}_{pair['inverse']}_{window}.csv")
    return pd.DataFrame(rows)


def print_table(df: pd.DataFrame, period: str):
    for window in HOLD_WINDOWS:
        wdf = df[(df["period"] == period) & (df["window"] == window)].sort_values("return", ascending=False)
        if wdf.empty: continue
        print(f"\n{'=' * 80}")
        print(f"  {period.upper()} — {window.replace('_',' ').title()} Hold")
        print(f"{'=' * 80}")
        print(f"  {'Pair':<12} {'Return':>8} {'MaxDD':>8} {'WorstDay':>9} {'W/L':>7} {'Trades':>7} {'MaxOpen':>8}")
        for _, r in wdf.iterrows():
            print(f"  {r['pair']:<12} {r['return']:>+7.1f}% {r['max_dd']:>+7.1f}% "
                  f"{r['worst_day']:>+8.1f}% {r['wins']:>2}W/{r['losses']:>2}L "
                  f"{r['trades']:>7} {r['max_open']:>8}")


def main():
    signals = load_signals()
    is_signals = {d: s for d, s in signals.items() if d <= IS_CUTOFF}
    oos_signals = {d: s for d, s in signals.items() if OOS_START <= d <= OOS_END}

    print(f"Total signals: {len(signals)}")
    print(f"  In-sample (Jan 5 – Mar 12): {len(is_signals)}")
    print(f"  Out-of-sample (Mar 13 – Apr 19): {len(oos_signals)}")
    print(f"  Full-period (Jan 5 – Apr 19): {len(signals)}")

    # Fetch price data covering entire range (end buffer for 30-day hold resolution)
    price_start = "2025-12-01"
    price_end = "2026-05-31"

    all_results = []

    print("\n>>> Running IN-SAMPLE (for reference)...")
    all_results.append(run_backtest_set(is_signals, "in_sample", price_start, price_end))

    print(">>> Running OUT-OF-SAMPLE (new data only)...")
    all_results.append(run_backtest_set(oos_signals, "oos", price_start, price_end))

    print(">>> Running FULL-PERIOD (combined)...")
    all_results.append(run_backtest_set(signals, "full", price_start, price_end))

    df = pd.concat(all_results, ignore_index=True)
    df.to_csv("data/trades/analysis_updated_summary.csv", index=False)

    for period in ["in_sample", "oos", "full"]:
        print_table(df, period)

    # 30-day hold equity curves: side-by-side comparison chart
    fig, axes = plt.subplots(3, 1, figsize=(14, 12), sharex=False)
    for idx, period in enumerate(["in_sample", "oos", "full"]):
        for pair_key, pair in ETF_PAIRS.items():
            csv_path = f"data/trades/mtm_{period}_{pair['long']}_{pair['inverse']}_thirty_day.csv"
            try:
                curve = pd.read_csv(csv_path, index_col="date", parse_dates=True)
            except FileNotFoundError:
                continue
            axes[idx].plot(curve.index, curve["total_value"], label=pair_key, linewidth=1)
        axes[idx].axhline(y=STARTING_CAPITAL, color="black", linestyle=":", alpha=0.3)
        axes[idx].set_title(f"{period} — 30-day Hold — Daily Portfolio Value")
        axes[idx].set_ylabel("Portfolio ($)")
        axes[idx].legend(fontsize=7, ncol=4)
        axes[idx].grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig("data/trades/mtm_updated_equity_curves.png", dpi=150)
    print("\nSaved chart: data/trades/mtm_updated_equity_curves.png")


if __name__ == "__main__":
    main()
