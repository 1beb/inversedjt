"""LLM-based signal extraction for Trump speeches.

Uses the local Claude Code CLI (`claude -p`) so we ride on existing login
credentials instead of requiring ANTHROPIC_API_KEY.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path


CACHE_PATH = Path("data/trades/llm_scores.json")
MODEL = "opus"
MAX_CHARS = 80_000  # cap to keep within 200k context after harness overhead

RUBRIC = """\
You analyze transcripts of Donald Trump speaking and produce structured
scores for a contrarian trading strategy. The strategy bets AGAINST Trump's
bullish claims: strongly bullish Trump speeches trigger short/inverse
trades, bearish Trump speeches (rare) trigger long trades.

For each transcript return JSON with:

- bullishness: integer -5 to +5.
  +5 = extreme, multi-front optimism about US prospects
       (economy greatest ever, stock market at highs, jobs pouring in,
        inflation crushed, oil prices falling, tariff wins, trade deals,
        military/geopolitical triumphalism with implied favorable economic
        consequences).
  +3 = several clear bullish claims across economy / markets / geopolitics.
  +1 = a passing bullish reference.
   0 = no market-relevant claims, ceremonial, or roughly balanced.
  -1..-5 = bearish claims (economy in trouble, recession warning). Rare.

  CRITICAL: Iran / military / foreign-policy triumphalism COUNTS as
  bullish when Trump ties it to US economic dominance, falling oil prices,
  trade wins, or broad US success. Do not require the word "economy".

- salience: integer 0-10. How much of the speech is forward claims a
  trader could bet against? 10 = entire speech is bullish predictions.
  0 = purely ceremonial, no forward claims.

- topics: list of short tags from this set only:
  {economy, stock_market, jobs, unemployment, inflation, oil, energy,
   tariffs, trade, gdp, military, geopolitics, deals, immigration, taxes,
   regulation}.

- rationale: one sentence naming the two or three loudest contrarian-worthy
  quotes or themes.

Be consistent across transcripts. Do not fabricate. If a speech has zero
market-relevant content, return bullishness 0 and salience 0.
Output JSON ONLY."""

SCHEMA = {
    "type": "object",
    "properties": {
        "bullishness": {"type": "integer", "minimum": -5, "maximum": 5},
        "salience":    {"type": "integer", "minimum": 0,  "maximum": 10},
        "topics":      {"type": "array", "items": {"type": "string"}},
        "rationale":   {"type": "string"},
    },
    "required": ["bullishness", "salience", "topics", "rationale"],
    "additionalProperties": False,
}


def score_speech_via_cli(date: str, title: str, text: str, timeout: int = 300) -> dict:
    """Score a single speech by subprocessing `claude -p`."""
    if len(text) > MAX_CHARS:
        text = text[:MAX_CHARS] + "\n[...truncated...]"

    user_input = f"Date: {date}\nTitle: {title}\n\nTranscript:\n{text}\n\nScore this speech using the rubric."

    result = subprocess.run(
        [
            "claude", "-p",
            "--model", MODEL,
            "--tools", "",
            "--no-session-persistence",
            "--output-format", "json",
            "--system-prompt", RUBRIC,
            "--json-schema", json.dumps(SCHEMA),
        ],
        input=user_input,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if result.returncode != 0:
        raise RuntimeError(f"claude CLI failed: {result.stderr[:500]}")

    resp = json.loads(result.stdout)
    if resp.get("is_error"):
        raise RuntimeError(f"claude returned error: {resp.get('result')}")
    out = resp.get("structured_output")
    if not out:
        raise RuntimeError(f"no structured_output in response: {str(resp)[:400]}")
    return {
        "score": out,
        "cost_usd": resp.get("total_cost_usd", 0.0),
    }


def load_cache() -> dict:
    if CACHE_PATH.exists():
        return json.loads(CACHE_PATH.read_text())
    return {}


def save_cache(cache: dict) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache, indent=2))


def score_all_speeches(speeches_dir: str = "data/speeches", force: bool = False) -> dict:
    """Score every 2026 speech, caching results. Returns {key: record_dict}."""
    cache = {} if force else load_cache()
    total_cost = sum(v.get("cost_usd", 0.0) for v in cache.values())

    speech_files = sorted(Path(speeches_dir).glob("2026-*.json"))
    print(f"Scoring {len(speech_files)} speeches (cache has {len(cache)} already)")

    for sf in speech_files:
        with open(sf) as f:
            s = json.load(f)
        key = sf.stem
        if key in cache and not force:
            continue
        try:
            result = score_speech_via_cli(s["date"], s.get("title", ""), s["text"])
        except Exception as e:
            print(f"  ERR {key}: {e}")
            continue
        score = result["score"]
        total_cost += result["cost_usd"]
        cache[key] = {
            "date": s["date"],
            "title": s.get("title", ""),
            "cost_usd": result["cost_usd"],
            **score,
        }
        save_cache(cache)
        print(f"  {s['date']} | bull={score['bullishness']:+d} sal={score['salience']:2d} "
              f"${result['cost_usd']:.3f} | {key[:50]}")

    print(f"\nTotal cost across all cached scores: ${total_cost:.2f}")
    return cache


def signal_from_score(score: dict, bull_threshold: int = 2, salience_threshold: int = 3) -> str | None:
    """Map a score record to put / call / None.

    Bet AGAINST Trump: bullish → put (inverse); bearish → call (long).
    Require a minimum salience so we don't trade on ceremonial speeches.
    """
    b = score["bullishness"]
    s = score["salience"]
    if s < salience_threshold:
        return None
    if b >= bull_threshold:
        return "put"
    if b <= -bull_threshold:
        return "call"
    return None


def signals_by_date(cache: dict, bull_threshold: int = 2, salience_threshold: int = 3) -> dict[str, str]:
    """Aggregate scores to {date: signal}. Resolves same-day conflicts by
    keeping the stronger-salience signal."""
    by_date: dict[str, dict] = {}
    for rec in cache.values():
        sig = signal_from_score(rec, bull_threshold, salience_threshold)
        if sig is None:
            continue
        prev = by_date.get(rec["date"])
        if prev is None or rec["salience"] > prev["salience"]:
            by_date[rec["date"]] = {"signal": sig, "salience": rec["salience"]}
    return {d: v["signal"] for d, v in by_date.items()}


if __name__ == "__main__":
    cache = score_all_speeches()
    print(f"\nScored {len(cache)} speeches. Cache at {CACHE_PATH}")
    signals = signals_by_date(cache)
    puts = sum(1 for v in signals.values() if v == "put")
    calls = sum(1 for v in signals.values() if v == "call")
    print(f"Signals: {len(signals)} ({puts} put, {calls} call)")
    for d, s in sorted(signals.items()):
        print(f"  {d} | {s}")
