"""Scrape Trump transcript text from Rev.com using Playwright."""
import json
import re
import sys
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

DATA_DIR = Path("data/speeches")


def parse_date(date_str: str) -> str:
    """Convert 'Mar 12, 2026' to '2026-03-12'."""
    dt = datetime.strptime(date_str, "%b %d, %Y")
    return dt.strftime("%Y-%m-%d")


def extract_trump_text(full_text: str) -> str:
    """Extract Trump's spoken portions from the full transcript text."""
    lines = full_text.split("\n")
    trump_parts = []
    capturing = False

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Check if this is a Trump speaker label line
        if re.match(r"^Donald Trump\s*[\(:]", line, re.IGNORECASE):
            capturing = True
            # Remove the speaker label and timestamp
            text = re.sub(r"^Donald Trump\s*\([^)]*\)\s*:?\s*", "", line, flags=re.IGNORECASE)
            text = re.sub(r"^Donald Trump\s*:\s*", "", text, flags=re.IGNORECASE)
            if text:
                trump_parts.append(text)
        elif re.match(r"^[A-Z][a-z]+ [A-Z][a-z]+\s*[\(:]", line):
            # Another speaker started
            capturing = False
        elif re.match(r"^Speaker \d+\s*[\(:]", line):
            capturing = False
        elif capturing:
            trump_parts.append(line)

    return " ".join(trump_parts)


def main():
    listing_file = DATA_DIR / "listing.json"
    if not listing_file.exists():
        print("No listing.json found.")
        sys.exit(1)

    with open(listing_file) as f:
        entries = json.load(f)

    print(f"Found {len(entries)} transcripts to scrape")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        for i, entry in enumerate(entries):
            date_iso = parse_date(entry["date"])
            slug = entry["url"].split("/")[-1]
            outfile = DATA_DIR / f"{date_iso}_{slug}.json"

            if outfile.exists():
                print(f"  [{i+1}/{len(entries)}] Cached: {entry['title']}")
                continue

            print(f"  [{i+1}/{len(entries)}] Scraping: {entry['title']}...")
            try:
                page.goto(entry["url"], wait_until="domcontentloaded", timeout=30000)
                # Wait for transcript content to render
                page.wait_for_timeout(3000)
                full_text = page.evaluate("() => document.body.innerText")
            except Exception as e:
                print(f"    ERROR: {e}")
                continue

            if not full_text:
                print(f"    WARNING: No text returned")
                continue

            trump_text = extract_trump_text(full_text)
            if not trump_text:
                # If no speaker labels, use full body text
                trump_text = full_text

            speech = {
                "date": date_iso,
                "title": entry["title"],
                "url": entry["url"],
                "text": trump_text,
            }

            with open(outfile, "w") as f:
                json.dump(speech, f, indent=2)

            print(f"    Saved {len(trump_text)} chars")

        browser.close()

    print("\nDone!")


if __name__ == "__main__":
    main()
