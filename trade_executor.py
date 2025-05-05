import os
import logging
from typing import List, Any
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest, OptionLegRequest
from alpaca.trading.enums import OrderSide, OrderType, TimeInForce, OrderClass
from tenacity import retry, stop_after_attempt, wait_fixed

class TradeExecutor:
    """
    Executes option orders via Alpaca API (paper trading mode), with retry logic and optional dry-run mode.
    """
    def __init__(self, dry_run: bool = False):
        """
        Initialize TradeExecutor.

        dry_run: if True, skip actual order submissions.
        """
        self.dry_run = dry_run
        api_key = os.getenv('ALPACA_API_KEY')
        secret_key = os.getenv('ALPACA_SECRET_KEY')
        if not api_key or not secret_key:
            logging.error('Alpaca API credentials not found in environment variables.')
            raise ValueError('Missing Alpaca API credentials')
        # Initialize Alpaca Trading Client in paper mode
        # Initialize Alpaca Trading Client in paper mode
        # Use ALPACA_API_BASE_URL override if provided
        base_url = os.getenv('ALPACA_API_BASE_URL')
        # paper=True ensures paper trading endpoint is used
        # If base_url is set, pass it as url_override
        self.client = TradingClient(
            api_key,
            secret_key,
            paper=True,
            url_override=base_url if base_url else None
        )

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
    def _submit(self, req):
        """
        Submit the order with retry logic applied.
        """
        return self.client.submit_order(req)


    def execute(self, orders: List[dict]) -> List[Any]:
        """
        Submit a list of option or stock orders.

        For multi-leg option strategies (more than one order), submits as a single multi-leg order (mleg).
        For single orders, submits a market order.

        orders: list of dicts with keys: symbol, qty, side, type, time_in_force
        Returns list of API responses for successful orders.
        """
        results = []
        if not orders:
            return results

        if len(orders) > 1:
            try:
                # Multi-leg option order
                qty = orders[0]['qty']
                tif = TimeInForce(orders[0]['time_in_force'])
                legs: List[OptionLegRequest] = []
                for o in orders:
                    legs.append(OptionLegRequest(
                        symbol=o['symbol'],
                        ratio_qty=o['qty'],
                        side=OrderSide(o['side'])
                    ))
                req = MarketOrderRequest(
                    qty=qty,
                    time_in_force=tif,
                    order_class=OrderClass.MLEG,
                    legs=legs
                )
                symbols = [o['symbol'] for o in orders]
                if self.dry_run:
                    logging.info(f"DRY RUN: Multi-leg order, symbols={symbols}, request={req}")
                    results.append(req)
                else:
                    resp = self._submit(req)
                    logging.info(f"Multi-leg order submitted: {symbols}")
                    results.append(resp)
            except Exception as e:
                logging.error(f"Failed to submit multi-leg order {orders}: {e}")
            return results

        for order in orders:
            try:
                req = MarketOrderRequest(
                    symbol=order['symbol'],
                    qty=order['qty'],
                    side=OrderSide(order['side']),
                    type=OrderType(order['type']),
                    time_in_force=TimeInForce(order['time_in_force'])
                )
                if self.dry_run:
                    logging.info(f"DRY RUN: Single order request: {req}")
                    results.append(req)
                else:
                    resp = self._submit(req)
                    logging.info(f"Order submitted: {order['symbol']} side={order['side']} qty={order['qty']}")
                    results.append(resp)
            except Exception as e:
                logging.error(f"Failed to submit order {order}: {e}")
        return results
