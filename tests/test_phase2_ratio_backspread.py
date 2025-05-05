import pytest
from datetime import date
from strategies import RatioBackspread

# Constants
TICKER = 'XYZ'
PRICE = 100.0
EXP_DATE = date(2025, 10, 17)


def sample_score_data(trend, momentum, iv, iv_th=0.25):
    return {
        'trend': trend,
        'momentum': momentum,
        'iv': iv,
        'iv_threshold': iv_th,
    }


def sample_run_data(momentum):
    return {
        'ticker': TICKER,
        'price': PRICE,
        'expiration': EXP_DATE,
        'momentum': momentum,
    }


test_params_score = [
    ('bullish', 'positive', 0.2, 0.25, 3.0),
    ('bullish', 'positive', 0.3, 0.25, 2.0),
    ('bearish', 'negative', 0.2, 0.25, 3.0),
    ('bearish', 'negative', 0.3, 0.25, 2.0),
    ('neutral', 'neutral', 0.2, 0.25, 1.0),
    ('neutral', 'neutral', 0.3, 0.25, 0.0),
]

@pytest.mark.parametrize("trend, momentum, iv, iv_th, expected", test_params_score)
def test_ratio_backspread_score(trend, momentum, iv, iv_th, expected):
    data = sample_score_data(trend, momentum, iv, iv_th)
    assert RatioBackspread.score(data) == expected


def test_ratio_backspread_run_positive():
    data = sample_run_data('positive')
    orders = RatioBackspread().run(data)
    # Should sell 1 call at ATM, buy 2 calls OTM
    assert len(orders) == 3
    sell_order = orders[0]
    buy_orders = orders[1:]
    # Check sell order
    assert sell_order['side'] == 'sell'
    assert sell_order['symbol'].endswith('C' + f"{int(round(PRICE) * 1000):08d}")
    # Check buy orders
    otm_strike = round(PRICE) + 2
    suffix = 'C' + f"{int(otm_strike * 1000):08d}"
    for bo in buy_orders:
        assert bo['side'] == 'buy'
        assert bo['symbol'].endswith(suffix)


def test_ratio_backspread_run_negative():
    data = sample_run_data('negative')
    orders = RatioBackspread().run(data)
    # Should sell 1 put at ATM, buy 2 puts OTM
    assert len(orders) == 3
    sell_order = orders[0]
    buy_orders = orders[1:]
    assert sell_order['side'] == 'sell'
    assert sell_order['symbol'].endswith('P' + f"{int(round(PRICE) * 1000):08d}")
    utm_strike = round(PRICE) - 2
    suffix = 'P' + f"{int(utm_strike * 1000):08d}"
    for bo in buy_orders:
        assert bo['side'] == 'buy'
        assert bo['symbol'].endswith(suffix)


def test_ratio_backspread_run_non_directional():
    # momentum not positive or negative
    data = sample_run_data('neutral')
    orders = RatioBackspread().run(data)
    assert orders == []
