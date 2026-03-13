# Inverse Trump Options Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a Python backtesting tool that scrapes Trump's 2026 speeches, extracts economic claims, and simulates a contrarian options trading strategy on SPY across three expiration windows.

**Architecture:** Pipeline of 5 modules: scraper pulls transcripts from Rev.com, claims module maps keywords to trade signals, options pricer calculates Black-Scholes prices for ATM options at 3 expiry windows, backtester simulates portfolio with 10% bet sizing, analysis module produces charts and stats.

**Tech Stack:** Python 3.12+, uv, beautifulsoup4, requests, yfinance, scipy, pandas, matplotlib

---

### Task 1: Project Setup

**Files:**
- Create: `pyproject.toml`
- Create: `src/__init__.py`
- Create: `src/config.py`
- Create: `tests/__init__.py`
- Create: `tests/test_config.py`

**Step 1: Initialize git and uv project**

```bash
cd /home/b/projects/inversedjt
git init
uv init --no-readme
```

**Step 2: Configure pyproject.toml**

Replace the generated pyproject.toml with:

```toml
[project]
name = "inversedjt"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "beautifulsoup4>=4.12",
    "requests>=2.31",
    "yfinance>=0.2",
    "scipy>=1.12",
    "pandas>=2.1",
    "matplotlib>=3.8",
    "lxml>=5.0",
]

[tool.pytest.ini_options]
testpaths = ["tests"]

[project.optional-dependencies]
dev = ["pytest>=8.0"]
```

**Step 3: Install dependencies**

```bash
uv pip install -e ".[dev]"
```

**Step 4: Create directory structure**

```bash
mkdir -p src data/speeches data/trades tests
touch src/__init__.py tests/__init__.py
```

**Step 5: Write the failing test for config**

```python
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
```

**Step 6: Run test to verify it fails**

Run: `uv run pytest tests/test_config.py -v`
Expected: FAIL (ImportError)

**Step 7: Write config.py**

```python
# src/config.py
STARTING_CAPITAL = 100_000
BET_FRACTION = 0.10

EXPIRY_WINDOWS = {
    "next_day": 1,
    "end_of_week": None,  # calculated dynamically based on trade day
    "thirty_day": 30,
}

# Keywords/phrases that indicate economic claims
# bullish claims -> we buy puts (bet market drops)
# bearish claims -> we buy calls (bet market rises)
CLAIM_CATEGORIES = {
    "bullish": [
        "economy is strong",
        "economy is booming",
        "economy is doing great",
        "economy is incredible",
        "greatest economy",
        "best economy",
        "stock market is at an all-time high",
        "stock market is soaring",
        "stock market is doing great",
        "market is way up",
        "markets are up",
        "jobs are through the roof",
        "jobs numbers are incredible",
        "unemployment is at a record low",
        "lowest unemployment",
        "wages are rising",
        "inflation is coming down",
        "inflation is under control",
        "we're doing tremendously",
        "numbers are fantastic",
        "gdp is through the roof",
        "manufacturing is coming back",
        "trade deals are working",
    ],
    "bearish": [
        "economy is a disaster",
        "economy is crashing",
        "economy is failing",
        "economy is terrible",
        "worst economy",
        "stock market crash",
        "market is collapsing",
        "jobs are disappearing",
        "unemployment is terrible",
        "inflation is out of control",
        "inflation is destroying",
        "prices are through the roof",
        "we're heading for a recession",
        "trade deficit is a disaster",
    ],
}

SPY_TICKER = "SPY"
RISK_FREE_RATE = 0.05  # approximate 2026 rate
```

**Step 8: Run test to verify it passes**

Run: `uv run pytest tests/test_config.py -v`
Expected: PASS

**Step 9: Commit**

```bash
git add pyproject.toml src/__init__.py src/config.py tests/__init__.py tests/test_config.py data/
git commit -m "project setup with config constants"
```

---

### Task 2: Speech Scraper

**Files:**
- Create: `src/scraper.py`
- Create: `tests/test_scraper.py`

**Step 1: Write the failing test**

```python
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
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_scraper.py::test_parse_transcript_page -v`
Expected: FAIL (ImportError)

**Step 3: Write scraper.py**

```python
# src/scraper.py
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
```

**Step 4: Run tests**

Run: `uv run pytest tests/test_scraper.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/scraper.py tests/test_scraper.py
git commit -m "add Rev.com transcript scraper"
```

---

### Task 3: Claim Extraction

**Files:**
- Create: `src/claims.py`
- Create: `tests/test_claims.py`

**Step 1: Write the failing test**

```python
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
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_claims.py -v`
Expected: FAIL (ImportError)

**Step 3: Write claims.py**

```python
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
```

**Step 4: Run tests**

Run: `uv run pytest tests/test_claims.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/claims.py tests/test_claims.py
git commit -m "add claim extraction with keyword matching"
```

---

### Task 4: Options Pricer (Black-Scholes)

**Files:**
- Create: `src/options_pricer.py`
- Create: `tests/test_options_pricer.py`

**Step 1: Write the failing test**

```python
# tests/test_options_pricer.py
from src.options_pricer import black_scholes_price, calculate_option_pnl


def test_bs_call_price_positive():
    price = black_scholes_price(
        S=500, K=500, T=30/365, r=0.05, sigma=0.20, option_type="call"
    )
    assert price > 0
    assert price < 500  # can't cost more than underlying


def test_bs_put_price_positive():
    price = black_scholes_price(
        S=500, K=500, T=30/365, r=0.05, sigma=0.20, option_type="put"
    )
    assert price > 0


def test_bs_atm_call_roughly_correct():
    # ATM 30-day option on $500 stock with 20% vol should be ~$8-12
    price = black_scholes_price(
        S=500, K=500, T=30/365, r=0.05, sigma=0.20, option_type="call"
    )
    assert 5 < price < 20


def test_pnl_winning_call():
    pnl = calculate_option_pnl(
        entry_price=10.0, spot_at_entry=500, spot_at_expiry=520,
        strike=500, option_type="call", num_contracts=1,
    )
    # Intrinsic value at expiry = 20, paid 10, profit = 10 per share, 100 shares per contract
    assert pnl == (20 - 10) * 100


def test_pnl_losing_put():
    pnl = calculate_option_pnl(
        entry_price=10.0, spot_at_entry=500, spot_at_expiry=510,
        strike=500, option_type="put", num_contracts=1,
    )
    # Put expires worthless, lose premium
    assert pnl == -10 * 100


def test_max_loss_is_premium():
    pnl = calculate_option_pnl(
        entry_price=10.0, spot_at_entry=500, spot_at_expiry=400,
        strike=500, option_type="call", num_contracts=1,
    )
    assert pnl == -10 * 100  # max loss = premium paid
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_options_pricer.py -v`
Expected: FAIL (ImportError)

**Step 3: Write options_pricer.py**

```python
# src/options_pricer.py
"""Black-Scholes options pricing and P&L calculation."""
import math

from scipy.stats import norm


def black_scholes_price(
    S: float, K: float, T: float, r: float, sigma: float, option_type: str
) -> float:
    """Calculate Black-Scholes option price.

    Args:
        S: Current spot price
        K: Strike price
        T: Time to expiration in years
        r: Risk-free rate
        sigma: Annualized volatility
        option_type: "call" or "put"
    """
    if T <= 0:
        # At expiration, return intrinsic value
        if option_type == "call":
            return max(S - K, 0)
        return max(K - S, 0)

    d1 = (math.log(S / K) + (r + sigma**2 / 2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)

    if option_type == "call":
        return S * norm.cdf(d1) - K * math.exp(-r * T) * norm.cdf(d2)
    else:
        return K * math.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)


def calculate_option_pnl(
    entry_price: float,
    spot_at_entry: float,
    spot_at_expiry: float,
    strike: float,
    option_type: str,
    num_contracts: int,
) -> float:
    """Calculate P&L for a long option position at expiration.

    Each contract = 100 shares. Max loss = premium paid.
    """
    if option_type == "call":
        intrinsic = max(spot_at_expiry - strike, 0)
    else:
        intrinsic = max(strike - spot_at_expiry, 0)

    pnl_per_share = intrinsic - entry_price
    return pnl_per_share * 100 * num_contracts
```

**Step 4: Run tests**

Run: `uv run pytest tests/test_options_pricer.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/options_pricer.py tests/test_options_pricer.py
git commit -m "add Black-Scholes options pricer"
```

---

### Task 5: Backtester

**Files:**
- Create: `src/backtester.py`
- Create: `tests/test_backtester.py`

**Step 1: Write the failing test**

```python
# tests/test_backtester.py
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
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_backtester.py -v`
Expected: FAIL (ImportError)

**Step 3: Write backtester.py**

```python
# src/backtester.py
"""Portfolio simulation engine for the contrarian options strategy."""
import math
from datetime import datetime, timedelta

import pandas as pd
import yfinance as yf

from src.config import EXPIRY_WINDOWS, RISK_FREE_RATE, SPY_TICKER
from src.options_pricer import black_scholes_price, calculate_option_pnl


def get_spy_prices(start: str = "2026-01-01", end: str = "2026-12-31") -> pd.DataFrame:
    """Fetch SPY OHLC data from yfinance."""
    ticker = yf.Ticker(SPY_TICKER)
    return ticker.history(start=start, end=end)


def estimate_volatility(prices: pd.DataFrame, window: int = 20) -> pd.Series:
    """Calculate rolling annualized volatility from daily returns."""
    returns = prices["Close"].pct_change()
    return returns.rolling(window).std() * math.sqrt(252)


def days_to_expiry(trade_date: pd.Timestamp, window_name: str, prices: pd.DataFrame) -> int:
    """Calculate days to expiration based on window type."""
    if window_name == "next_day":
        return 1
    elif window_name == "end_of_week":
        # Days until Friday
        days_until_friday = 4 - trade_date.weekday()
        if days_until_friday <= 0:
            days_until_friday += 5
        return max(days_until_friday, 1)
    elif window_name == "thirty_day":
        return 30
    return 1


def find_expiry_price(prices: pd.DataFrame, trade_date: pd.Timestamp, dte: int) -> float | None:
    """Find the closing price at or near the expiry date."""
    target = trade_date + timedelta(days=dte)
    # Find nearest trading day at or after target
    future_dates = prices.index[prices.index >= target]
    if len(future_dates) == 0:
        # If expiry is past our data, use last available price
        return prices["Close"].iloc[-1] if len(prices) > 0 else None
    return prices["Close"].loc[future_dates[0]]


def run_backtest(
    prices: pd.DataFrame,
    signals: dict[str, str],
    starting_capital: float,
    bet_fraction: float,
) -> pd.DataFrame:
    """Run the backtest simulation across all 3 expiry windows.

    Args:
        prices: SPY OHLC DataFrame indexed by date
        signals: dict mapping date strings to "put" or "call"
        starting_capital: initial portfolio value
        bet_fraction: fraction of portfolio to bet per trade
    """
    vol = estimate_volatility(prices)

    portfolios = {
        "next_day": starting_capital,
        "end_of_week": starting_capital,
        "thirty_day": starting_capital,
    }

    trades = []

    for date_str, signal in sorted(signals.items()):
        trade_date = pd.Timestamp(date_str)

        # Find this date in prices (must be a trading day)
        if trade_date not in prices.index:
            # Find next trading day
            future = prices.index[prices.index >= trade_date]
            if len(future) == 0:
                continue
            trade_date = future[0]

        spot = prices.loc[trade_date, "Open"]
        current_vol = vol.loc[:trade_date].dropna().iloc[-1] if len(vol.loc[:trade_date].dropna()) > 0 else 0.20
        strike = round(spot)  # ATM

        trade_row = {
            "date": date_str,
            "trade_date": trade_date,
            "signal": signal,
            "spot": spot,
            "strike": strike,
            "volatility": current_vol,
        }

        for window_name in ["next_day", "end_of_week", "thirty_day"]:
            dte = days_to_expiry(trade_date, window_name, prices)
            T = dte / 365

            option_price = black_scholes_price(
                S=spot, K=strike, T=T, r=RISK_FREE_RATE,
                sigma=current_vol, option_type=signal,
            )

            # How much to spend
            budget = portfolios[window_name] * bet_fraction
            # Each contract costs option_price * 100
            cost_per_contract = option_price * 100
            if cost_per_contract <= 0:
                num_contracts = 0
            else:
                num_contracts = max(1, int(budget / cost_per_contract))

            total_cost = num_contracts * cost_per_contract

            # Find expiry price
            expiry_price = find_expiry_price(prices, trade_date, dte)
            if expiry_price is None:
                pnl = 0
            else:
                pnl = calculate_option_pnl(
                    entry_price=option_price,
                    spot_at_entry=spot,
                    spot_at_expiry=expiry_price,
                    strike=strike,
                    option_type=signal,
                    num_contracts=num_contracts,
                )

            portfolios[window_name] += pnl

            trade_row[f"option_price_{window_name}"] = option_price
            trade_row[f"num_contracts_{window_name}"] = num_contracts
            trade_row[f"dte_{window_name}"] = dte
            trade_row[f"expiry_price_{window_name}"] = expiry_price
            trade_row[f"pnl_{window_name}"] = pnl
            trade_row[f"portfolio_{window_name}"] = portfolios[window_name]

        trades.append(trade_row)

    return pd.DataFrame(trades)
```

**Step 4: Run tests**

Run: `uv run pytest tests/test_backtester.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/backtester.py tests/test_backtester.py
git commit -m "add portfolio backtester"
```

---

### Task 6: Analysis Runner

**Files:**
- Create: `analysis.py`

**Step 1: Write analysis.py**

```python
# analysis.py
"""Main runner: scrape, extract signals, backtest, and produce analysis."""
import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from src.backtester import get_spy_prices, run_backtest
from src.claims import extract_signal
from src.config import BET_FRACTION, STARTING_CAPITAL
from src.scraper import scrape_all


def load_or_scrape_speeches() -> list[dict]:
    """Load cached speeches or scrape fresh."""
    speech_dir = Path("data/speeches")
    existing = sorted(speech_dir.glob("*.json"))

    if existing:
        print(f"Found {len(existing)} cached speeches")
        speeches = []
        for f in existing:
            with open(f) as fh:
                speeches.append(json.load(fh))
        return speeches

    print("Scraping speeches from Rev.com...")
    return scrape_all(2026)


def extract_signals(speeches: list[dict]) -> dict[str, str]:
    """Extract trade signals from speeches."""
    signals = {}
    for speech in speeches:
        signal = extract_signal(speech["text"])
        if signal:
            date = speech["date"]
            # Only one trade per day (first speech wins)
            if date not in signals:
                signals[date] = signal
                print(f"  {date}: {signal} (from: {speech.get('title', 'unknown')})")
    return signals


def print_summary(trades: pd.DataFrame):
    """Print summary statistics."""
    print("\n" + "=" * 70)
    print("INVERSE TRUMP OPTIONS STRATEGY - RESULTS")
    print("=" * 70)
    print(f"Total signal days: {len(trades)}")
    print(f"Starting capital: ${STARTING_CAPITAL:,.0f}")
    print()

    for window in ["next_day", "end_of_week", "thirty_day"]:
        pnl_col = f"pnl_{window}"
        port_col = f"portfolio_{window}"

        if pnl_col not in trades.columns:
            continue

        total_pnl = trades[pnl_col].sum()
        wins = (trades[pnl_col] > 0).sum()
        losses = (trades[pnl_col] < 0).sum()
        flat = (trades[pnl_col] == 0).sum()
        win_rate = wins / max(wins + losses, 1) * 100
        final_portfolio = trades[port_col].iloc[-1] if len(trades) > 0 else STARTING_CAPITAL
        total_return = (final_portfolio - STARTING_CAPITAL) / STARTING_CAPITAL * 100

        # Max drawdown
        portfolio_series = pd.concat([
            pd.Series([STARTING_CAPITAL]),
            trades[port_col].reset_index(drop=True),
        ])
        peak = portfolio_series.cummax()
        drawdown = (portfolio_series - peak) / peak * 100
        max_dd = drawdown.min()

        label = window.replace("_", " ").title()
        print(f"--- {label} Expiry ---")
        print(f"  Final portfolio: ${final_portfolio:,.0f}")
        print(f"  Total return:    {total_return:+.1f}%")
        print(f"  Win rate:        {win_rate:.0f}% ({wins}W / {losses}L / {flat}F)")
        print(f"  Max drawdown:    {max_dd:.1f}%")
        print(f"  Best trade:      ${trades[pnl_col].max():,.0f}")
        print(f"  Worst trade:     ${trades[pnl_col].min():,.0f}")
        print()


def plot_results(trades: pd.DataFrame, spy_prices: pd.DataFrame):
    """Generate portfolio value chart."""
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))

    # Portfolio value over time
    for window, color, label in [
        ("next_day", "red", "Next-Day Expiry"),
        ("end_of_week", "blue", "End-of-Week Expiry"),
        ("thirty_day", "green", "30-Day Expiry"),
    ]:
        col = f"portfolio_{window}"
        if col in trades.columns:
            values = pd.concat([
                pd.Series([STARTING_CAPITAL], index=[trades["trade_date"].iloc[0]]),
                trades.set_index("trade_date")[col],
            ])
            ax1.plot(values.index, values.values, color=color, label=label, marker="o", markersize=3)

    # SPY buy-and-hold baseline
    spy_start = spy_prices["Close"].iloc[0]
    spy_baseline = (spy_prices["Close"] / spy_start) * STARTING_CAPITAL
    ax1.plot(spy_baseline.index, spy_baseline.values, color="gray", linestyle="--", label="SPY Buy & Hold", alpha=0.7)

    ax1.axhline(y=STARTING_CAPITAL, color="black", linestyle=":", alpha=0.3)
    ax1.set_title("Inverse Trump Strategy vs SPY Buy & Hold")
    ax1.set_ylabel("Portfolio Value ($)")
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    # Trade P&L distribution
    for window, color, label in [
        ("next_day", "red", "Next-Day"),
        ("end_of_week", "blue", "End-of-Week"),
        ("thirty_day", "green", "30-Day"),
    ]:
        col = f"pnl_{window}"
        if col in trades.columns:
            ax2.hist(trades[col], bins=20, alpha=0.5, color=color, label=label)

    ax2.axvline(x=0, color="black", linestyle="-", alpha=0.5)
    ax2.set_title("Trade P&L Distribution")
    ax2.set_xlabel("P&L ($)")
    ax2.set_ylabel("Count")
    ax2.legend()
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig("data/trades/results.png", dpi=150)
    print("Chart saved to data/trades/results.png")
    plt.show()


def main():
    # 1. Get speeches
    speeches = load_or_scrape_speeches()
    print(f"\nLoaded {len(speeches)} speeches")

    # 2. Extract signals
    print("\nExtracting trade signals...")
    signals = extract_signals(speeches)
    print(f"\n{len(signals)} trading days identified")

    if not signals:
        print("No trade signals found. Check speech data and claim categories.")
        sys.exit(1)

    # 3. Get SPY prices
    print("\nFetching SPY price data...")
    spy_prices = get_spy_prices("2026-01-01", "2026-12-31")
    print(f"Got {len(spy_prices)} trading days of SPY data")

    # 4. Run backtest
    print("\nRunning backtest...")
    trades = run_backtest(spy_prices, signals, STARTING_CAPITAL, BET_FRACTION)

    # 5. Save trade log
    trades.to_csv("data/trades/trade_log.csv", index=False)
    print("Trade log saved to data/trades/trade_log.csv")

    # 6. Print summary
    print_summary(trades)

    # 7. Plot
    plot_results(trades, spy_prices)


if __name__ == "__main__":
    main()
```

**Step 2: Run full pipeline test**

Run: `uv run python analysis.py`
Expected: Scrapes speeches, extracts signals, runs backtest, prints summary, saves chart.

**Step 3: Commit**

```bash
git add analysis.py
git commit -m "add analysis runner with charts and summary stats"
```

---

### Task 7: End-to-End Smoke Test

**Files:**
- Create: `tests/test_integration.py`

**Step 1: Write integration test**

```python
# tests/test_integration.py
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
```

**Step 2: Run all tests**

Run: `uv run pytest tests/ -v`
Expected: ALL PASS

**Step 3: Commit**

```bash
git add tests/test_integration.py
git commit -m "add integration smoke test"
```
