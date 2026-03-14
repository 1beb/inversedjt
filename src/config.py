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

MIN_TRADE_SIZE = 500  # minimum position size to open a trade

# Questrade commission structure
COMMISSION_BASE = 9.95  # flat fee per trade
COMMISSION_PER_CONTRACT = 1.00  # per contract
COMMISSION_MIN = 9.95  # minimum per trade
