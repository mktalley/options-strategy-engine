import logging
from typing import List, Dict
from alpaca.trading.requests import StopLossRequest, TakeProfitRequest


class RiskManager:
    """
    Risk management module: apply trailing stops, volatility-based position sizing,
    and dynamic stop-loss/profit targets.
    """
    def __init__(self, atr_period: int = 14, stop_loss_pct: float = 0.02, take_profit_pct: float = 0.04):
        self.atr_period = atr_period
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct

    def adjust_orders(self, orders: List[Dict], data: Dict) -> List[Dict]:
        """
        Modify orders to include risk management parameters (e.g., attach trailing stops).
        Stub implementation returns orders unchanged.
        """
                # Single order risk adjustments only
        if not orders:
            return []
        # Skip multi-leg orders (handled separately)
        if len(orders) > 1:
            logging.info('RiskManager: skipping multi-leg orders')
            return orders
        order = orders[0].copy()
        # Volatility-based position sizing: scale qty inversely with iv (capped)
        iv = data.get('iv', 0.0)
        base_qty = order.get('qty', 1)
        # Scale factor: reduce size if iv high; factor = max(0.1, 1 - iv)
        factor = max(0.1, 1 - iv)
        new_qty = max(1, int(base_qty * factor))
        order['qty'] = new_qty
        # Dynamic stop-loss and take-profit based on percentage of current price
        price = data.get('price') or 0.0
        side = order.get('side', '').lower()
        if side == 'buy':
            stop_price = round(price * (1 - self.stop_loss_pct), 2)
            profit_price = round(price * (1 + self.take_profit_pct), 2)
        else:
            stop_price = round(price * (1 + self.stop_loss_pct), 2)
            profit_price = round(price * (1 - self.take_profit_pct), 2)
        # Attach StopLoss and TakeProfit requests
        order['stop_loss'] = StopLossRequest(stop_price=stop_price)
        order['take_profit'] = TakeProfitRequest(limit_price=profit_price)
        return [order]
