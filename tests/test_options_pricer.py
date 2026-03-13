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
