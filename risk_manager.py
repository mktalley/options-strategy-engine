import logging
from typing import List, Dict
from alpaca.trading.requests import StopLossRequest, TakeProfitRequest

class RiskManager:
    """
    Risk management module: apply trailing stops, volatility-based position sizing,
    and dynamic stop-loss/profit targets.
    """
    def __init__(self,
                 atr_period: int = 14,
                 stop_loss_pct: float = 0.01,
                 take_profit_pct: float = 0.08,
                 atr_stop_multiplier: float = 1.5,
                 atr_take_profit_multiplier: float = 2.5,
                 trailing_stop_pct: float = 0.02):
        self.atr_period = atr_period
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct
        self.atr_stop_multiplier = atr_stop_multiplier
        self.atr_take_profit_multiplier = atr_take_profit_multiplier
        self.trailing_stop_pct = trailing_stop_pct

    def adjust_orders(self, orders: List[Dict], data: Dict) -> List[Dict]:
        """
        Modify orders to include risk management parameters (e.g., attach trailing stops),
        refine position sizing, and set dynamic stop-loss and take-profit.
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
        factor = max(0.1, 1 - iv)
        new_qty = max(1, int(base_qty * factor))
        order['qty'] = new_qty

        # Market price and side
        price = data.get('price') or 0.0
        side = order.get('side', '').lower()

        # Compute ATR if multipliers specified
        close_prices = data.get('close_prices', [])
        atr = None
        if (self.atr_stop_multiplier > 0 or self.atr_take_profit_multiplier > 0) and len(close_prices) > self.atr_period:
            diffs = [abs(close_prices[i] - close_prices[i-1]) for i in range(1, len(close_prices))]
            recent = diffs[-self.atr_period:]
            if recent:
                atr = sum(recent) / len(recent)

        # Determine stop-loss and take-profit
        if atr is not None:
            # ATR-based dynamic stops
            if side == 'buy':
                stop_price = round(price - self.atr_stop_multiplier * atr, 2)
                profit_price = round(price + self.atr_take_profit_multiplier * atr, 2)
            else:
                stop_price = round(price + self.atr_stop_multiplier * atr, 2)
                profit_price = round(price - self.atr_take_profit_multiplier * atr, 2)
        else:
            # Static percentage-based stops
            if side == 'buy':
                stop_price = round(price * (1 - self.stop_loss_pct), 2)
                profit_price = round(price * (1 + self.take_profit_pct), 2)
            else:
                stop_price = round(price * (1 + self.stop_loss_pct), 2)
                profit_price = round(price * (1 - self.take_profit_pct), 2)

        # Attach StopLoss and TakeProfit requests
        order['stop_loss'] = StopLossRequest(stop_price=stop_price)
        order['take_profit'] = TakeProfitRequest(limit_price=profit_price)

        # Trailing stop flag for downstream handling
        if self.trailing_stop_pct and side:
            order['trailing_stop_pct'] = self.trailing_stop_pct

        return [order]
