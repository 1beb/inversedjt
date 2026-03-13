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
