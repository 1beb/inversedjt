"""Apply the identified winning pattern to the full Jan-Apr 2026 window.

Pattern:
- Use LLM-derived signal days (bullishness >= 2, salience >= 3) — extends
  coverage through April vs the keyword extractor.
- Approach B: LLM-matched markets per signal day.
- Refinement: only buy NO when entry price < 0.50 (market disagrees with
  Trump's claim → contrarian upside).
- Topic restriction: trump-calls, ukraine-ceasefire, greenland, tariffs.
- 30-day hold, forced exit at resolution.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from src.config import BET_FRACTION, STARTING_CAPITAL
from src.llm_signals import signals_by_date
from src.polymarket import load_all_markets
from src.polymarket_backtester import run_polymarket_backtest


WINNING_TOPICS = {"trump-calls", "ukraine-ceasefire", "greenland", "tariffs"}
ENTRY_PRICE_MAX = 0.50
HOLD = "thirty_day"


def load_speeches() -> list[dict]:
    return [json.load(open(f)) for f in sorted(Path("data/speeches").glob("2026-*.json"))]


def get_llm_signals() -> dict[str, str]:
    scores = json.loads(Path("data/trades/llm_scores.json").read_text())
    return signals_by_date(scores, bull_threshold=2, salience_threshold=3)


def build_llm_matches_for_signals(speeches, signals, markets) -> dict[str, list[str]]:
    """Per signal day, use claude -p to pick markets the speeches make bullish claims about.
    Reuses cache where available; only calls for new dates."""
    import subprocess

    cache_path = Path("data/polymarket/llm_market_matches.json")
    cache = json.loads(cache_path.read_text()) if cache_path.exists() else {}

    market_list = "\n".join(f"- {mid}: {m.question}" for mid, m in markets.items())
    rubric = """\
You analyze a Donald Trump speech transcript and decide which prediction-market
questions the speech is making BULLISH claims about (claims aligned with the
YES outcome).

Return a JSON list of the ids of markets where the speech contains
forward-looking, bullish-for-YES claims by Trump (e.g. he says he will achieve,
will sign, will end, will make, is winning, on the topic the market asks about).

If a market is unrelated or only weakly mentioned, do not include it. Output
JSON ONLY, in the form {"market_ids": [...]}.
"""
    schema = {"type": "object", "properties": {"market_ids": {"type": "array", "items": {"type": "string"}}}, "required": ["market_ids"], "additionalProperties": False}

    by_date: dict[str, list[dict]] = {}
    for s in speeches:
        if s["date"] in signals:
            by_date.setdefault(s["date"], []).append(s)

    for date, day_speeches in sorted(by_date.items()):
        if date in cache:
            continue
        combined = "\n\n--- NEXT SPEECH ---\n\n".join(
            f"Title: {s.get('title','')}\n{s['text'][:30000]}" for s in day_speeches
        )
        if len(combined) > 80000:
            combined = combined[:80000] + "\n[...truncated...]"
        prompt = f"Date: {date}\n\nMARKETS:\n{market_list}\n\nSPEECH(ES):\n{combined}\n\nReturn matching market ids."
        print(f"  LLM match for {date}...", end=" ", flush=True)
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
        cache_path.write_text(json.dumps(cache, indent=2))
        print(f"matched {len(ids)}")
    return cache


def selector_factory(matches):
    def pick(day, signal):
        return matches.get(day.strftime("%Y-%m-%d"), [])
    return pick


def main():
    speeches = load_speeches()
    signals = get_llm_signals()
    print(f"LLM signal days: {len(signals)} ({sorted(signals)})")

    markets = load_all_markets()
    matches = build_llm_matches_for_signals(speeches, signals, markets)

    # Run the unfiltered LLM-matched 30-day strategy (extended signals)
    curve, trades = run_polymarket_backtest(
        markets, selector_factory(matches), signals,
        STARTING_CAPITAL, BET_FRACTION, HOLD,
        calendar_start="2025-12-15", calendar_end="2026-05-31",
        mode="inverse",
    )
    if len(trades):
        trades["return_pct"] = (trades.exit_price - trades.entry_price) / trades.entry_price * 100

    # Save
    curve.to_csv("data/trades/poly_pattern_curve.csv")
    if len(trades):
        trades.to_csv("data/trades/poly_pattern_trades.csv", index=False)

    print(f"\n=== Full LLM-matched B (30-day, Jan-Apr) ===")
    final = curve.total_value.iloc[-1]
    ret = (final - STARTING_CAPITAL) / STARTING_CAPITAL * 100
    peak = curve.total_value.cummax()
    dd = ((curve.total_value - peak) / peak * 100).min()
    print(f"  Trades: {len(trades)}, Total P&L: ${trades.realized_pnl.sum():,.0f}")
    print(f"  Final equity: ${final:,.0f} ({ret:+.1f}%), Max DD: {dd:+.1f}%")

    # Apply refined pattern filter
    if len(trades):
        refined = trades[(trades.entry_price < ENTRY_PRICE_MAX) & (trades.topic.isin(WINNING_TOPICS))]
        print(f"\n=== Refined pattern (entry NO < {ENTRY_PRICE_MAX} + winning topics) ===")
        print(f"  Trades: {len(refined)}, Total P&L: ${refined.realized_pnl.sum():,.0f}")
        if len(refined):
            print(f"  Win rate: {(refined.realized_pnl>0).mean()*100:.0f}%")
            print(refined[["open_date","topic","question","entry_price","exit_price","return_pct","realized_pnl"]].sort_values("realized_pnl",ascending=False).to_string(index=False))


if __name__ == "__main__":
    main()
