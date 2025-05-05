import pytest
from strategy_selector import StrategySelector
from strategies import LongCall, LongPut, Straddle, IronCondor, VerticalSpread

@ pytest.mark.parametrize("trend, iv, momentum, expected_cls", [
    ("bullish", 0.1, "positive", LongCall),
    ("bearish", 0.1, "negative", LongPut),
    ("neutral", 0.1, "positive", Straddle),
    ("neutral", 0.3, "negative", IronCondor),
    ("bearish", 0.3, "positive", VerticalSpread),
])
def test_select_strategy(trend, iv, momentum, expected_cls):
    selector = StrategySelector(iv_threshold=0.25)
    strategy = selector.select(trend, iv, momentum)
    assert isinstance(strategy, expected_cls)