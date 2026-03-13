# tests/test_scraper.py
import json
from unittest.mock import patch, MagicMock
from src.scraper import parse_transcript_page, get_trump_transcript_urls


SAMPLE_LISTING_HTML = """
<article>
  <a href="/transcripts/trump-rally-in-kentucky">Trump Rally in Kentucky</a>
  <time datetime="2026-03-12">March 12, 2026</time>
</article>
<article>
  <a href="/transcripts/trump-gives-iran-update">Trump Gives Iran Update</a>
  <time datetime="2026-03-10">March 10, 2026</time>
</article>
"""

SAMPLE_TRANSCRIPT_HTML = """
<div class="fl-callout-text">
  <p><span>Donald Trump: (02:08)</span>
  Well, thank you very much. The economy is doing great. We have the greatest economy in the history of our country.</p>
  <p><span>Donald Trump: (03:15)</span>
  Jobs are through the roof and the stock market is at an all-time high.</p>
</div>
"""


def test_parse_transcript_page():
    result = parse_transcript_page(SAMPLE_TRANSCRIPT_HTML, "2026-03-12")
    assert result["date"] == "2026-03-12"
    assert "economy is doing great" in result["text"].lower()
    assert len(result["text"]) > 0
