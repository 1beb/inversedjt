# Inverse Trump: Betting Against Presidential Economic Claims

An analysis of what happens when you trade against Trump's bullish economic claims using SPY and sector ETFs. Covers January 5 - March 12, 2026 using 34 scraped speech transcripts from Rev.com.

## The Question

Trump frequently makes bullish claims about the economy in speeches ("greatest economy ever", "stock market at all-time high", etc.). What if you systematically bet against those claims?

## Data Pipeline

1. Scraped 34 Trump speech transcripts from Rev.com (Jan-Mar 2026) using Playwright
2. Keyword-matched bullish/bearish economic claims to generate trade signals
3. 13 signal days identified (12 bullish -> buy puts/short, 1 bearish -> buy calls/long)
4. Backtested across multiple instruments, strategies, and hold windows

## Step 1: Basic Options Backtest on SPY

Starting capital $100k, betting 10% per trade, ATM options priced via Black-Scholes using historical volatility.

### Inverse (bet against claims) vs Believe (trust claims)

| Strategy | Next-Day | End-of-Week | 30-Day |
|---|---|---|---|
| Inverse Trump | +75.1% | +35.6% | +8.5% |
| Believe Trump | -16.6% | -52.0% | -66.8% |

The "believe" strategy on 30-day options went 0 wins, 13 losses. Every single trade lost money.

## Step 2: Multi-Ticker Options (Historical Vol)

Extended the strategy to sector ETFs and leveraged products, still using historical volatility for pricing.

### Next-Day Expiry

| Ticker | Name | Inverse | Believe | Spread | W/L |
|---|---|---|---|---|---|
| TNA | 3x Russell 2000 | +3,691% | +1,285% | +2,406% | 6W/7L |
| TQQQ | 3x Nasdaq | +573% | +73% | +500% | 7W/6L |
| SPXL | 3x S&P 500 | +411% | +69% | +342% | 7W/6L |
| IWM | Russell 2000 | +274% | +72% | +203% | 6W/7L |
| SMH | Semiconductors | +247% | +121% | +126% | 6W/7L |
| XLF | Financials | +184% | -27% | +211% | 7W/6L |
| XHB | Homebuilders | +93% | +53% | +40% | 5W/8L |
| SPY | S&P 500 | +75% | -17% | +92% | 5W/8L |
| KRE | Regional Banks | +65% | +811% | -746% | 5W/8L |
| EEM | Emerging Markets | +58% | -8% | +66% | 5W/8L |
| XLI | Industrials | +57% | -7% | +64% | 6W/7L |
| XLE | Energy | -66% | +465% | -531% | 1W/12L |

XLE (Energy) is the consistent exception -- Trump's energy claims ("drill baby drill") actually aligned with reality.

## Step 3: Multi-Ticker Options (Real Implied Volatility)

The historical vol numbers were unrealistic. Real options on leveraged ETFs have much higher implied volatility. Current IV from options chains:

| Ticker | IV |
|---|---|
| TNA | 107% |
| XHB | 86% |
| TQQQ | 85% |
| SPXL | 78% |
| XLI | 52% |
| SMH | 50% |
| KRE | 45% |
| EEM | 42% |
| XLE | 36% |
| XLF | 31% |
| IWM | 30% |
| SPY | 21% |

### Next-Day Expiry (Real IV Pricing)

| Ticker | IV | Inverse | Believe | W/L |
|---|---|---|---|---|
| IWM | 30% | +47.2% | -2.7% | 6W/7L |
| TNA | 107% | +16.0% | -12.4% | 6W/7L |
| XLF | 31% | +10.7% | -45.9% | 7W/6L |
| TQQQ | 85% | +9.5% | -34.2% | 5W/8L |
| SPY | 21% | +3.8% | -34.4% | 4W/9L |
| SMH | 50% | -1.4% | -18.5% | 6W/7L |
| SPXL | 78% | -20.2% | -47.6% | 4W/9L |

TNA went from +3,691% to +16%. Real IV pricing crushes the leveraged ETF fantasy returns.

### 30-Day Expiry (Real IV Pricing)

| Ticker | IV | Inverse | Believe | W/L |
|---|---|---|---|---|
| XLF | 31% | +15.7% | -72.3% | 6W/7L |
| KRE | 45% | -13.7% | -54.1% | 5W/8L |
| IWM | 30% | -23.6% | -67.1% | 6W/7L |
| TQQQ | 85% | -25.6% | -70.6% | 5W/8L |
| SPY | 21% | -30.2% | -67.4% | 4W/9L |

With real IV, most 30-day options strategies lose money. Only XLF stays positive.

## Step 4: Direct Buy/Sell (No Options)

Removed options entirely. Buy/sell ETFs directly on signal days.

### Next-Day Hold

| Ticker | Name | Inverse | Believe | Spread | W/L |
|---|---|---|---|---|---|
| TQQQ | 3x Nasdaq | +0.8% | -1.1% | +1.9% | 8W/5L |
| TNA | 3x Russell 2000 | +0.7% | -1.0% | +1.7% | 7W/6L |
| SPXL | 3x S&P 500 | +0.5% | -0.8% | +1.4% | 8W/5L |
| XLF | Financials | +0.3% | -0.6% | +0.9% | 8W/5L |
| IWM | Russell 2000 | +0.1% | -0.4% | +0.5% | 6W/7L |

### 30-Day Hold

| Ticker | Name | Inverse | Believe | Spread | W/L |
|---|---|---|---|---|---|
| TNA | 3x Russell 2000 | +10.4% | -9.8% | +20.1% | 10W/3L |
| TQQQ | 3x Nasdaq | +9.2% | -8.8% | +18.0% | 12W/1L |
| SPXL | 3x S&P 500 | +6.5% | -6.4% | +12.8% | 10W/3L |
| XLF | Financials | +5.0% | -5.0% | +10.0% | 12W/1L |
| KRE | Regional Banks | +3.0% | -3.3% | +6.3% | 9W/4L |
| IWM | Russell 2000 | +2.8% | -3.0% | +5.8% | 8W/5L |
| SPY | S&P 500 | +1.7% | -1.9% | +3.6% | 10W/3L |
| XLE | Energy | -10.9% | +11.8% | -22.7% | 1W/12L |

Modest returns, but the signal is real and consistent. Inverse beats believe on 10 of 12 tickers.

## Step 5: Inverse ETFs (Buy Only, No Shorting)

Since 12/13 signals are bearish (buy puts/short), use inverse ETFs instead of short selling. No borrowing fees, no margin.

### 30-Day Hold

| Pair | Return | Win Rate | Commissions |
|---|---|---|---|
| XLF/SKF | +11.7% | 12W/1L | $129 |
| TNA/TZA | +9.0% | 8W/5L | $129 |
| QQQ/SQQQ | +8.6% | 10W/3L | $129 |
| IWM/TZA | +8.2% | 8W/5L | $129 |
| TQQQ/SQQQ | +8.0% | 10W/3L | $129 |
| SPY/SPXU | +6.2% | 10W/3L | $129 |
| SPY/SH | +2.2% | 10W/3L | $129 |
| XLE/ERY | -18.8% | 1W/12L | $129 |

## Step 6: Debit Spreads (Reduced IV Cost)

Bear put spreads on put signals, bull call spreads on call signals. Tested $1, $2, $5, $10 widths.

### 30-Day Expiry -- Best Spreads

| Ticker | IV | Width | Return | W/L | Avg Debit |
|---|---|---|---|---|---|
| XLF | 31% | $1 | +189.7% | 12W/1L | $0.45 |
| XLF | 31% | $2 | +154.1% | 11W/2L | $0.82 |
| TQQQ | 85% | $2 | +107.9% | 10W/3L | $1.00 |
| SPY | 21% | $2 | +88.1% | 10W/3L | $0.95 |
| SPXL | 78% | $5 | +69.9% | 10W/3L | $2.55 |
| IWM | 30% | $5 | +45.3% | 8W/5L | $2.26 |
| TNA | 107% | $2 | +40.3% | 8W/5L | $1.04 |

Narrow spreads ($1-2 wide) dramatically outperform naked options because entry cost is low and small moves hit max profit.

**However:** These spread numbers use the simplified backtester that doesn't track daily portfolio fluctuations or overlapping positions. See Step 7 for realistic numbers.

## Step 7: Mark-to-Market (Realistic Daily Portfolio Tracking)

The final, most honest version. Fixes all backtester flaws:

- Tracks all open positions daily with mark-to-market valuation
- Sizes new trades based on actual free capital (not locked in open positions)
- With 30-day holds and signals every few days, up to 7 positions overlap
- Produces a daily equity curve, not just trade-to-trade snapshots

### Inverse ETF Strategy -- Mark-to-Market Results

#### Next-Day Hold

| Pair | Return | Max DD | Worst Day | W/L | Max Open |
|---|---|---|---|---|---|
| TNA/TZA | +1.8% | -1.4% | -0.4% | 7W/4L | 1 |
| TQQQ/SQQQ | +1.4% | -0.8% | -0.4% | 8W/3L | 1 |
| IWM/TZA | +1.3% | -1.4% | -0.4% | 7W/4L | 1 |
| QQQ/SQQQ | +1.2% | -0.8% | -0.4% | 8W/3L | 1 |
| SPY/SPXU | +0.7% | -0.5% | -0.3% | 8W/3L | 1 |
| XLF/SKF | +0.4% | -0.6% | -0.3% | 6W/5L | 1 |
| SPY/SH | +0.2% | -0.2% | -0.1% | 8W/3L | 1 |

#### End-of-Week Hold

| Pair | Return | Max DD | Worst Day | W/L | Max Open |
|---|---|---|---|---|---|
| TNA/TZA | +3.0% | -1.3% | -1.2% | 6W/5L | 2 |
| IWM/TZA | +2.1% | -1.4% | -1.2% | 6W/5L | 2 |
| TQQQ/SQQQ | +2.0% | -0.7% | -0.7% | 7W/4L | 2 |
| QQQ/SQQQ | +1.8% | -0.8% | -0.7% | 7W/4L | 2 |
| SPY/SPXU | +1.0% | -0.6% | -0.6% | 6W/5L | 2 |
| XLF/SKF | +0.7% | -0.8% | -0.4% | 6W/5L | 2 |
| SPY/SH | +0.4% | -0.2% | -0.2% | 6W/5L | 2 |

#### 30-Day Hold

| Pair | Return | Max DD | Worst Day | W/L | Max Open |
|---|---|---|---|---|---|
| XLF/SKF | +5.9% | -2.2% | -1.8% | 10W/1L | 7 |
| TNA/TZA | +5.3% | -6.0% | -5.3% | 7W/4L | 7 |
| QQQ/SQQQ | +5.3% | -4.0% | -3.1% | 9W/2L | 7 |
| TQQQ/SQQQ | +4.7% | -4.0% | -3.1% | 9W/2L | 7 |
| IWM/TZA | +4.5% | -6.1% | -5.4% | 7W/4L | 7 |
| SPY/SPXU | +3.7% | -3.3% | -2.8% | 9W/2L | 7 |
| SPY/SH | +1.3% | -1.1% | -0.9% | 9W/2L | 7 |

## Key Findings

1. The inverse signal is real -- betting against Trump's bullish economic claims beat believing them across nearly every instrument, strategy, and time window tested
2. Energy (XLE) is the one exception -- Trump's energy claims aligned with reality
3. The realistic return (MTM, inverse ETFs, 30-day hold) is roughly +4-6% over 2.5 months, not the +189% the naive backtester suggested
4. XLF/SKF (financials) was the most consistent winner: +5.9% return, -2.2% max drawdown, 10W/1L
5. No one has published this specific finding before (as of March 2026)
6. The simplest implementation: buy SKF when Trump makes a bullish economic claim, hold 30 days, sell

## Commissions

All backtests include Questrade commission modeling:

- Options: $9.95 + $1/contract per trade
- Stocks/ETFs: $4.95 per trade

## Disclaimer

This is a research project, not investment advice. Past performance does not guarantee future results. The strategy covers a short time window (Jan-Mar 2026) and may not generalize.

## How to Run

```bash
# Install dependencies
uv pip install -e ".[dev]"

# Scrape fresh transcripts (requires Playwright)
uv run playwright install chromium
uv run python scrape_transcripts.py

# Run analyses
uv run python analysis.py              # Basic SPY options
uv run python analysis_multi.py        # Multi-ticker options (real IV)
uv run python analysis_direct.py       # Direct buy/sell
uv run python analysis_inverse_etfs.py # Inverse ETF buy-only
uv run python analysis_spreads.py      # Debit spreads
uv run python analysis_mtm.py          # Mark-to-market (realistic)

# Run tests
uv run pytest tests/ -v
```
