"""Scrape Trump speech transcripts from Rev.com."""
import json
import re
import time
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.rev.com"
LISTING_URL = f"{BASE_URL}/blog/transcript-category/donald-trump-transcripts"
DATA_DIR = Path(__file__).parent.parent / "data" / "speeches"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"
}


def get_trump_transcript_urls(year: int = 2026) -> list[dict]:
    """Fetch list of Trump transcript URLs and dates from Rev.com listing page."""
    transcripts = []
    page = 1

    while True:
        url = f"{LISTING_URL}/page/{page}/" if page > 1 else LISTING_URL
        resp = requests.get(url, headers=HEADERS, timeout=30)
        if resp.status_code == 404:
            break
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "lxml")
        articles = soup.select("article")

        if not articles:
            break

        for article in articles:
            link = article.select_one("a[href*='/transcripts/']")
            time_el = article.select_one("time")
            if not link or not time_el:
                continue

            date_str = time_el.get("datetime", "")
            if not date_str:
                continue

            dt = datetime.strptime(date_str[:10], "%Y-%m-%d")
            if dt.year < year:
                return transcripts
            if dt.year == year:
                title = link.get_text(strip=True)
                if "trump" in title.lower():
                    transcripts.append({
                        "date": date_str[:10],
                        "title": title,
                        "url": BASE_URL + link["href"] if link["href"].startswith("/") else link["href"],
                    })

        page += 1
        time.sleep(1)  # be polite

    return transcripts


def parse_transcript_page(html: str, date: str) -> dict:
    """Extract Trump's spoken text from a Rev.com transcript page."""
    soup = BeautifulSoup(html, "lxml")

    # Rev.com uses various containers for transcript text
    # Try multiple selectors
    text_parts = []
    for selector in [".fl-callout-text p", "article p", ".post-content p"]:
        elements = soup.select(selector)
        if elements:
            for el in elements:
                text = el.get_text(strip=True)
                # Only include Trump's speech segments
                if text.lower().startswith("donald trump") or not any(
                    text.lower().startswith(name)
                    for name in ["speaker ", "jake paul", "joe biden"]
                ):
                    # Strip speaker label prefix
                    text = re.sub(r"^Donald Trump:\s*\(\d+:\d+\)\s*", "", text, flags=re.IGNORECASE)
                    text_parts.append(text)
            break

    return {
        "date": date,
        "text": " ".join(text_parts),
    }


def scrape_all(year: int = 2026) -> list[dict]:
    """Scrape all Trump transcripts for the given year, save to data/speeches/."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    transcripts = get_trump_transcript_urls(year)
    results = []

    for entry in transcripts:
        outfile = DATA_DIR / f"{entry['date']}.json"
        if outfile.exists():
            with open(outfile) as f:
                results.append(json.load(f))
            continue

        resp = requests.get(entry["url"], headers=HEADERS, timeout=30)
        resp.raise_for_status()

        parsed = parse_transcript_page(resp.text, entry["date"])
        parsed["title"] = entry["title"]
        parsed["url"] = entry["url"]

        with open(outfile, "w") as f:
            json.dump(parsed, f, indent=2)

        results.append(parsed)
        time.sleep(1)

    return results
