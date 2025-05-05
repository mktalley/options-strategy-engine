import pytest
from datetime import date
from strategies import ProtectivePut

# Constants
TICKER = 'XYZ'
PRICE = 100.0
EXP_DATE = date(2025, 10, 17)


def sample_data(trend, momentum, iv, iv_th=0.25):
    return {
        'ticker': TICKER,
        'price': PRICE,
        'expiration': EXP_DATE,
        'trend': trend,
        'momentum': momentum,
        'iv': iv,
        'iv_threshold': iv_th,
    }


def test_protective_put_score_bearish_negative_iv_high():
    data = sample_data('bearish', 'negative', iv=0.3)
    assert ProtectivePut.score(data) == 3.0


def test_protective_put_score_bearish_negative_iv_low():
    data = sample_data('bearish', 'negative', iv=0.2)
    assert ProtectivePut.score(data) == 2.0


def test_protective_put_score_non_qualifying():
    tests = [
        ('bullish', 'negative', 0.3),
        ('bearish', 'positive', 0.3),
        ('neutral', 'negative', 0.3),
    ]
    for trend, momentum, iv in tests:
        data = sample_data(trend, momentum, iv)
        score = ProtectivePut.score(data)
        if iv >= data['iv_threshold']:
            assert score == 1.0
        else:
            assert score == 0.0


def test_protective_put_run_bearish_negative():
    data = sample_data('bearish', 'negative', iv=0.3)
    orders = ProtectivePut().run(data)
    assert len(orders) == 1
    order = orders[0]
    assert order['side'] == 'buy'
    assert order['symbol'].endswith('P' + f"{int(round(PRICE) * 1000):08d}")


def test_protective_put_run_non_qualifying():
    for trend, momentum in [('bullish', 'negative'), ('bearish', 'positive'), ('neutral', 'negative')]:
        data = sample_data(trend, momentum, iv=0.3)
        orders = ProtectivePut().run(data)
        assert orders == []
