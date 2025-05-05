import pytest
from strategies import (
    
    Strangle,
    ShortStraddle,
    CoveredCall,
    ProtectivePut,
    RatioBackspread,
    Collar,
    BullCallSpread,
    BearPutSpread,
    CalendarSpread,
    IronButterfly,
    GammaScalping,
    Wheel,
    ZeroDTE
)
from datetime import date

# Sample data for testing Phase-2 strategies
def sample_data():
    return {
        'ticker': 'XYZ',
        'price': 100.0,
        'close_prices': [99.0, 100.0, 101.0],
        'expiration': date(2025, 10, 17),
        'trend': 'neutral',
        'iv': 0.2,
        'momentum': 'positive',
        'iv_threshold': 0.25,
    }

@pytest.mark.parametrize("cls", [
    BullCallSpread,
    BearPutSpread,
    CalendarSpread,
    IronButterfly,
    GammaScalping,
    Wheel,
    ZeroDTE,
])
def test_phase2_strategy_smoke_score_and_run(cls):
    data = sample_data()
    # Score should return a float
    score = cls.score(data)
    assert isinstance(score, float)
    # Instantiate and run should not error, returning a list
    strat = cls()
    orders = strat.run(data)
    assert isinstance(orders, list)
    # Each order, if present, should be a dict with required keys
    for order in orders:
        assert isinstance(order, dict)
        for key in ('symbol', 'qty', 'side', 'type', 'time_in_force'):
            assert key in order
