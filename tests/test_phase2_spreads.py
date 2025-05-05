import pytest
from datetime import date
from strategies import BullCallSpread, BearPutSpread
from utils import format_option_symbol

# Common constants
EXP_DATE = date(2025, 10, 17)
TICKER = 'XYZ'
PRICE = 100.0

@pytest.mark.parametrize("trend, expected_strikes, expected_sides", [
    ('bullish', [round(PRICE), round(PRICE) + 2], ['buy', 'sell']),
])
def test_bull_call_spread_orders_and_symbols(trend, expected_strikes, expected_sides):
    data = {'ticker': TICKER, 'price': PRICE, 'expiration': EXP_DATE, 'trend': trend}
    strat = BullCallSpread()
    orders = strat.run(data)
    assert len(orders) == 2, "BullCallSpread should produce 2 legs when bullish"
    for order, strike, side in zip(orders, expected_strikes, expected_sides):
        # Check side
        assert order['side'] == side
        # Symbol ends with correct option suffix
        suffix = 'C' + f"{int(strike * 1000):08d}"
        assert order['symbol'].endswith(suffix)

@pytest.mark.parametrize("trend", ['bearish', 'neutral', 'positive'])
def test_bull_call_spread_no_orders_on_non_bullish(trend):
    data = {'ticker': TICKER, 'price': PRICE, 'expiration': EXP_DATE, 'trend': trend}
    strat = BullCallSpread()
    orders = strat.run(data)
    assert orders == []

@pytest.mark.parametrize("trend, expected_strikes, expected_sides,opt_prefix", [
    ('bearish', [round(PRICE), round(PRICE) - 2], ['buy', 'sell'], 'P'),
])
def test_bear_put_spread_orders_and_symbols(trend, expected_strikes, expected_sides,opt_prefix):
    data = {'ticker': TICKER, 'price': PRICE, 'expiration': EXP_DATE, 'trend': trend}
    strat = BearPutSpread()
    orders = strat.run(data)
    assert len(orders) == 2, "BearPutSpread should produce 2 legs when bearish"
    for order, strike, side in zip(orders, expected_strikes, expected_sides):
        assert order['side'] == side
        suffix = opt_prefix + f"{int(strike * 1000):08d}"
        assert order['symbol'].endswith(suffix)

@pytest.mark.parametrize("trend", ['bullish', 'neutral'])
def test_bear_put_spread_no_orders_on_non_bearish(trend):
    data = {'ticker': TICKER, 'price': PRICE, 'expiration': EXP_DATE, 'trend': trend}
    strat = BearPutSpread()
    orders = strat.run(data)
    assert orders == []