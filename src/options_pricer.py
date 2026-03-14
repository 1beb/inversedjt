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


def calculate_spread_price(
    S: float, K_long: float, K_short: float, T: float, r: float, sigma: float,
    spread_type: str,
) -> float:
    """Calculate net debit for a vertical spread.

    spread_type: "bear_put" (buy high put, sell low put) or
                 "bull_call" (buy low call, sell high call)
    """
    if spread_type == "bear_put":
        long_price = black_scholes_price(S, K_long, T, r, sigma, "put")
        short_price = black_scholes_price(S, K_short, T, r, sigma, "put")
    else:  # bull_call
        long_price = black_scholes_price(S, K_long, T, r, sigma, "call")
        short_price = black_scholes_price(S, K_short, T, r, sigma, "call")
    return long_price - short_price


def calculate_spread_pnl(
    net_debit: float,
    spot_at_expiry: float,
    K_long: float,
    K_short: float,
    spread_type: str,
    num_contracts: int,
) -> float:
    """Calculate P&L for a vertical spread at expiration.

    Max loss = net debit. Max gain = width - net debit.
    """
    if spread_type == "bear_put":
        # Long put at K_long, short put at K_short (K_long > K_short)
        long_intrinsic = max(K_long - spot_at_expiry, 0)
        short_intrinsic = max(K_short - spot_at_expiry, 0)
    else:  # bull_call
        # Long call at K_long, short call at K_short (K_long < K_short)
        long_intrinsic = max(spot_at_expiry - K_long, 0)
        short_intrinsic = max(spot_at_expiry - K_short, 0)

    spread_value = long_intrinsic - short_intrinsic
    pnl_per_share = spread_value - net_debit
    return pnl_per_share * 100 * num_contracts
