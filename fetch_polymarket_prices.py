"""Fetch daily price history for all shortlisted Polymarket markets."""
import json
import time
from pathlib import Path

import requests


SHORTLIST = Path("data/polymarket/shortlist.json")
OUT_DIR = Path("data/polymarket/prices")
CLOB = "https://clob.polymarket.com/prices-history"


def fetch_one(token_id: str) -> list[dict]:
    r = requests.get(CLOB, params={"market": token_id, "interval": "max", "fidelity": 1440}, timeout=30)
    r.raise_for_status()
    return r.json().get("history", [])


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    markets = json.loads(SHORTLIST.read_text())
    print(f"Fetching prices for {len(markets)} markets")

    for m in markets:
        out_path = OUT_DIR / f"{m['id']}.json"
        if out_path.exists():
            print(f"  skip {m['id']} (cached) — {m['question'][:60]}")
            continue

        try:
            yes_hist = fetch_one(m["yes_token"])
            time.sleep(0.2)
            no_hist = fetch_one(m["no_token"])
            time.sleep(0.2)
        except Exception as e:
            print(f"  ERR  {m['id']}: {e}")
            continue

        out_path.write_text(json.dumps({
            "id": m["id"],
            "slug": m["slug"],
            "question": m["question"],
            "topic": m["topic"],
            "trade": m["trade"],
            "start_date": m["start_date"],
            "end_date": m["end_date"],
            "yes_token": m["yes_token"],
            "no_token": m["no_token"],
            "yes_history": yes_hist,
            "no_history": no_hist,
        }, indent=2))
        print(f"  ok   {m['id']} — yes={len(yes_hist):>3}d no={len(no_hist):>3}d — {m['question'][:60]}")


if __name__ == "__main__":
    main()
