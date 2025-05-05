import pytest
from datetime import date, timedelta
from utils import format_option_symbol
from strategies import CalendarSpread, IronButterfly

# Constants
TICKER = 'XYZ'
PRICE = 100.0
EXP_DATE = date(2025, 10, 17)
ATM = round(PRICE)
WIDTH = 2
FAR_EXP = EXP_DATE + timedelta(days=7)

# Tests for CalendarSpread
@pytest.mark.parametrize("trend, iv, iv_th, expected_score", [
    ('neutral', 0.2, 0.25, 3.0),
    ('neutral', 0.3, 0.25, 2.0),
    ('bullish', 0.2, 0.25, 1.0),
    ('bearish', 0.3, 0.25, 1.0),
    ('bullish', 0.3, 0.25, 0.0),
])
def test_calendar_spread_score(trend, iv, iv_th, expected_score):
    data = {'trend': trend, 'iv': iv, 'iv_threshold': iv_th}
    assert CalendarSpread.score(data) == expected_score

@pytest.mark.parametrize("trend", ['neutral'])
def test_calendar_spread_run_neutral(trend):
    data = {'ticker': TICKER, 'price': PRICE, 'expiration': EXP_DATE, 'trend': trend}
    strat = CalendarSpread()
    orders = strat.run(data)
    assert len(orders) == 2, "CalendarSpread should produce 2 legs when neutral"
    # Leg 0: buy far-term ATM call
    o0 = orders[0]
    assert o0['side'] == 'buy'
    assert o0['symbol'].startswith(f"{TICKER}{FAR_EXP.strftime('%y%m%d')}")
    # Leg 1: sell near-term ATM call
    o1 = orders[1]
    assert o1['side'] == 'sell'
    assert o1['symbol'].startswith(f"{TICKER}{EXP_DATE.strftime('%y%m%d')}")
    # Both should be calls at ATM strike
    expected_suffix = 'C' + f"{ATM*1000:08d}"
    assert o0['symbol'].endswith(expected_suffix)
    assert o1['symbol'].endswith(expected_suffix)

@pytest.mark.parametrize("trend", ['bullish', 'bearish'])
def test_calendar_spread_run_non_neutral(trend):
    data = {'ticker': TICKER, 'price': PRICE, 'expiration': EXP_DATE, 'trend': trend}
    strat = CalendarSpread()
    assert strat.run(data) == []

# Tests for IronButterfly
@pytest.mark.parametrize("trend, iv, iv_th, expected_score", [
    ('neutral', 0.3, 0.25, 3.0),
    ('neutral', 0.2, 0.25, 2.0),
    ('bullish', 0.3, 0.25, 1.0),
    ('bearish', 0.2, 0.25, 1.0),
    ('bullish', 0.2, 0.25, 0.0),
])
def test_iron_butterfly_score(trend, iv, iv_th, expected_score):
    data = {'trend': trend, 'iv': iv, 'iv_threshold': iv_th}
    assert IronButterfly.score(data) == expected_score

@pytest.mark.parametrize("trend", ['neutral'])
def test_iron_butterfly_run_neutral(trend):
    data = {'ticker': TICKER, 'price': PRICE, 'expiration': EXP_DATE, 'trend': trend}
    strat = IronButterfly()
    orders = strat.run(data)
    assert len(orders) == 4, "IronButterfly should produce 4 legs when neutral"
    # Expected legs: (ATM-WIDTH, put, buy), (ATM, put, sell), (ATM, call, sell), (ATM+WIDTH, call, buy)
    strikes = [ATM - WIDTH, ATM, ATM, ATM + WIDTH]
    types = ['put', 'put', 'call', 'call']
    sides = ['buy', 'sell', 'sell', 'buy']
    for order, strike, opt_type, side in zip(orders, strikes, types, sides):
        assert order['side'] == side
        prefix = f"{TICKER}{EXP_DATE.strftime('%y%m%d')}"
        letter = 'P' if opt_type == 'put' else 'C'
        suffix = letter + f"{int(strike*1000):08d}"
        assert order['symbol'] == prefix + suffix

@pytest.mark.parametrize("trend", ['bullish', 'bearish'])
def test_iron_butterfly_run_non_neutral(trend):
    data = {'ticker': TICKER, 'price': PRICE, 'expiration': EXP_DATE, 'trend': trend}
    strat = IronButterfly()
    assert strat.run(data) == []