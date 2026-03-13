# tests/test_config.py
from src.config import STARTING_CAPITAL, BET_FRACTION, EXPIRY_WINDOWS, CLAIM_CATEGORIES


def test_starting_capital():
    assert STARTING_CAPITAL == 100_000


def test_bet_fraction():
    assert BET_FRACTION == 0.10


def test_expiry_windows():
    assert "next_day" in EXPIRY_WINDOWS
    assert "end_of_week" in EXPIRY_WINDOWS
    assert "thirty_day" in EXPIRY_WINDOWS


def test_claim_categories_has_bullish_and_bearish():
    assert "bullish" in CLAIM_CATEGORIES
    assert "bearish" in CLAIM_CATEGORIES
    for phrases in CLAIM_CATEGORIES.values():
        assert len(phrases) > 0
