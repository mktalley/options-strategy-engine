import pytest
from datetime import date
from strategies import CoveredCall

# Constants for tests
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


def test_covered_call_score_bullish_positive_iv_high():
    data = sample_data('bullish', 'positive', iv=0.3)
    assert CoveredCall.score(data) == 3.0


def test_covered_call_score_bullish_positive_iv_low():
    data = sample_data('bullish', 'positive', iv=0.2)
    assert CoveredCall.score(data) == 2.0


def test_covered_call_score_non_qualifying():
    # Non-bullish or non-positive momentum
    tests = [
        ('bearish', 'positive', 0.3),
        ('bullish', 'negative', 0.3),
        ('neutral', 'positive', 0.3),
    ]
    for trend, momentum, iv in tests:
        data = sample_data(trend, momentum, iv)
        # Even if IV high, without both trend and momentum, only 1 point from IV
        score = CoveredCall.score(data)
        if iv >= data['iv_threshold']:
            assert score == 1.0
        else:
            assert score == 0.0


def test_covered_call_run_bullish_positive():
    data = sample_data('bullish', 'positive', iv=0.3)
    orders = CoveredCall().run(data)
    assert len(orders) == 1
    order = orders[0]
    assert order['side'] == 'sell'
    assert order['qty'] == 1
    assert order['type'] == 'market'
    assert order['time_in_force'] == 'day'
    # Check symbol suffix for call at ATM
    suffix = 'C' + f"{int(round(PRICE) * 1000):08d}"
    assert order['symbol'].endswith(suffix)


def test_covered_call_run_non_qualifying():
    for trend, momentum in [('bearish', 'positive'), ('bullish', 'negative'), ('neutral', 'positive')]:
        data = sample_data(trend, momentum, iv=0.3)
        orders = CoveredCall().run(data)
        assert orders == []
