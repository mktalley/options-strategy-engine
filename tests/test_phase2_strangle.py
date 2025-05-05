import pytest
from datetime import date
from strategies import Strangle

# Constants
TICKER = 'XYZ'
EXP_DATE = date(2025, 10, 17)


def sample_data(iv=0.2, trend='neutral'):
    return {
        'ticker': TICKER,
        'price': 100.0,
        'expiration': EXP_DATE,
        'trend': trend,
        'iv': iv,
        'iv_threshold': 0.25
    }


def test_strangle_score_neutral_iv_low():
    data = sample_data(iv=0.2, trend='neutral')
    assert Strangle.score(data) == 2.0


def test_strangle_score_neutral_iv_high():
    data = sample_data(iv=0.3, trend='neutral')
    assert Strangle.score(data) == 1.0


def test_strangle_score_non_neutral():
    for trend in ['bullish', 'bearish']:
        data = sample_data(iv=0.2, trend=trend)
        assert Strangle.score(data) == 0.0


def test_strangle_run_neutral():
    data = sample_data(iv=0.2, trend='neutral')
    orders = Strangle().run(data)
    assert len(orders) == 2, "Strangle should generate two legs when neutral"
    # Expected strikes
    put_strike = round(data['price']) - 2
    call_strike = round(data['price']) + 2
    # Build suffixes to match symbols
    suffix_put = 'P' + f"{int(put_strike * 1000):08d}"
    suffix_call = 'C' + f"{int(call_strike * 1000):08d}"
    # Check both legs present
    symbols = [o['symbol'] for o in orders]
    assert any(s.endswith(suffix_put) for s in symbols)
    assert any(s.endswith(suffix_call) for s in symbols)
    # Check sides and order types
    for order in orders:
        assert order['side'] == 'buy'
        assert order['type'] == 'market'
        assert order['time_in_force'] == 'day'


def test_strangle_run_non_neutral():
    for trend in ['bullish', 'bearish']:
        data = sample_data(iv=0.2, trend=trend)
        orders = Strangle().run(data)
        assert orders == [], f"Expected no orders when trend is {trend}, got {orders}"
