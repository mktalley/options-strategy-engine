import pytest
import logging

import main
import utils

# Tests for feature module integrations

@pytest.mark.asyncio
async def test_news_manager_blocks_trade(monkeypatch, caplog):
    # Monkeypatch market data
    sample_data = {'ABC': {}}
    monkeypatch.setattr(utils, 'get_market_data', lambda tickers, api, sec, url: sample_data)

    # Dummy selector and executor
    class DummySelector:
        def select(self, trend, iv, momentum):
            class S:
                def run(self, data):
                    return [{'symbol': data.get('ticker'), 'qty': 1}]
            return S()

    class DummyExecutor:
        def __init__(self):
            self.calls = []
        def execute(self, orders):
            self.calls.append(orders)
            return ['resp']

    selector = DummySelector()
    executor = DummyExecutor()

    # Replace news_manager to block trades
    blocked = {'called': False}
    class Blocker:
        def is_trade_allowed(self, sym, data):
            blocked['called'] = True
            return False
    monkeypatch.setattr(main, 'news_manager', Blocker())

    # Ensure other managers are disabled
    monkeypatch.setattr(main, 'risk_manager', None)
    monkeypatch.setattr(main, 'model_manager', None)
    monkeypatch.setattr(main, 'alert_manager', None)

    caplog.set_level(logging.INFO)
    await main.scheduled_run(selector, executor, 'k', 's', 'url', ['ABC'])

    # Assert news_manager consulted and no execution occurred
    assert blocked['called'], "NewsManager.is_trade_allowed not called"
    assert executor.calls == [], "Orders should be blocked by NewsManager"
    assert "Trade for ABC blocked by news risk manager" in caplog.text

@pytest.mark.asyncio
async def test_risk_manager_and_model_adjustments(monkeypatch, caplog):
    # Monkeypatch market data
    sample_data = {'XYZ': {}}
    monkeypatch.setattr(utils, 'get_market_data', lambda tickers, api, sec, url: sample_data)

    # Dummy selector and executor
    class DummySelector:
        def select(self, *args):
            class S:
                def run(self, data):
                    return [{'symbol': data.get('ticker'), 'qty': 2}]
            return S()

    class DummyExecutor:
        def __init__(self):
            self.calls = []
        def execute(self, orders):
            self.calls.append(list(orders))
                    # Return dummy response list
            return ['ok']

    selector = DummySelector()
    executor = DummyExecutor()

    # Stub managers
    # RiskManager removes all orders
    monkeypatch.setattr(main, 'risk_manager', type('R', (), {'adjust_orders': lambda self, o, d: []})())
    # ModelManager passes orders through
    monkeypatch.setattr(main, 'model_manager', type('M', (), {'adjust_orders': lambda self, o, d: o})())
    # Disable news and alerts
    monkeypatch.setattr(main, 'news_manager', None)
    monkeypatch.setattr(main, 'alert_manager', None)

    caplog.set_level(logging.INFO)
    await main.scheduled_run(selector, executor, 'k', 's', 'url', ['XYZ'])

    # No execution calls since orders removed
    assert executor.calls == [], "Executor should not be called when risk_manager removes orders"
    assert "No orders remaining after adjustments for XYZ" in caplog.text

@pytest.mark.asyncio
async def test_alert_manager_called(monkeypatch):
    # Monkeypatch market data
    sample_data = {'DEF': {}}
    monkeypatch.setattr(utils, 'get_market_data', lambda tickers, api, sec, url: sample_data)

    # Dummy selector and executor
    class DummySelector:
        def select(self, *args):
            class S:
                def run(self, data):
                    return [{'symbol': data.get('ticker'), 'qty': 3}]
            return S()

    class DummyExecutor:
        def __init__(self):
            self.calls = []
        def execute(self, orders):
            self.calls.append(orders)
            return ['resp']

    selector = DummySelector()
    executor = DummyExecutor()

    # Disable news and risk and model managers
    monkeypatch.setattr(main, 'news_manager', None)
    monkeypatch.setattr(main, 'risk_manager', None)
    monkeypatch.setattr(main, 'model_manager', None)

    # Stub AlertManager to capture calls
    alerts = {'called': False, 'args': None}
    class A:
        def send_trade_alert(self, sym, ords, results, data):
            alerts['called'] = True
            alerts['args'] = (sym, ords, results)
    monkeypatch.setattr(main, 'alert_manager', A())

    await main.scheduled_run(selector, executor, 'k', 's', 'url', ['DEF'])

    # Assert executor ran and alert called
    assert executor.calls, "Executor.execute was not called"
    assert alerts['called'], "AlertManager.send_trade_alert not called"
    sym, ords, results = alerts['args']
    assert sym == 'DEF'
    assert results == ['resp']
