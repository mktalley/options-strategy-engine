import pytest
from datetime import date
from strategies import ShortStraddle

# Constants
TICKER = 'XYZ'
EXP_DATE = date(2025, 10, 17)
PRICE = 100.0


def sample_data(trend, iv, iv_th=0.25):
    return {
        'ticker': TICKER,
        'price': PRICE,
        'expiration': EXP_DATE,
        'trend': trend,
        'iv': iv,
        'iv_threshold': iv_th,
    }


def test_short_straddle_score_neutral_iv_high():
    data = sample_data('neutral', iv=0.3)
    assert ShortStraddle.score(data) == 2.0


def test_short_straddle_score_neutral_iv_low():
    data = sample_data('neutral', iv=0.2)
    assert ShortStraddle.score(data) == 1.0


def test_short_straddle_score_non_neutral():
    for trend in ['bullish', 'bearish']:
        data = sample_data(trend, iv=0.3)
        assert ShortStraddle.score(data) == 0.0


def test_short_straddle_run_neutral():
    data = sample_data('neutral', iv=0.3)
    orders = ShortStraddle().run(data)
    assert len(orders) == 2, "Should have two legs"
    # Should be sell orders for put then call
    put_order, call_order = orders
    # Check sides
    assert put_order['side'] == 'sell'
    assert call_order['side'] == 'sell'
    # Check option types via symbol suffix
    put_suffix = 'P' + f"{int(PRICE * 1000):08d}"
    call_suffix = 'C' + f"{int(PRICE * 1000):08d}"
    assert put_order['symbol'].endswith(put_suffix)
    assert call_order['symbol'].endswith(call_suffix)


def test_short_straddle_run_non_neutral():
    for trend in ['bullish', 'bearish']:
        data = sample_data(trend, iv=0.3)
        orders = ShortStraddle().run(data)
        assert orders == [], f"Expected no orders for trend {trend}"