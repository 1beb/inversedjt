# tests/test_claims.py
from src.claims import extract_signal


def test_bullish_claim_returns_put():
    text = "The economy is doing great. We have the greatest economy ever."
    signal = extract_signal(text)
    assert signal == "put"


def test_bearish_claim_returns_call():
    text = "The economy is a disaster. Inflation is out of control."
    signal = extract_signal(text)
    assert signal == "call"


def test_no_claim_returns_none():
    text = "We met with the president of France to discuss foreign policy."
    signal = extract_signal(text)
    assert signal is None


def test_mixed_claims_uses_majority():
    text = (
        "The economy is strong. The economy is booming. "
        "But inflation is out of control."
    )
    signal = extract_signal(text)
    # 2 bullish vs 1 bearish -> bullish -> put
    assert signal == "put"
