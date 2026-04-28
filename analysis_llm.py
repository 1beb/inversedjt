"""MTM analysis using LLM-derived signals.

In-sample:     2026-01-05 to 2026-03-12
Out-of-sample: 2026-03-13 to 2026-04-19
Full-period:   2026-01-05 to 2026-04-19
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from src.backtester import get_prices
from src.config import BET_FRACTION, STARTING_CAPITAL
from src.llm_signals import load_cache, signals_by_date
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
        "return": ret, "max_dd": max_dd, "worst_day": worst_day,
        "wins": wins, "losses": losses, "trades": wins + losses,
        "max_open": int(daily_curve["num_open_positions"].max()),
    }


def run_backtest_set(signals, label, price_start, price_end):
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
            daily.to_csv(f"data/trades/mtm_llm_{label}_{pair['long']}_{pair['inverse']}_{window}.csv")
    return pd.DataFrame(rows)


def print_table(df, period):
    for window in HOLD_WINDOWS:
        wdf = df[(df["period"] == period) & (df["window"] == window)].sort_values("return", ascending=False)
        if wdf.empty:
            continue
        print(f"\n{'=' * 80}")
        print(f"  {period.upper()} — {window.replace('_',' ').title()} Hold (LLM signals)")
        print(f"{'=' * 80}")
        print(f"  {'Pair':<12} {'Return':>8} {'MaxDD':>8} {'WorstDay':>9} {'W/L':>7} {'Trades':>7} {'MaxOpen':>8}")
        for _, r in wdf.iterrows():
            print(f"  {r['pair']:<12} {r['return']:>+7.1f}% {r['max_dd']:>+7.1f}% "
                  f"{r['worst_day']:>+8.1f}% {r['wins']:>2}W/{r['losses']:>2}L "
                  f"{r['trades']:>7} {r['max_open']:>8}")


def main():
    cache = load_cache()
    signals = signals_by_date(cache)
    is_signals = {d: s for d, s in signals.items() if d <= IS_CUTOFF}
    oos_signals = {d: s for d, s in signals.items() if OOS_START <= d <= OOS_END}

    print(f"LLM signals: {len(signals)} total")
    print(f"  In-sample (≤Mar 12): {len(is_signals)}")
    print(f"  OOS (Mar 13–Apr 19):  {len(oos_signals)}")

    price_start = "2025-12-01"
    price_end = "2026-05-31"

    all_results = []
    for label, sigs in [("in_sample", is_signals), ("oos", oos_signals), ("full", signals)]:
        print(f"\n>>> Backtesting {label} ({len(sigs)} signals)...")
        all_results.append(run_backtest_set(sigs, label, price_start, price_end))

    df = pd.concat(all_results, ignore_index=True)
    df.to_csv("data/trades/analysis_llm_summary.csv", index=False)

    for period in ["in_sample", "oos", "full"]:
        print_table(df, period)

    # Equity curves for 30-day hold
    fig, axes = plt.subplots(3, 1, figsize=(14, 12), sharex=False)
    for idx, period in enumerate(["in_sample", "oos", "full"]):
        for pair_key, pair in ETF_PAIRS.items():
            path = f"data/trades/mtm_llm_{period}_{pair['long']}_{pair['inverse']}_thirty_day.csv"
            try:
                curve = pd.read_csv(path, index_col="date", parse_dates=True)
            except FileNotFoundError:
                continue
            axes[idx].plot(curve.index, curve["total_value"], label=pair_key, linewidth=1)
        axes[idx].axhline(y=STARTING_CAPITAL, color="black", linestyle=":", alpha=0.3)
        axes[idx].set_title(f"{period} — 30-day Hold (LLM signals)")
        axes[idx].set_ylabel("Portfolio ($)")
        axes[idx].legend(fontsize=7, ncol=4)
        axes[idx].grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig("data/trades/mtm_llm_equity_curves.png", dpi=150)
    print("\nSaved chart: data/trades/mtm_llm_equity_curves.png")


if __name__ == "__main__":
    main()
