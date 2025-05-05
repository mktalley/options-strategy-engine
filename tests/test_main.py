import pytest
import asyncio
import logging

import main
import utils

class DummyStrategy:
    def run(self, data):
        # return a single mock order
        return [{
            'symbol': data.get('ticker'),
            'qty': 2,
            'side': 'sell',
            'type': 'market',
            'time_in_force': 'day'
        }]

class DummySelector:
    def select(self, trend, iv, momentum):
        return DummyStrategy()

class DummyExecutor:
    def __init__(self):
        self.calls = []
    def execute(self, orders):
        self.calls.append(orders)
        return ['mock_response']

@pytest.mark.asyncio
async def test_scheduled_run_success(monkeypatch, caplog):
    # Simulate market data for one ticker
    sample_data = {'ABC': {}}
    monkeypatch.setenv('ALPACA_API_KEY', 'key')
    monkeypatch.setenv('ALPACA_SECRET_KEY', 'secret')
    monkeypatch.setenv('ALPACA_API_BASE_URL', 'url')
    # Monkeypatch get_market_data to return sample_data
    monkeypatch.setattr(utils, 'get_market_data', lambda tickers, api, sec, url: sample_data)

    selector = DummySelector()
    executor = DummyExecutor()
    caplog.set_level(logging.INFO)

    # Run scheduled_run
    await main.scheduled_run(selector, executor, 'key', 'secret', 'url', ['ABC'])

    # Ensure executor was called with the mock order
    assert executor.calls, "Executor.execute was not called"
    orders = executor.calls[0]
    assert isinstance(orders, list)
    assert orders[0]['symbol'] == 'ABC'
    assert 'Batch processing complete' in caplog.text

@pytest.mark.asyncio
async def test_scheduled_run_no_orders(monkeypatch, caplog):
    # Simulate no market data returned
    monkeypatch.setenv('ALPACA_API_KEY', 'key')
    monkeypatch.setenv('ALPACA_SECRET_KEY', 'secret')
    monkeypatch.setenv('ALPACA_API_BASE_URL', 'url')
    monkeypatch.setattr(utils, 'get_market_data', lambda tickers, api, sec, url: {})

    selector = DummySelector()
    executor = DummyExecutor()
    caplog.set_level(logging.INFO)

    # Run scheduled_run with empty data
    await main.scheduled_run(selector, executor, 'key', 'secret', 'url', ['XYZ'])

    # Should finish without calling executor
    assert executor.calls == []
    # Should still log completion
    assert 'Batch processing complete' in caplog.text

@pytest.mark.asyncio
async def test_scheduled_run_fetch_error(monkeypatch, caplog):
    # Simulate get_market_data throwing an exception
    def raise_error(tickers, api, sec, url):  # noqa: unused-argument
        raise RuntimeError('fetch failed')
    monkeypatch.setenv('ALPACA_API_KEY', 'key')
    monkeypatch.setenv('ALPACA_SECRET_KEY', 'secret')
    monkeypatch.setenv('ALPACA_API_BASE_URL', 'url')
    monkeypatch.setattr(utils, 'get_market_data', raise_error)

    selector = DummySelector()
    executor = DummyExecutor()
    caplog.set_level(logging.ERROR)

    # Run scheduled_run and expect it to return early
    await main.scheduled_run(selector, executor, 'key', 'secret', 'url', ['ERR'])

    # No executor calls
    assert executor.calls == []
    # Should log the fetch error
    assert 'Failed to fetch market data: fetch failed' in caplog.text


def test_validate_env():
    # Missing api_key
    assert not main.validate_env('', 'secret', 'url', ['T'])
    # Missing secret_key
    assert not main.validate_env('key', '', 'url', ['T'])
    # Missing base_url
    assert not main.validate_env('key', 'secret', '', ['T'])
    # Missing tickers
    assert not main.validate_env('key', 'secret', 'url', [])
    # All present
    assert main.validate_env('key', 'secret', 'url', ['T'])
