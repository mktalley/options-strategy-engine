import logging
import pytest
from risk_manager import RiskManager
from alpaca.trading.requests import StopLossRequest, TakeProfitRequest


def test_empty_orders():
    rm = RiskManager()
    # No orders should return empty list
    assert rm.adjust_orders([], {}) == []


def test_skip_multi_leg_orders(caplog):
    rm = RiskManager()
    orders = [
        {'symbol': 'A', 'qty': 1, 'side': 'buy', 'type': 'market', 'time_in_force': 'day'},
        {'symbol': 'B', 'qty': 1, 'side': 'sell', 'type': 'market', 'time_in_force': 'day'}
    ]
    caplog.set_level(logging.INFO)
    result = rm.adjust_orders(orders, {'iv': 0.0, 'price': 100.0})
    # Should return original orders unchanged
    assert result == orders
    assert 'skipping multi-leg orders' in caplog.text.lower()


def test_adjust_single_buy_order():
    # Setup with custom stop-loss and take-profit percentages
    rm = RiskManager(stop_loss_pct=0.1, take_profit_pct=0.2)
    order = {
        'symbol': 'ABC', 'qty': 4, 'side': 'buy', 'type': 'market', 'time_in_force': 'day'
    }
    data = {'iv': 0.5, 'price': 100.0}
    result = rm.adjust_orders([order], data)
    assert isinstance(result, list) and len(result) == 1
    o = result[0]
    # Volatility-based sizing: factor = 1 - iv = 0.5, new_qty = int(4 * 0.5) = 2
    assert o['qty'] == 2
    # Stop-loss and take-profit attached
    assert isinstance(o.get('stop_loss'), StopLossRequest)
    assert isinstance(o.get('take_profit'), TakeProfitRequest)
    # Check price levels: stop at 90.0, profit at 120.0
    assert o['stop_loss'].stop_price == 90.0
    assert o['take_profit'].limit_price == 120.0
    # Symbol and side preserved
    assert o['symbol'] == 'ABC' and o['side'] == 'buy'


def test_adjust_single_sell_order():
    rm = RiskManager(stop_loss_pct=0.1, take_profit_pct=0.2)
    order = {
        'symbol': 'XYZ', 'qty': 5, 'side': 'sell', 'type': 'market', 'time_in_force': 'day'
    }
    data = {'iv': 0.2, 'price': 50.0}
    result = rm.adjust_orders([order], data)
    assert len(result) == 1
    o = result[0]
    # factor = 1 - iv = 0.8, new_qty = int(5 * 0.8) = 4
    assert o['qty'] == 4
    # Stop-loss for sell: price * (1 + stop_loss_pct) = 55.0
    assert pytest.approx(o['stop_loss'].stop_price, rel=1e-6) == 55.0
    # Take-profit for sell: price * (1 - take_profit_pct) = 40.0
    assert pytest.approx(o['take_profit'].limit_price, rel=1e-6) == 40.0


def test_volatility_sizing_floor():
    rm = RiskManager()
    order = {'symbol': 'FLR', 'qty': 10, 'side': 'buy', 'type': 'market', 'time_in_force': 'day'}
    data = {'iv': 0.95, 'price': 100.0, 'close_prices': []}
    result = rm.adjust_orders([order], data)
    assert len(result) == 1
    o = result[0]
    # High IV should floor factor at 0.1, new_qty = int(10 * 0.1) = 1
    assert o['qty'] == 1


def test_atr_based_dynamic_stops_buy():
    # ATR-based stops for buy side
    rm = RiskManager(atr_period=3, atr_stop_multiplier=2, atr_take_profit_multiplier=3)
    order = {'symbol': 'ATRBUY', 'qty': 5, 'side': 'buy', 'type': 'market', 'time_in_force': 'day'}
    # close_prices with constant 10-point moves
    close = [100, 110, 120, 130, 140]
    data = {'iv': 0.0, 'price': 200.0, 'close_prices': close}
    result = rm.adjust_orders([order], data)
    assert len(result) == 1
    o = result[0]
    # ATR = 10, stop = 200 - 2*10 = 180, profit = 200 + 3*10 = 230
    assert o['stop_loss'].stop_price == 180.0
    assert o['take_profit'].limit_price == 230.0


def test_atr_based_dynamic_stops_sell():
    # ATR-based stops for sell side
    rm = RiskManager(atr_period=3, atr_stop_multiplier=1, atr_take_profit_multiplier=2)
    order = {'symbol': 'ATRSELL', 'qty': 3, 'side': 'sell', 'type': 'market', 'time_in_force': 'day'}
    close = [50, 60, 70, 80]
    data = {'iv': 0.0, 'price': 50.0, 'close_prices': close}
    result = rm.adjust_orders([order], data)
    o = result[0]
    # ATR = 10, stop = 50 + 1*10 = 60, profit = 50 - 2*10 = 30
    assert pytest.approx(o['stop_loss'].stop_price, rel=1e-6) == 60.0
    assert pytest.approx(o['take_profit'].limit_price, rel=1e-6) == 30.0


def test_trailing_stop_flag_attached():
    rm = RiskManager(trailing_stop_pct=0.05)
    order = {'symbol': 'TRAIL', 'qty': 2, 'side': 'buy', 'type': 'market', 'time_in_force': 'day'}
    data = {'iv': 0.0, 'price': 100.0, 'close_prices': [90, 95, 100]}
    result = rm.adjust_orders([order], data)
    o = result[0]
    assert 'trailing_stop_pct' in o
    assert o['trailing_stop_pct'] == 0.05

