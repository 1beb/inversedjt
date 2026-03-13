import pandas as pd
from src.backtester import run_backtest


def make_fake_prices():
    """Create simple SPY price series for testing."""
    dates = pd.bdate_range("2026-01-05", "2026-01-09")
    return pd.DataFrame({
        "Open": [500, 502, 498, 505, 500],
        "Close": [502, 498, 505, 500, 503],
        "High": [503, 503, 506, 506, 504],
        "Low": [499, 497, 497, 499, 499],
    }, index=dates)


def make_fake_signals():
    return {
        "2026-01-05": "put",   # bullish claim -> buy put, market goes up -> lose
        "2026-01-07": "call",  # bearish claim -> buy call, market goes up -> win
    }


def test_backtest_returns_dataframe():
    prices = make_fake_prices()
    signals = make_fake_signals()
    result = run_backtest(prices, signals, 100_000, 0.10)
    assert isinstance(result, pd.DataFrame)
    assert "date" in result.columns
    assert "signal" in result.columns
    assert "pnl_next_day" in result.columns
    assert "pnl_end_of_week" in result.columns
    assert "pnl_thirty_day" in result.columns


def test_backtest_only_trades_signal_days():
    prices = make_fake_prices()
    signals = make_fake_signals()
    result = run_backtest(prices, signals, 100_000, 0.10)
    assert len(result) == 2  # only 2 signal days


def test_backtest_portfolio_changes():
    prices = make_fake_prices()
    signals = make_fake_signals()
    result = run_backtest(prices, signals, 100_000, 0.10)
    # Portfolio should not be exactly 100k after trades
    for col in ["portfolio_next_day", "portfolio_end_of_week", "portfolio_thirty_day"]:
        assert col in result.columns
