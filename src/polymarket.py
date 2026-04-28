"""Polymarket data loading: markets, prices, topic tags."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd


PRICES_DIR = Path("data/polymarket/prices")

# Topic tags per market (matches the speech-topic taxonomy in llm_signals.py).
# Keyed by market topic-cluster (from shortlist.json).
CLUSTER_TOPICS: dict[str, list[str]] = {
    "ukraine-ceasefire": ["military", "geopolitics", "deals"],
    "trump-calls":       ["geopolitics", "deals"],
    "greenland":         ["geopolitics"],
    "iran-strike":       ["military", "geopolitics", "oil", "energy"],
    "iran-regime":       ["military", "geopolitics", "oil", "energy"],
    "mexico-ops":        ["military", "immigration", "geopolitics"],
    "venezuela":         ["military", "geopolitics", "oil", "energy"],
    "crypto":            ["economy", "regulation"],
    "fed-cut":           ["economy", "inflation"],
    "tariffs":           ["tariffs", "trade"],
    "oil-low":           ["oil", "energy"],
}


@dataclass
class Market:
    id: str
    slug: str
    question: str
    topic: str          # cluster, e.g. "ukraine-ceasefire"
    topics: list[str]   # speech-taxonomy topics this market relates to
    start_date: pd.Timestamp
    end_date: pd.Timestamp
    yes_series: pd.Series
    no_series: pd.Series

    def is_active_on(self, date: pd.Timestamp) -> bool:
        return self.start_date <= date <= self.end_date

    def has_quote_on_or_before(self, date: pd.Timestamp, side: str) -> bool:
        s = self.yes_series if side == "YES" else self.no_series
        return (s.index <= date).any()

    def price_on(self, date: pd.Timestamp, side: str) -> float | None:
        """Last quote on or before `date`. Returns None if no prior quote."""
        s = self.yes_series if side == "YES" else self.no_series
        prior = s[s.index <= date]
        if len(prior) == 0:
            return None
        return float(prior.iloc[-1])

    def resolution_price(self, side: str) -> float:
        """Last observed price after resolution."""
        s = self.yes_series if side == "YES" else self.no_series
        return float(s.iloc[-1]) if len(s) > 0 else 0.5

    def is_resolved_by(self, date: pd.Timestamp) -> bool:
        return date >= self.end_date


def _series_from_history(history: list[dict]) -> pd.Series:
    """Convert [{t, p}] to a pandas Series indexed by date (last-of-day price)."""
    if not history:
        return pd.Series(dtype=float)
    df = pd.DataFrame(history)
    df["date"] = pd.to_datetime(df["t"], unit="s").dt.normalize()
    # If multiple ticks per day, take the last one
    df = df.sort_values("t").drop_duplicates("date", keep="last")
    return df.set_index("date")["p"].astype(float).sort_index()


def load_market(path: Path) -> Market | None:
    raw = json.loads(path.read_text())
    yes_s = _series_from_history(raw["yes_history"])
    no_s = _series_from_history(raw["no_history"])
    if len(yes_s) == 0 and len(no_s) == 0:
        return None
    cluster = raw["topic"]
    return Market(
        id=raw["id"],
        slug=raw["slug"],
        question=raw["question"],
        topic=cluster,
        topics=CLUSTER_TOPICS.get(cluster, []),
        start_date=pd.Timestamp(raw["start_date"]),
        end_date=pd.Timestamp(raw["end_date"]),
        yes_series=yes_s,
        no_series=no_s,
    )


def load_all_markets() -> dict[str, Market]:
    out: dict[str, Market] = {}
    for p in sorted(PRICES_DIR.glob("*.json")):
        m = load_market(p)
        if m is not None:
            out[m.id] = m
    return out


def trading_calendar(markets: dict[str, Market], start: str, end: str) -> pd.DatetimeIndex:
    """Union of all observation dates across markets (Polymarket trades daily)."""
    dates = pd.DatetimeIndex([])
    for m in markets.values():
        dates = dates.union(m.yes_series.index).union(m.no_series.index)
    cal = pd.date_range(start=start, end=end, freq="D")
    return cal.intersection(dates).union(cal[cal.weekday < 5])  # ensure weekdays present
