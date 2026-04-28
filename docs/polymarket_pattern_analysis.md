# Polymarket Inverse-Trump Pattern Analysis

Findings from applying the inverse-Trump signal pipeline to Polymarket binary markets over Jan 5 - Apr 30, 2026. Companion to README Step 8.

## Headline result

Starting capital $100,000, hold window 30 days, mark-to-market.

| Strategy | Trades | Final P&L | Return | Max DD |
|---|---|---|---|---|
| Approach B (LLM-matched markets, all signal days) | 66 | +$68,687 | +68.7% | -8.6% |
| Refined pattern (entry NO < 0.50 + winning topics) | 6 | +$63,326 | +63.3% | <-3% |

The refined pattern captured 92% of the full strategy's profit on 9% of the trades. Five of those six winners are the same market: "Will Trump visit China by April 30?".

## The dataset

- 42 Trump speech transcripts (Jan 5 - Apr 14, 2026), scored by LLM for bullishness, salience, topics
- 32 LLM-derived signal days (vs 14 from the keyword extractor)
- 29 hand-curated Polymarket markets in `data/polymarket/shortlist.json`
- Full daily price history per market via Polymarket CLOB API

## Three market trajectories

Every market we studied falls into one of three trajectory categories.

### 1. Pump-and-fade

Trump's hype briefly pushes YES up, then it collapses to zero by deadline. This is where the contrarian NO trade has the biggest theoretical upside.

| Market | Start YES | Peak YES | End YES | Best NO trade |
|---|---|---|---|---|
| Trump visit China by April 30 | 0.80 | 0.94 | 0.00 | +1,715% |
| Trump talk to Xi in March | 0.52 | 0.94 | 0.00 | +1,564% |
| US strikes Iran by Jan 31 | 0.23 | 0.65 | 0.01 | +178% |
| US strikes Iran by Feb 28 | 0.43 | 0.59 | 0.20 | +96% |
| US forces enter Iran by Mar 31 | 0.23 | 0.48 | 0.00 | +94% |
| Iranian regime fall by Mar 31 | 0.13 | 0.37 | 0.00 | +57% |
| Greenland acquisition (2026/2027) | 0.10-0.14 | 0.20-0.30 | 0.07-0.14 | +17-24% |
| SCOTUS rules for Trump tariffs | 0.23 | 0.33 | 0.26 | +10% |

The Iran cluster mirrors the China-visit dynamic: three different "US strikes Iran by date X" markets all pumped on Trump's hawkish rhetoric, then crashed when no strike materialized.

### 2. Steady-decay

Markets where YES was already cheap (≤0.15) and just drifted to zero. The strategy works but capital efficiency is poor — 5-19% returns over months.

- Russia-Ukraine ceasefires (Jan 31, Feb 28, Apr 30): all started near 0.10, all resolved NO. NO entry at 0.90+ caps upside.
- Bitcoin $150K monthly markets: all started near 0.01. Never delivered. NO already at 0.99.
- Fed January 50bps cut: same dynamic.

### 3. Anti-patterns - Trump's claim actually came true

| Market | Result | Why the inverse trade fails |
|---|---|---|
| U.S. anti-cartel ground operation in Mexico by Jan 31 | YES | Trump can unilaterally order military ops |
| Khamenei out as Supreme Leader of Iran by March 31 | YES | Actually happened (real geopolitics) |
| Crude Oil hit $100 by end of March | YES | External supply shock, not Trump's doing |
| Trump talks to Macron in January | YES | Macron-Trump calls are routine |

## The unifying principle

Trump's claims fail when they require a counterparty's action plus a deadline.

| Type of claim | Fails because | Markets that fit |
|---|---|---|
| "I'll meet/visit/talk to leader X" | Counterparty must agree and schedule | China visit, Xi call, Putin call |
| "Russia-Ukraine ceasefire by [date]" | Both belligerents must agree | All near-term ceasefire markets |
| "Fed will cut at next meeting" | Powell decides, not Trump | All near-term Fed cut markets |
| "We'll strike Iran by [date]" | Requires Pentagon commitment + Trump rarely follows through | All Iran-strike-by-date markets |

Trump's claims succeed when he can unilaterally execute.

| Type of claim | Works because | Markets that fit |
|---|---|---|
| Cartel ops in Mexico | Commander-in-chief order | Mexico anti-cartel ops |
| Tariff threats | Executive authority | Most enacted |
| Pardons / executive orders | Stroke-of-pen actions | N/A in this basket |

## Speech frequency vs market resolution

How often Trump mentioned a theme across the 42 speeches, paired with how the corresponding markets resolved.

| Theme | Speeches mentioning | Market direction |
|---|---|---|
| Iran | 31 | Mixed (strikes-by-date NO, Khamenei out YES) |
| Mexico cartel | 29 | YES (Trump executed) |
| Tariff/trade win | 26 | Mostly enacted; SCOTUS market still open |
| Russia-Ukraine end | 19 | NO across all near-term deadlines |
| Putin call/meet | 15 | NO (Jan deadline) |
| Fed rate cuts | 13 | NO across all near-term meetings |
| China visit/Xi | 12 | NO (the killer pattern) |
| Greenland | 5 | Trending NO, still open |
| Bitcoin/crypto | 2 | NO (small sample) |

Speech frequency alone is a weak signal. Iran (31 mentions) and Mexico cartel (29 mentions) were the most-talked themes but produced mixed or anti-pattern outcomes. The China-visit theme was 12th in mention count but generated the largest profit.

## The winning trades

All six refined-pattern trades, by signal day:

| Date | Market | Entry NO | Exit NO | Return | P&L |
|---|---|---|---|---|---|
| Feb 19 | Trump visit China by April 30 | 0.145 | 0.775 | +434% | $24,112 |
| Feb 15 | Trump visit China by April 30 | 0.155 | 0.570 | +268% | $15,981 |
| Mar 10 | Trump visit China by April 30 | 0.125 | 0.982 | +686% | $9,399 |
| Mar 04 | Trump visit China by April 30 | 0.135 | 0.982 | +627% | $7,074 |
| Feb 17 | Trump visit China by April 30 | 0.145 | 0.595 | +310% | $4,784 |
| Mar 10 | Trump talk to Xi in March | 0.295 | 0.720 | +144% | $1,975 |

Trump claimed an imminent China visit in five separate speeches across Feb-Mar. The market priced YES at 12-16% each time. He never went. Each speech was a $5K-$24K hit.

## Tradeable patterns to add to the playbook

1. Iran imminent-strike pump-and-fade. When Trump's speech is hawkish on Iran and the Polymarket strike-by-date market is above 0.30, buy NO. Three separate Iran markets fit this profile and all paid out.

2. Russia-Ukraine ceasefire by next short deadline. Reliable NO winner but small magnitudes. Better used for diversification than alpha.

3. Fed cut at next FOMC meeting where YES > 0.20. When Trump publicly pressures the Fed and the market is pricing a cut at >20% probability, buy NO on the cut. The March meeting market (0.365 to 0.004) confirmed once. Needs more meetings to validate.

## Mistakes to avoid

- Do not bet against military strikes Trump has already ordered (Iran Midnight Hammer was a Jan 5 anti-pattern that lost $5,353).
- Do not bet against routine diplomatic calls (Macron - cost $3,899 across approaches).
- Do not bet against unilateral executive actions (Mexico cartel ops).
- Do not trade markets that resolved before the signal day fired (Maduro markets returned exactly $0).

## Caveats

1. Concentration risk. Five of six refined-pattern winners are the same market. If China-visit had resolved YES, the entire +63% goes to roughly zero.
2. Sample size. 32 signal days, 6 high-conviction trades. Confidence intervals on the headline return are wide.
3. Resolution clipping. Many markets resolve before a 30-day hold ends, forcing early exit. Most clipping was favorable here but won't always be.
4. No fee modeling. Polymarket has zero commissions but a small protocol fee on profits; not modeled.
5. Topic gaps in Polymarket coverage. Trump talks tariffs, inflation, GDP, jobs constantly, but Polymarket has essentially no liquid markets on these. The basket is biased toward foreign-policy promises.
6. Forward applicability. Trump's pattern of overpromising on multilateral commitments may persist, but specific themes change. The mechanism (counterparty + deadline) is more durable than the specific markets.

## Reproducing

```
uv run python fetch_polymarket_prices.py
uv run python analysis_polymarket.py            # baseline A/B/C
uv run python analysis_polymarket_pattern.py    # extended with LLM signals + refined filter
```

Outputs in `data/trades/poly_*` and `data/trades/polymarket_summary.csv`.
