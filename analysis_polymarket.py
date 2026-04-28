"""Polymarket backtest: 3 selection strategies, 3 hold windows.

Approach A: hand-curated basket - trade ALL active markets on every signal day.
Approach B: LLM-matched per speech - per-day basket chosen by `claude -p`.
Approach C: topic-tagged - intersect speech topics with market topics.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

from src.claims import extract_signal
from src.config import BET_FRACTION, STARTING_CAPITAL
from src.polymarket import load_all_markets
from src.polymarket_backtester import run_polymarket_backtest


HOLD_WINDOWS = ["next_day", "end_of_week", "thirty_day"]
LLM_SCORES_PATH = Path("data/trades/llm_scores.json")
LLM_MATCH_CACHE = Path("data/polymarket/llm_market_matches.json")


def load_speeches() -> list[dict]:
    files = sorted(Path("data/speeches").glob("2026-*.json"))
    return [json.load(open(f)) for f in files]


def extract_signals(speeches: list[dict]) -> dict[str, str]:
    sigs: dict[str, str] = {}
    for s in speeches:
        sig = extract_signal(s["text"])
        if sig and s["date"] not in sigs:
            sigs[s["date"]] = sig
    return sigs


def speech_topics_by_date(speeches: list[dict]) -> dict[str, set[str]]:
    """Aggregate LLM-derived topics per speech-date."""
    if not LLM_SCORES_PATH.exists():
        return {}
    scores = json.loads(LLM_SCORES_PATH.read_text())
    by_date: dict[str, set[str]] = {}
    for rec in scores.values():
        date = rec["date"]
        topics = set(rec.get("topics", []))
        by_date.setdefault(date, set()).update(topics)
    return by_date


def stats(daily_curve: pd.DataFrame, trade_df: pd.DataFrame) -> dict:
    final = daily_curve["total_value"].iloc[-1]
    ret_pct = (final - STARTING_CAPITAL) / STARTING_CAPITAL * 100
    peak = daily_curve["total_value"].cummax()
    dd = ((daily_curve["total_value"] - peak) / peak * 100).min()
    daily_ret = daily_curve["total_value"].pct_change().dropna()
    worst = daily_ret.min() * 100 if len(daily_ret) else 0.0
    if len(trade_df):
        wins = int((trade_df["realized_pnl"] > 0).sum())
        losses = int((trade_df["realized_pnl"] <= 0).sum())
    else:
        wins = losses = 0
    return {
        "final": final,
        "return_pct": ret_pct,
        "max_dd": dd,
        "worst_day": worst,
        "wins": wins,
        "losses": losses,
        "trades": wins + losses,
        "max_open": int(daily_curve["num_open"].max()),
    }


# ---------- Selectors ----------

def selector_A(markets):
    """Hand-curated: all 29 markets every signal day (active filter happens in backtester)."""
    all_ids = list(markets.keys())
    def pick(day, signal):
        return all_ids
    return pick


def selector_C(markets, speech_topics: dict[str, set[str]]):
    """Topic-intersection: trade markets whose topics overlap that day's speech topics."""
    def pick(day, signal):
        date_str = day.strftime("%Y-%m-%d")
        day_topics = speech_topics.get(date_str, set())
        if not day_topics:
            return []
        return [
            mid for mid, m in markets.items()
            if set(m.topics) & day_topics
        ]
    return pick


def selector_B(markets, llm_matches: dict[str, list[str]]):
    """LLM-matched: per-date list of market ids picked by Claude."""
    def pick(day, signal):
        date_str = day.strftime("%Y-%m-%d")
        return llm_matches.get(date_str, [])
    return pick


# ---------- Approach B: build LLM matches ----------

def build_llm_matches(speeches: list[dict], signals: dict[str, str], markets) -> dict[str, list[str]]:
    """For each signal day, ask claude -p which markets the speech makes claims about."""
    import subprocess

    if LLM_MATCH_CACHE.exists():
        cache = json.loads(LLM_MATCH_CACHE.read_text())
    else:
        cache = {}

    market_list = "\n".join(
        f"- {mid}: {m.question}" for mid, m in markets.items()
    )

    rubric = """\
You analyze a Donald Trump speech transcript and decide which prediction-market
questions the speech is making BULLISH claims about (claims aligned with the
YES outcome).

You will be given a list of binary markets (YES/NO). Return a JSON list of the
ids of markets where the speech contains forward-looking, bullish-for-YES
claims by Trump (e.g. he says he will achieve, will sign, will end, will make,
is winning, is great, etc., on the topic the market asks about).

If a market is unrelated or only weakly mentioned, do not include it. If none
match, return an empty list. Output JSON ONLY, in the form {"market_ids": [...]}.
"""

    schema = {
        "type": "object",
        "properties": {
            "market_ids": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["market_ids"],
        "additionalProperties": False,
    }

    # Group speeches by date so one LLM call covers a date
    by_date: dict[str, list[dict]] = {}
    for s in speeches:
        if s["date"] in signals:
            by_date.setdefault(s["date"], []).append(s)

    for date, day_speeches in sorted(by_date.items()):
        if date in cache:
            continue
        # Combine all speech text for the day, capped
        combined = "\n\n--- NEXT SPEECH ---\n\n".join(
            f"Title: {s.get('title','')}\n{s['text'][:30000]}" for s in day_speeches
        )
        if len(combined) > 80000:
            combined = combined[:80000] + "\n[...truncated...]"

        prompt = (
            f"Date: {date}\n\nMARKETS:\n{market_list}\n\n"
            f"SPEECH(ES):\n{combined}\n\n"
            "Return matching market ids."
        )
        print(f"  LLM match for {date}...", end=" ", flush=True)
        try:
            r = subprocess.run(
                ["claude", "-p", "--model", "opus", "--tools", "",
                 "--no-session-persistence", "--output-format", "json",
                 "--system-prompt", rubric, "--json-schema", json.dumps(schema)],
                input=prompt, capture_output=True, text=True, timeout=300,
            )
            if r.returncode != 0:
                print(f"ERR: {r.stderr[:120]}")
                continue
            resp = json.loads(r.stdout)
            ids = (resp.get("structured_output") or {}).get("market_ids", [])
            ids = [i for i in ids if i in markets]
            cache[date] = ids
            LLM_MATCH_CACHE.parent.mkdir(parents=True, exist_ok=True)
            LLM_MATCH_CACHE.write_text(json.dumps(cache, indent=2))
            print(f"matched {len(ids)}")
        except Exception as e:
            print(f"ERR: {e}")
    return cache


# ---------- Main ----------

def run_strategy(name, selector, markets, signals):
    rows = []
    for window in HOLD_WINDOWS:
        for mode in ("inverse", "believe"):
            curve, trades = run_polymarket_backtest(
                markets, selector, signals, STARTING_CAPITAL, BET_FRACTION, window,
                mode=mode,
            )
            s = stats(curve, trades)
            s["approach"] = name
            s["window"] = window
            s["mode"] = mode
            rows.append(s)
            tag = f"{name}_{mode}_{window}"
            curve.to_csv(f"data/trades/poly_{tag}_curve.csv")
            if len(trades):
                trades.to_csv(f"data/trades/poly_{tag}_trades.csv", index=False)
    return rows


def print_grid(rows: list[dict]):
    df = pd.DataFrame(rows)
    for window in HOLD_WINDOWS:
        sub = df[df["window"] == window]
        # Pivot so each approach has inverse + believe + spread
        piv = sub.pivot(index="approach", columns="mode", values="return_pct")
        piv["spread"] = piv.get("inverse", 0) - piv.get("believe", 0)
        dd_inv = sub[sub["mode"] == "inverse"].set_index("approach")["max_dd"]
        wl_inv = sub[sub["mode"] == "inverse"].set_index("approach")[["wins", "losses", "trades"]]
        label = window.replace("_", " ").title()
        print(f"\n{'=' * 90}")
        print(f"  {label} Hold — Polymarket (Inverse / Believe / Spread)")
        print(f"{'=' * 90}")
        print(f"  {'Approach':<10} {'Inverse':>8} {'Believe':>8} {'Spread':>8} {'MaxDD':>8} {'W/L (inv)':>12} {'Trades':>7}")
        print(f"  {'-'*10} {'-'*8} {'-'*8} {'-'*8} {'-'*8} {'-'*12} {'-'*7}")
        for app in sorted(piv.index, key=lambda a: -piv.loc[a, "spread"]):
            row = piv.loc[app]
            wl = wl_inv.loc[app]
            print(f"  {app:<10} {row['inverse']:>+7.1f}% {row['believe']:>+7.1f}% {row['spread']:>+7.1f}% "
                  f"{dd_inv[app]:>+7.1f}% {int(wl['wins']):>4}W/{int(wl['losses']):>3}L {int(wl['trades']):>7}")


def main():
    speeches = load_speeches()
    signals = extract_signals(speeches)
    puts = sum(1 for v in signals.values() if v == "put")
    print(f"Loaded {len(speeches)} speeches, {len(signals)} signal days "
          f"({puts} put, {len(signals)-puts} call)")

    markets = load_all_markets()
    print(f"Loaded {len(markets)} Polymarket markets")

    if "--approach" in sys.argv:
        which = sys.argv[sys.argv.index("--approach") + 1]
    else:
        which = "ABC"

    rows = []
    if "A" in which:
        print("\n--- Approach A: hand-curated basket ---")
        rows += run_strategy("A", selector_A(markets), markets, signals)
    if "C" in which:
        print("\n--- Approach C: topic-tagged matching ---")
        topics = speech_topics_by_date(speeches)
        rows += run_strategy("C", selector_C(markets, topics), markets, signals)
    if "B" in which:
        print("\n--- Approach B: LLM-matched per speech ---")
        matches = build_llm_matches(speeches, signals, markets)
        rows += run_strategy("B", selector_B(markets, matches), markets, signals)

    print_grid(rows)
    pd.DataFrame(rows).to_csv("data/trades/polymarket_summary.csv", index=False)
    print("\nSummary saved to data/trades/polymarket_summary.csv")


if __name__ == "__main__":
    main()
