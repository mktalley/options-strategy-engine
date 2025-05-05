import datetime
import pandas as pd
import pytest

import backtest

class FakeBar:
    def __init__(self, c, t):
        self.c = c
        self.t = t

class FakeStrategy:
    def __init__(self, data):
        # name visible via class __name__
        pass
    def run(self, data):
        # Return a single dummy order dict
        return [{
            'symbol': 'SYMFAKE123',
            'side': 'buy',
            'qty': 1,
            'type': 'market',
            'time_in_force': 'day'
        }]

class FakeSelector:
    def __init__(self, iv_threshold=None):
        pass
    def select(self, trend, iv, momentum):
        return FakeStrategy(None)

class FakeExecutor:
    def __init__(self, dry_run=False):
        self.dry_run = dry_run
    def execute(self, orders):
        # Echo back orders
        return orders

@pytest.fixture(autouse=True)
def patch_components(monkeypatch):
    # Patch StrategySelector and TradeExecutor
    monkeypatch.setattr(backtest, 'StrategySelector', FakeSelector)
    monkeypatch.setattr(backtest, 'TradeExecutor', FakeExecutor)
    # Patch get_bars to return synthetic bars
    def fake_get_bars(client, ticker, start, end):
        # Create 21 bars: first 20 for window, last is entry
        bars = []
        # Window bars: price increments
        for i in range(20):
            bars.append(FakeBar(c=100.0 + i, t=datetime.datetime(2025,5,1)))
        # Last bar
        bars.append(FakeBar(c=120.0, t=datetime.datetime(2025,5,1)))
        return bars
    monkeypatch.setattr(backtest, 'get_bars', fake_get_bars)
    yield


def test_run_backtest_records():
    # Provide minimal parameters
    df = backtest.run_backtest(
        tickers=['FAKE'],
        start_date=datetime.datetime(2025,4,1),
        end_date=datetime.datetime(2025,5,30),
        api_key='AK',
        secret_key='SK',
        base_url='https://api.example.com',
        data_url=None,
        iv_threshold=0.5
    )
    # Should return a DataFrame with one entry record and one summary record
    assert isinstance(df, pd.DataFrame)
    # Two rows: one for the order, one for the summary
    assert df.shape[0] == 2

    # Check first row contains the order details
    order_row = df.iloc[0]
    assert order_row['symbol'] == 'SYMFAKE123'
    assert order_row['side'] == 'buy'
    assert order_row['qty'] == 1
    assert order_row['ticker'] == 'FAKE'
    # entry_date should be a date equal to 2025-05-01
    assert order_row['entry_date'] == datetime.date(2025,5,1)
    # expiration should be next Friday after May 1, 2025 (Thursday -> Friday, May 2, 2025)
    assert order_row['expiration'] == datetime.date(2025,5,2)

    # Check summary row contains order_count
    summary_row = df.iloc[1]
    assert summary_row['ticker'] == 'FAKE'
    assert summary_row['strategy'] == 'FakeStrategy'
    assert summary_row['order_count'] == 1

@pytest.mark.parametrize("bars,expected_records", [
    # Less than 21 bars: no records
    ([FakeBar(c=100, t=datetime.datetime(2025,5,1)) for _ in range(20)], 0),
])
def test_run_backtest_insufficient_bars(bars, expected_records, monkeypatch):
    # Patch get_bars for this test
    monkeypatch.setattr(backtest, 'get_bars', lambda client, ticker, start, end: bars)
    df = backtest.run_backtest(
        tickers=['BAR'],
        start_date=datetime.datetime(2025,4,1),
        end_date=datetime.datetime(2025,5,30),
        api_key='AK',
        secret_key='SK',
        base_url='url',
        data_url=None,
        iv_threshold=0.5
    )
    assert isinstance(df, pd.DataFrame)
    # Should be empty DataFrame
    assert df.empty
