"""Smoke test the full pipeline with fake data."""
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from src.backtester import run_backtest
from src.claims import extract_signal


def test_full_pipeline_with_fake_data():
    """Test signal extraction -> backtest with synthetic data."""
    # Fake speeches
    speeches = [
        {"date": "2026-01-06", "text": "The economy is doing great. Best economy ever. Stock market is at an all-time high."},
        {"date": "2026-01-15", "text": "We discussed foreign policy with our allies."},
        {"date": "2026-02-01", "text": "The economy is a disaster under the previous administration."},
    ]

    # Extract signals
    signals = {}
    for s in speeches:
        sig = extract_signal(s["text"])
        if sig:
            signals[s["date"]] = sig

    assert signals == {
        "2026-01-06": "put",   # bullish -> buy puts
        "2026-02-01": "call",  # bearish -> buy calls
    }

    # Fake prices
    dates = pd.bdate_range("2026-01-02", "2026-03-15")
    prices = pd.DataFrame({
        "Open": [500 + i * 0.5 for i in range(len(dates))],
        "Close": [501 + i * 0.5 for i in range(len(dates))],
        "High": [503 + i * 0.5 for i in range(len(dates))],
        "Low": [499 + i * 0.5 for i in range(len(dates))],
    }, index=dates)

    # Run backtest
    result = run_backtest(prices, signals, 100_000, 0.10)

    assert len(result) == 2
    assert "pnl_next_day" in result.columns
    assert "portfolio_thirty_day" in result.columns
    # Portfolio should have changed from starting value
    assert result["portfolio_next_day"].iloc[-1] != 0
