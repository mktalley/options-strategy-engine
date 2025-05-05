import pytest
from datetime import date
from strategies import Collar

# Constants
TICKER = 'XYZ'
PRICE = 100.0
EXP_DATE = date(2025, 10, 17)
WIDTH = 2


def sample_data(trend, iv, iv_th=0.25):
    return {
        'ticker': TICKER,
        'price': PRICE,
        'expiration': EXP_DATE,
        'trend': trend,
        'iv': iv,
        'iv_threshold': iv_th,
    }


def test_collar_score_neutral_iv_high():
    data = sample_data('neutral', iv=0.3)
    assert Collar.score(data) == 3.0


def test_collar_score_neutral_iv_low():
    data = sample_data('neutral', iv=0.2)
    assert Collar.score(data) == 2.0


def test_collar_score_non_neutral():
    for trend in ['bullish', 'bearish']:
        data = sample_data(trend, iv=0.3)
        # Only IV high gives 1.0 point
        assert Collar.score(data) == 1.0
        data_low = sample_data(trend, iv=0.2)
        assert Collar.score(data_low) == 0.0


def test_collar_run_neutral():
    data = sample_data('neutral', iv=0.3)
    orders = Collar().run(data)
    assert len(orders) == 2
    # First: sell call at ATM+width
    call_order = orders[0]
    expected_call_strike = round(PRICE) + WIDTH
    suffix_call = 'C' + f"{int(expected_call_strike * 1000):08d}"
    assert call_order['side'] == 'sell'
    assert call_order['symbol'].endswith(suffix_call)
    # Second: buy put at ATM-width
    put_order = orders[1]
    expected_put_strike = round(PRICE) - WIDTH
    suffix_put = 'P' + f"{int(expected_put_strike * 1000):08d}"
    assert put_order['side'] == 'buy'
    assert put_order['symbol'].endswith(suffix_put)


def test_collar_run_non_neutral():
    for trend in ['bullish', 'bearish']:
        data = sample_data(trend, iv=0.3)
        orders = Collar().run(data)
        assert orders == []
