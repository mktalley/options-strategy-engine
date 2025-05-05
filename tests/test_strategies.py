import pytest
from datetime import date
from strategies import LongCall, LongPut, Straddle, IronCondor, VerticalSpread
from utils import format_option_symbol

EXP_DATE = date(2025, 10, 17)
TICKER = 'ABC'
PRICE = 100.0

@ pytest.mark.parametrize("strike, opt_type, side, expected_symbol_suffix", [
    (100, 'call', 'buy', 'C00100000'),
    (100, 'put', 'buy', 'P00100000'),
])
def test_long_strategies(strike, opt_type, side, expected_symbol_suffix):
    data = {'ticker': TICKER, 'price': PRICE, 'expiration': EXP_DATE}
    if opt_type == 'call':
        strat = LongCall() if side == 'buy' else None
    else:
        strat = LongPut() if side == 'buy' else None
    assert strat is not None
    orders = strat.run(data)
    assert len(orders) == 1
    order = orders[0]
    # symbol suffix matches expected format
    assert order['symbol'].startswith(TICKER)
    assert order['symbol'].endswith(expected_symbol_suffix)
    assert order['qty'] == 1
    assert order['side'] == 'buy'
    assert order['type'] == 'market'
    assert order['time_in_force'] == 'day'

def test_straddle():
    data = {'ticker': TICKER, 'price': PRICE, 'expiration': EXP_DATE}
    strat = Straddle()
    orders = strat.run(data)
    assert len(orders) == 2
    # call leg then put leg
    call_sym, put_sym = orders[0]['symbol'], orders[1]['symbol']
    assert call_sym.endswith('C00100000')
    assert put_sym.endswith('P00100000')

def test_iron_condor():
    data = {'ticker': TICKER, 'price': PRICE, 'expiration': EXP_DATE}
    strat = IronCondor()
    orders = strat.run(data)
    # four legs
    assert len(orders) == 4
    # check combinations: put buy at 96, put sell at 98, call sell at 102, call buy at 104
    strikes = [96, 98, 102, 104]
    sides = ['buy', 'sell', 'sell', 'buy']
    types = ['put', 'put', 'call', 'call']
    for order, strike, side, opt_type in zip(orders, strikes, sides, types):
        assert order['side'] == side
        suffix = ('P' if opt_type=='put' else 'C') + f"{int(strike*1000):08d}"
        assert order['symbol'].endswith(suffix)

@ pytest.mark.parametrize("trend, strikes", [
    ('bullish', [100, 102]),
    ('bearish', [100, 98]),
    ('neutral', [100, 102]),
])
def test_vertical_spread(trend, strikes):
    data = {'ticker': TICKER, 'price': PRICE, 'expiration': EXP_DATE, 'trend': trend}
    strat = VerticalSpread()
    orders = strat.run(data)
    assert len(orders) == 2
    # check first leg corresponds to trend
    for order, strike in zip(orders, strikes):
        suffix = ( 'C' if trend!='bearish' else 'P' ) + f"{int(strike*1000):08d}"
        assert order['symbol'].endswith(suffix)

