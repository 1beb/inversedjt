"""Score remaining speeches in parallel (8 concurrent CLI calls)."""
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from src.llm_signals import (
    CACHE_PATH, load_cache, save_cache, score_speech_via_cli,
)


def main(concurrency: int = 8):
    cache = load_cache()
    files = sorted(Path("data/speeches").glob("2026-*.json"))
    todo = [f for f in files if f.stem not in cache]
    print(f"Have {len(cache)} cached; need {len(todo)} more with concurrency={concurrency}")

    def work(sf: Path):
        with open(sf) as fh:
            s = json.load(fh)
        try:
            res = score_speech_via_cli(s["date"], s.get("title", ""), s["text"])
        except Exception as e:
            return sf.stem, None, str(e)
        return sf.stem, {"date": s["date"], "title": s.get("title", ""),
                         "cost_usd": res["cost_usd"], **res["score"]}, None

    with ThreadPoolExecutor(max_workers=concurrency) as ex:
        futures = {ex.submit(work, sf): sf for sf in todo}
        for fut in as_completed(futures):
            key, rec, err = fut.result()
            if err:
                print(f"  ERR {key}: {err[:120]}")
                continue
            cache[key] = rec
            save_cache(cache)
            print(f"  {rec['date']} | bull={rec['bullishness']:+d} sal={rec['salience']:2d} "
                  f"${rec['cost_usd']:.3f} | {key[:50]}")

    total = sum(v.get("cost_usd", 0.0) for v in cache.values())
    print(f"\nDone. {len(cache)} total, ${total:.2f} total cost")


if __name__ == "__main__":
    main()
