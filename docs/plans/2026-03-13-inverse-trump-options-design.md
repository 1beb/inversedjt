# Inverse Trump Options Trading Analysis

## Overview

Analyze Trump's 2026 speeches and simulate an options trading strategy that bets against his economic claims on SPY. Compare performance across three options expiration windows.

## Data Sources

- Speech transcripts from Rev.com (donald-trump-transcripts category, 2026 YTD)
- SPY price data via yfinance
- Options pricing via Black-Scholes estimation

## Claim Mapping

Predefined keyword categories map speech claims to trade signals:

- Bullish economic claims (economy strong, market highs, jobs great) -> buy SPY puts
- Bearish economic claims (economy failing, market crashing, jobs terrible) -> buy SPY calls
- No relevant claims -> no trade
- One trade per day max, at market open

## Trade Structure

- Starting portfolio: $100,000
- Bet size: 10% of current portfolio value per trade
- Options: ATM (at-the-money) long puts or calls
- Three expiration windows tested in parallel:
  - Next-day expiry
  - End-of-week expiry
  - 30-day expiry
- Max loss per trade = premium paid

## Project Structure

```
inversedjt/
├── pyproject.toml
├── src/
│   ├── scraper.py        # Rev.com speech scraper
│   ├── claims.py         # Claim category mapping + signal extraction
│   ├── options_pricer.py # Black-Scholes pricing for 3 expiry windows
│   ├── backtester.py     # Portfolio simulation engine
│   └── config.py         # Constants (start capital, bet size, categories)
├── data/
│   ├── speeches/         # Raw scraped transcripts (JSON)
│   └── trades/           # Generated trade log (CSV)
└── analysis.py           # Main runner + output charts/tables
```

## Output

- Trade log CSV with per-trade details for all 3 expiry windows
- Summary stats: total trades, win rate, total return, max drawdown, sharpe ratio
- Charts: cumulative portfolio value (3 expiry lines + SPY buy-and-hold baseline), trade P&L distribution
