import os
import pytest

import trade_executor
from trade_executor import TradeExecutor
from alpaca.trading.requests import MarketOrderRequest, OptionLegRequest
from alpaca.trading.enums import OrderSide, OrderType, TimeInForce, OrderClass
import logging

class FakeClient:
    def __init__(self, api_key, secret_key, paper=False, url_override=None):
        # record init args if needed
        self.api_key = api_key
        self.secret_key = secret_key
        self.paper = paper
        self.url_override = url_override

    def submit_order(self, req):
        # Echo back the request object for inspection
        return req

class FakeClientThrow(FakeClient):
    def submit_order(self, req):
        raise RuntimeError("submission failed")

@ pytest.fixture(autouse=True)
def patch_env_and_client(monkeypatch):
    # Set required env vars
    monkeypatch.setenv('ALPACA_API_KEY', 'testkey')
    monkeypatch.setenv('ALPACA_SECRET_KEY', 'testsecret')
    # Monkeypatch TradingClient in trade_executor module
    monkeypatch.setattr(trade_executor, 'TradingClient', FakeClient)
    yield


def test_single_leg_order():
    executor = TradeExecutor()
    orders = [{
        'symbol': 'ABC123',
        'qty': 3,
        'side': 'buy',
        'type': 'market',
        'time_in_force': 'day',
    }]
    results = executor.execute(orders)
    assert len(results) == 1
    req = results[0]
    # Should be MarketOrderRequest with matching fields
    assert isinstance(req, MarketOrderRequest)
    assert req.symbol == 'ABC123'
    assert req.qty == 3
    assert req.side == OrderSide.BUY
    assert req.type == OrderType.MARKET
    assert req.time_in_force == TimeInForce.DAY


def test_multi_leg_order():
    # Use two legs to trigger multi-leg branch
    executor = TradeExecutor()
    orders = [
        {'symbol': 'LEG1', 'qty': 1, 'side': 'buy', 'type': 'market', 'time_in_force': 'day'},
        {'symbol': 'LEG2', 'qty': 2, 'side': 'sell', 'type': 'market', 'time_in_force': 'day'},
    ]
    results = executor.execute(orders)
    assert len(results) == 1
    req = results[0]
    # Multi-leg should produce a MarketOrderRequest with order_class MLEG
    assert isinstance(req, MarketOrderRequest)
    assert req.order_class == OrderClass.MLEG
    # top-level qty should be from first leg
    assert req.qty == orders[0]['qty']
    # legs should be OptionLegRequest instances
    assert isinstance(req.legs, list)
    assert len(req.legs) == 2
    leg0, leg1 = req.legs
    assert isinstance(leg0, OptionLegRequest)
    assert leg0.symbol == 'LEG1'
    assert leg0.ratio_qty == 1
    assert leg0.side == OrderSide.BUY
    assert isinstance(leg1, OptionLegRequest)
    assert leg1.symbol == 'LEG2'
    assert leg1.ratio_qty == 2
    assert leg1.side == OrderSide.SELL


def test_order_submission_error(monkeypatch):
    # Simulate API failure: use FakeClientThrow
    monkeypatch.setattr(trade_executor, 'TradingClient', FakeClientThrow)
    executor = TradeExecutor()
    orders = [{
        'symbol': 'ERROR', 'qty': 1, 'side': 'buy', 'type': 'market', 'time_in_force': 'day'
    }]
    # Should catch the exception and return empty results
    results = executor.execute(orders)
    assert results == []


def test_dry_run_single_order(caplog):
    """
    Test that in dry_run mode, single order is not submitted and appropriate log is emitted.
    """
    executor = TradeExecutor(dry_run=True)
    orders = [{
        'symbol': 'XYZ',
        'qty': 5,
        'side': 'buy',
        'type': 'market',
        'time_in_force': 'day',
    }]
    caplog.set_level(logging.INFO)
    results = executor.execute(orders)
    # Should return the request object instead of API response
    assert len(results) == 1
    req = results[0]
    assert isinstance(req, MarketOrderRequest)
    # Verify dry-run log message
    assert any('DRY RUN: Single order request' in message for message in caplog.messages)


def test_dry_run_multi_leg_order(caplog):
    """
    Test that in dry_run mode, multi-leg order is not submitted and appropriate log is emitted.
    """
    executor = TradeExecutor(dry_run=True)
    orders = [
        {'symbol': 'LEG1', 'qty': 1, 'side': 'buy', 'type': 'market', 'time_in_force': 'day'},
        {'symbol': 'LEG2', 'qty': 2, 'side': 'sell', 'type': 'market', 'time_in_force': 'day'},
    ]
    caplog.set_level(logging.INFO)
    results = executor.execute(orders)
    assert len(results) == 1
    req = results[0]
    assert isinstance(req, MarketOrderRequest)
    assert req.order_class == OrderClass.MLEG
    # Verify dry-run log message
    assert any('DRY RUN: Multi-leg order' in message for message in caplog.messages)


def test_retry_logic(monkeypatch):
    """
    Test that retry logic attempts submission up to 3 times upon failures.
    """
    class FakeClientRetry:
        def __init__(self, api_key, secret_key, paper=False, url_override=None):
            self.attempts = 0
        def submit_order(self, req):
            self.attempts += 1
            if self.attempts < 3:
                raise RuntimeError('submission failed')
            return req

    # Override TradingClient to use the retry client
    monkeypatch.setattr(trade_executor, 'TradingClient', FakeClientRetry)
    executor = TradeExecutor()
    orders = [{
        'symbol': 'TST',
        'qty': 1,
        'side': 'buy',
        'type': 'market',
        'time_in_force': 'day',
    }]
    results = executor.execute(orders)
    # Should succeed on 3rd attempt
    assert len(results) == 1
    req = results[0]
    assert isinstance(req, MarketOrderRequest)
    # Ensure that submit_order was called 3 times
    assert executor.client.attempts == 3

    # Simulate API failure: use FakeClientThrow
    monkeypatch.setattr(trade_executor, 'TradingClient', FakeClientThrow)
    executor = TradeExecutor()
    orders = [{
        'symbol': 'ERROR', 'qty': 1, 'side': 'buy', 'type': 'market', 'time_in_force': 'day'
    }]
    # Should catch the exception and return empty results
    results = executor.execute(orders)
    assert results == []
