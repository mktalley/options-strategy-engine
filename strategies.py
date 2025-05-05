import logging
from typing import List, Dict, Any
from utils import format_option_symbol
from datetime import date

class Strategy:
    """
    Base class for options trading strategies.
    """
    @classmethod
    def score(cls, data: Dict[str, Any]) -> float:
        """Default scoring method: override in subclasses."""
        return 0.0

    def run(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Given market data and metrics, returns list of order parameter dicts.
        """
        raise NotImplementedError

class LongCall(Strategy):
    @classmethod
    def score(cls, data: Dict[str, Any]) -> float:
        trend = data['trend']
        iv = data['iv']
        momentum = data['momentum']
        iv_th = data['iv_threshold']
        score = 0
        if trend == 'bullish' and momentum == 'positive':
            score += 2
        if iv < iv_th:
            score += 1
        return score

    def run(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        ticker = data['ticker']
        price = data['price']
        expiration = data['expiration']  # type: date
        strike = round(price)
        symbol = format_option_symbol(ticker, expiration, strike, 'call')
        order = {
            'symbol': symbol,
            'qty': 1,
            'side': 'buy',
            'type': 'market',
            'time_in_force': 'day'
        }
        logging.info(f"LongCall: {order}")
        return [order]

class LongPut(Strategy):
    @classmethod
    def score(cls, data: Dict[str, Any]) -> float:
        trend = data['trend']
        iv = data['iv']
        momentum = data['momentum']
        iv_th = data['iv_threshold']
        score = 0
        if trend == 'bearish' and momentum == 'negative':
            score += 2
        if iv < iv_th:
            score += 1
        return score

    def run(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        ticker = data['ticker']
        price = data['price']
        expiration = data['expiration']  # type: date
        strike = round(price)
        symbol = format_option_symbol(ticker, expiration, strike, 'put')
        order = {
            'symbol': symbol,
            'qty': 1,
            'side': 'buy',
            'type': 'market',
            'time_in_force': 'day'
        }
        logging.info(f"LongPut: {order}")
        return [order]

class Straddle(Strategy):
    @classmethod
    def score(cls, data: Dict[str, Any]) -> float:
        trend = data['trend']
        iv = data['iv']
        iv_th = data['iv_threshold']
        score = 0
        if trend == 'neutral':
            score += 1
            if iv < iv_th:
                score += 1
        return score

    def run(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        ticker = data['ticker']
        price = data['price']
        expiration = data['expiration']  # type: date
        strike = round(price)
        orders = []
        for opt_type in ['call', 'put']:
            symbol = format_option_symbol(ticker, expiration, strike, opt_type)
            order = {
                'symbol': symbol,
                'qty': 1,
                'side': 'buy',
                'type': 'market',
                'time_in_force': 'day'
            }
            orders.append(order)
            logging.info(f"Straddle {opt_type}: {order}")
        return orders

class IronCondor(Strategy):
    @classmethod
    def score(cls, data: Dict[str, Any]) -> float:
        trend = data['trend']
        iv = data['iv']
        iv_th = data['iv_threshold']
        score = 0
        if trend == 'neutral':
            score += 1
            if iv >= iv_th:
                score += 2
        return score

    def run(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        ticker = data['ticker']
        price = data['price']
        expiration = data['expiration']  # type: date
        atm = round(price)
        put_sell = atm - 2
        put_buy = atm - 4
        call_sell = atm + 2
        call_buy = atm + 4
        for s in [put_buy, put_sell, call_sell, call_buy]:
            if s <= 0:
                logging.error("Invalid strike generated for IronCondor")
                return []
        orders = []
        legs = [
            (put_buy, 'put', 'buy'),
            (put_sell, 'put', 'sell'),
            (call_sell, 'call', 'sell'),
            (call_buy, 'call', 'buy'),
        ]
        for strike, opt_type, side in legs:
            symbol = format_option_symbol(ticker, expiration, strike, opt_type)
            order = {
                'symbol': symbol,
                'qty': 1,
                'side': side,
                'type': 'market',
                'time_in_force': 'day'
            }
            orders.append(order)
            logging.info(f"IronCondor leg {opt_type} {side}: {order}")
        return orders

class VerticalSpread(Strategy):
    @classmethod
    def score(cls, data: Dict[str, Any]) -> float:
        # fallback baseline score
        return 0.5

    def run(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        ticker = data['ticker']
        price = data['price']
        expiration = data['expiration']  # type: date
        atm = round(price)
        trend = data.get('trend', 'neutral')
        orders = []
        if trend == 'bullish':
            buy_strike, sell_strike = atm, atm + 2
            buy_leg = (buy_strike, 'call', 'buy')
            sell_leg = (sell_strike, 'call', 'sell')
        elif trend == 'bearish':
            buy_strike, sell_strike = atm, atm - 2
            buy_leg = (buy_strike, 'put', 'buy')
            sell_leg = (sell_strike, 'put', 'sell')
        else:
            buy_strike, sell_strike = atm, atm + 2
            buy_leg = (buy_strike, 'call', 'buy')
            sell_leg = (sell_strike, 'call', 'sell')
        for strike, opt_type, side in [buy_leg, sell_leg]:
            if strike <= 0:
                logging.error("Invalid strike for VerticalSpread: %s", strike)
                continue
            symbol = format_option_symbol(ticker, expiration, strike, opt_type)
            order = {
                'symbol': symbol,
                'qty': 1,
                'side': side,
                'type': 'market',
                'time_in_force': 'day'
            }
            orders.append(order)
            logging.info(f"VerticalSpread leg {opt_type} {side}: {order}")
        return orders

# Phase-2 strategy stubs

def _default_score(data: Dict[str, Any]) -> float:
    """Baseline scoring: no tilt in either direction."""
    return 0.0

class BullCallSpread(Strategy):
    @classmethod
    def score(cls, data: Dict[str, Any]) -> float:
        return _default_score(data)

    def run(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        # TODO: implement Bull Call Spread logic
        logging.info("BullCallSpread is not yet implemented; returning no orders.")
        return []

class BearPutSpread(Strategy):
    @classmethod
    def score(cls, data: Dict[str, Any]) -> float:
        return _default_score(data)

    def run(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        # TODO: implement Bear Put Spread logic
        logging.info("BearPutSpread is not yet implemented; returning no orders.")
        return []

class CalendarSpread(Strategy):
    @classmethod
    def score(cls, data: Dict[str, Any]) -> float:
        return _default_score(data)

    def run(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        # TODO: implement Calendar Spread logic
        logging.info("CalendarSpread is not yet implemented; returning no orders.")
        return []

class IronButterfly(Strategy):
    @classmethod
    def score(cls, data: Dict[str, Any]) -> float:
        return _default_score(data)

    def run(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        # TODO: implement Iron Butterfly logic
        logging.info("IronButterfly is not yet implemented; returning no orders.")
        return []

class GammaScalping(Strategy):
    @classmethod
    def score(cls, data: Dict[str, Any]) -> float:
        return _default_score(data)

    def run(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        # TODO: implement Gamma Scalping logic
        logging.info("GammaScalping is not yet implemented; returning no orders.")
        return []

class Wheel(Strategy):
    @classmethod
    def score(cls, data: Dict[str, Any]) -> float:
        return _default_score(data)

    def run(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        # TODO: implement Wheel strategy logic
        logging.info("Wheel is not yet implemented; returning no orders.")
        return []

class ZeroDTE(Strategy):
    @classmethod
    def score(cls, data: Dict[str, Any]) -> float:
        return _default_score(data)

    def run(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        # TODO: implement Zero-Day-To-Expiration logic
        logging.info("ZeroDTE is not yet implemented; returning no orders.")
        return []

