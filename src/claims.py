# src/claims.py
"""Extract trade signals from speech text using keyword matching."""
from src.config import CLAIM_CATEGORIES


def extract_signal(text: str) -> str | None:
    """Analyze speech text and return a trade signal.

    Returns:
        "put" if bullish claims dominate (bet against bullish = buy puts)
        "call" if bearish claims dominate (bet against bearish = buy calls)
        None if no relevant economic claims found
    """
    text_lower = text.lower()

    bullish_count = sum(
        1 for phrase in CLAIM_CATEGORIES["bullish"] if phrase in text_lower
    )
    bearish_count = sum(
        1 for phrase in CLAIM_CATEGORIES["bearish"] if phrase in text_lower
    )

    if bullish_count == 0 and bearish_count == 0:
        return None

    if bullish_count >= bearish_count:
        return "put"
    return "call"
