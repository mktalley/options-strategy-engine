import pytest
import numpy as np
import os

from utils import get_iv, get_trend, get_momentum, get_market_data

class FakeTrade:
    def __init__(self, price):
        self.price = price

class FakeBar:
    def __init__(self, c):
        self.c = c

class FakeClient:
    def __init__(self, api_key=None, secret_key=None, raw_data=None, url_override=None):
        pass

    def get_stock_latest_trade(self, req):
        # Return a dict mapping symbol to FakeTrade
        return {req.symbol_or_symbols: FakeTrade(price=123.45)}

    def get_stock_bars(self, req):
        # Return a dict mapping symbol to list of FakeBar
        return {req.symbol_or_symbols: [FakeBar(c=100.0), FakeBar(c=110.0), FakeBar(c=105.0)]}

@pytest.fixture(autouse=True)
def patch_data_client(monkeypatch):
    # Monkeypatch the Alpaca data client classes
    import alpaca.data.historical.stock as stock_mod
    class BarReq:
        def __init__(self, *, symbol_or_symbols, timeframe, limit):
            self.symbol_or_symbols = symbol_or_symbols
    class TradeReq:
        def __init__(self, *, symbol_or_symbols):
            self.symbol_or_symbols = symbol_or_symbols

    monkeypatch.setattr(stock_mod, 'StockHistoricalDataClient', FakeClient)
    monkeypatch.setattr(stock_mod, 'StockBarsRequest', BarReq)
    monkeypatch.setattr(stock_mod, 'StockLatestTradeRequest', TradeReq)
    yield


def test_get_iv_empty():
    assert get_iv({'close_prices': []}) == 0.0


def test_get_iv_single():
    assert get_iv({'close_prices': [100.0]}) == 0.0


def test_get_iv_multiple():
    prices = [100.0, 102.0, 101.0]
    data = {'close_prices': prices}
    log_returns = np.diff(np.log(prices))
    expected = np.std(log_returns) * np.sqrt(252)
    assert get_iv(data) == pytest.approx(expected)


def test_get_trend_neutral_short():
    data = {'close_prices': [i for i in range(10)], 'price': 5}
    assert get_trend(data) == 'neutral'


def test_get_trend_bullish():
    close_prices = list(range(1, 21))  # 1 to 20
    price = 25
    data = {'close_prices': close_prices, 'price': price}
    assert get_trend(data) == 'bullish'


def test_get_trend_bearish():
    close_prices = list(range(1, 21))  # 1 to 20
    price = 5
    data = {'close_prices': close_prices, 'price': price}
    assert get_trend(data) == 'bearish'


def test_get_momentum_neutral():
    assert get_momentum({'close_prices': [100.0]}) == 'neutral'


def test_get_momentum_positive():
    data = {'close_prices': [100.0, 110.0]}
    assert get_momentum(data) == 'positive'


def test_get_momentum_negative():
    data = {'close_prices': [110.0, 100.0]}
    assert get_momentum(data) == 'negative'


def test_get_market_data(monkeypatch):
    # Using patched FakeClient via fixture
    result = get_market_data(['FOO'], 'key', 'secret', None)
    assert 'FOO' in result
    assert result['FOO']['price'] == 123.45
    assert result['FOO']['close_prices'] == [100.0, 110.0, 105.0]