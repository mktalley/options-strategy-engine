import logging
from typing import List, Dict, Any
from utils import format_option_symbol
from datetime import date, timedelta

class Strategy:
    phase = 1
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
    phase = 2
    @classmethod
    def score(cls, data: Dict[str, Any]) -> float:
        """
        Score Bull Call Spread: bullish trend (+2) and low IV (+1).
        """
        trend = data.get('trend')
        momentum = data.get('momentum')
        iv = data.get('iv', 0.0)
        iv_th = data.get('iv_threshold', 0.25)
        score = 0.0
        if trend == 'bullish' and momentum == 'positive':
            score += 2.0
        if iv < iv_th:
            score += 1.0
        return score

    def run(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Execute Bull Call Spread: buy ATM call, sell OTM call (width=2) when bullish.
        """
        trend = data.get('trend')
        if trend != 'bullish':
            logging.info(f"BullCallSpread: trend not bullish ({trend}); no orders.")
            return []
        ticker = data['ticker']
        price = data['price']
        expiration = data['expiration']  # type: date
        atm = round(price)
        width = 2
        buy_strike = atm
        sell_strike = atm + width
        orders: List[Dict[str, Any]] = []
        legs = [
            (buy_strike, 'call', 'buy'),
            (sell_strike, 'call', 'sell'),
        ]
        for strike, opt_type, side in legs:
            if strike <= 0:
                logging.error("Invalid strike for BullCallSpread: %s", strike)
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
            logging.info(f"BullCallSpread leg {opt_type} {side}: {order}")
        return orders

class BearPutSpread(Strategy):
    @classmethod
    def score(cls, data: Dict[str, Any]) -> float:
        """
        Score Bear Put Spread: bearish trend (+2) and low IV (+1).
        """
        trend = data.get('trend')
        momentum = data.get('momentum')
        iv = data.get('iv', 0.0)
        iv_th = data.get('iv_threshold', 0.25)
        score = 0.0
        if trend == 'bearish' and momentum == 'negative':
            score += 2.0
        if iv < iv_th:
            score += 1.0
        return score

    def run(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Execute Bear Put Spread: buy ATM put, sell OTM put (width=2) when bearish.
        """
        trend = data.get('trend')
        if trend != 'bearish':
            logging.info(f"BearPutSpread: trend not bearish ({trend}); no orders.")
            return []
        ticker = data['ticker']
        price = data['price']
        expiration = data['expiration']  # type: date
        atm = round(price)
        width = 2
        buy_strike = atm
        sell_strike = atm - width
        orders: List[Dict[str, Any]] = []
        legs = [
            (buy_strike, 'put', 'buy'),
            (sell_strike, 'put', 'sell'),
        ]
        for strike, opt_type, side in legs:
            if strike <= 0:
                logging.error("Invalid strike for BearPutSpread: %s", strike)
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
            logging.info(f"BearPutSpread leg {opt_type} {side}: {order}")
        return orders

class CalendarSpread(Strategy):
    phase = 2

    @classmethod
    def score(cls, data: Dict[str, Any]) -> float:
        """
        Score Calendar Spread: neutral trend (+2); add +1 for low IV or (for bearish) high IV.
        """
        trend = data.get('trend')
        iv = data.get('iv', 0.0)
        iv_th = data.get('iv_threshold', 0.25)
        score = 0.0
        # Trend bias
        if trend == 'neutral':
            score += 2.0
        # IV bias: low IV always +1; high IV favorable if bearish
        if iv < iv_th or (trend == 'bearish' and iv >= iv_th):
            score += 1.0
        return score

    def run(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Execute Calendar Spread: buy far-term ATM call, sell near-term ATM call when neutral.
        """
        trend = data.get('trend')
        if trend != 'neutral':
            logging.info(f"CalendarSpread: trend not neutral ({trend}); no orders.")
            return []
        ticker = data['ticker']
        price = data['price']
        near_exp = data['expiration']  # type: date
        far_exp = near_exp + timedelta(days=7)
        atm = round(price)
        orders: List[Dict[str, Any]] = []
        legs = [
            (atm, 'call', 'buy', far_exp),
            (atm, 'call', 'sell', near_exp),
        ]
        for strike, opt_type, side, exp in legs:
            if strike <= 0:
                logging.error("Invalid strike for CalendarSpread: %s", strike)
                continue
            symbol = format_option_symbol(ticker, exp, strike, opt_type)
            order = {
                'symbol': symbol,
                'qty': 1,
                'side': side,
                'type': 'market',
                'time_in_force': 'day'
            }
            orders.append(order)
            logging.info(f"CalendarSpread leg {opt_type} {side} exp={exp}: {order}")
        return orders

class IronButterfly(Strategy):
    @classmethod
    def score(cls, data: Dict[str, Any]) -> float:
        """
        Score Iron Butterfly: neutral trend (+2); +1 for IV alignment (high for bullish/neutral, low for bearish).
        """
        trend = data.get('trend')
        iv = data.get('iv', 0.0)
        iv_th = data.get('iv_threshold', 0.25)
        score = 0.0
        # Trend bias
        if trend == 'neutral':
            score += 2.0
        # IV bias: high IV benefits bullish/neutral, low IV benefits bearish
        if (trend != 'bearish' and iv >= iv_th) or (trend == 'bearish' and iv < iv_th):
            score += 1.0
        return score

    def run(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Execute Iron Butterfly: buy wings and sell wings at ATM when neutral.
        Legs: buy put at ATM-width, sell put at ATM, sell call at ATM, buy call at ATM+width.
        """
        trend = data.get('trend')
        if trend != 'neutral':
            logging.info(f"IronButterfly: trend not neutral ({trend}); no orders.")
            return []
        ticker = data['ticker']
        price = data['price']
        expiration = data['expiration']  # type: date
        atm = round(price)
        width = 2
        legs = [
            (atm - width, 'put', 'buy'),
            (atm, 'put', 'sell'),
            (atm, 'call', 'sell'),
            (atm + width, 'call', 'buy'),
        ]
        orders: List[Dict[str, Any]] = []
        for strike, opt_type, side in legs:
            if strike <= 0:
                logging.error("Invalid strike for IronButterfly: %s", strike)
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
            logging.info(f"IronButterfly leg {opt_type} {side}: {order}")
        return orders

class GammaScalping(Strategy):
    phase = 2
    @classmethod
    def score(cls, data: Dict[str, Any]) -> float:
        return _default_score(data)

    def run(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Gamma Scalping: buy ATM call and put (straddle) to capture gamma when momentum is neutral to positive.
        """
        ticker = data['ticker']
        price = data['price']
        expiration = data['expiration']  # type: date
        atm = round(price)
        # Buy straddle
        orders: List[Dict[str, Any]] = []
        for opt_type in ('call', 'put'):
            symbol = format_option_symbol(ticker, expiration, atm, opt_type)
            order = {
                'symbol': symbol,
                'qty': 1,
                'side': 'buy',
                'type': 'market',
                'time_in_force': 'day'
            }
            orders.append(order)
            logging.info(f"GammaScalping {opt_type} buy: {order}")
        return orders

class Wheel(Strategy):
    phase = 2
    """
    Wheel strategy: cash-secured put: sell one OTM put when trend is bullish and momentum is positive.
    """
    @classmethod
    def score(cls, data: Dict[str, Any]) -> float:
        trend = data.get('trend')
        momentum = data.get('momentum')
        iv = data.get('iv', 0.0)
        iv_th = data.get('iv_threshold', 0.25)
        score = 0.0
        if trend == 'bullish' and momentum == 'positive':
            score += 2.0
        # Benefit from higher IV when selling premium
        if iv >= iv_th:
            score += 1.0
        return score

    def run(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        trend = data.get('trend')
        momentum = data.get('momentum')
        if trend != 'bullish' or momentum != 'positive':
            logging.info(f"Wheel: requires bullish trend and positive momentum; got {trend}, {momentum}")
            return []
        ticker = data['ticker']
        price = data['price']
        expiration = data['expiration']  # type: date
        atm = round(price)
        width = 2  # OTM distance
        strike = atm - width
        if strike <= 0:
            logging.error(f"Wheel: invalid strike {strike}")
            return []
        symbol = format_option_symbol(ticker, expiration, strike, 'put')
        order = {
            'symbol': symbol,
            'qty': 1,
            'side': 'sell',
            'type': 'market',
            'time_in_force': 'day'
        }
        logging.info(f"Wheel sell put: {order}")
        return [order]

class ZeroDTE(Strategy):
    phase = 2
    """
    Zero-Day-To-Expiration strategy: buy ATM call on positive momentum or ATM put on negative momentum on expiration day.
    """
    @classmethod
    def score(cls, data: Dict[str, Any]) -> float:
        exp = data.get('expiration')  # type: date
        today = date.today()
        iv = data.get('iv', 0.0)
        iv_th = data.get('iv_threshold', 0.25)
        momentum = data.get('momentum')
        score = 0.0
        # Only score on expiration day
        if exp == today:
            if momentum in ('positive', 'negative'):
                score += 2.0
            if iv < iv_th:
                score += 1.0
        return score

    def run(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        exp = data.get('expiration')  # type: date
        today = date.today()
        if exp != today:
            logging.info(f"ZeroDTE: not expiration day ({exp}); no orders.")
            return []
        ticker = data['ticker']
        price = data['price']
        atm = round(price)
        momentum = data.get('momentum')
        if momentum == 'positive':
            opt_type = 'call'
        elif momentum == 'negative':
            opt_type = 'put'
        else:
            logging.info(f"ZeroDTE: neutral momentum; no orders.")
            return []
        symbol = format_option_symbol(ticker, exp, atm, opt_type)
        order = {
            'symbol': symbol,
            'qty': 1,
            'side': 'buy',
            'type': 'market',
            'time_in_force': 'day'
        }
        logging.info(f"ZeroDTE buy {opt_type}: {order}")
        return [order]


class Strangle(Strategy):
    phase = 2
    """
    Strangle strategy: buy OTM call and put when trend is neutral and IV is low.
    """
    @classmethod
    def score(cls, data: Dict[str, Any]) -> float:
        trend = data.get('trend')
        iv = data.get('iv', 0.0)
        iv_th = data.get('iv_threshold', 0.25)
        score = 0.0
        if trend == 'neutral':
            score += 1.0
            if iv < iv_th:
                score += 1.0
        return score

    def run(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        trend = data.get('trend')
        if trend != 'neutral':
            logging.info(f"Strangle: requires neutral trend; got {trend}")
            return []
        ticker = data['ticker']
        price = data['price']
        expiration = data['expiration']  # type: date
        atm = round(price)
        width = 2  # OTM distance
        call_strike = atm + width
        put_strike = atm - width
        if put_strike <= 0:
            logging.error(f"Strangle: invalid put strike {put_strike}")
            return []
        orders: List[Dict[str, Any]] = []
        legs = [
            (put_strike, 'put', 'buy'),
            (call_strike, 'call', 'buy'),
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
            logging.info(f"Strangle {opt_type} buy: {order}")
        return orders


class ShortStraddle(Strategy):
    phase = 2
    """
    Short Straddle strategy: sell ATM call and put when trend is neutral and IV is high.
    """
    @classmethod
    def score(cls, data: Dict[str, Any]) -> float:
        trend = data.get('trend')
        iv = data.get('iv', 0.0)
        iv_th = data.get('iv_threshold', 0.25)
        score = 0.0
        if trend == 'neutral':
            score += 1.0
            if iv >= iv_th:
                score += 1.0
        return score

    def run(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        trend = data.get('trend')
        if trend != 'neutral':
            logging.info(f"ShortStraddle: requires neutral trend; got {trend}")
            return []
        ticker = data['ticker']
        price = data['price']
        expiration = data['expiration']  # type: date
        atm = round(price)
        orders: List[Dict[str, Any]] = []
        for opt_type in ['put', 'call']:
            symbol = format_option_symbol(ticker, expiration, atm, opt_type)
            order = {
                'symbol': symbol,
                'qty': 1,
                'side': 'sell',
                'type': 'market',
                'time_in_force': 'day'
            }
            orders.append(order)
            logging.info(f"ShortStraddle {opt_type} sell: {order}")
        return orders


class CoveredCall(Strategy):
    phase = 2
    """
    Covered Call strategy: sell ATM call when trend is bullish and momentum is positive, and IV is high.
    """
    @classmethod
    def score(cls, data: Dict[str, Any]) -> float:
        trend = data.get('trend')
        momentum = data.get('momentum')
        iv = data.get('iv', 0.0)
        iv_th = data.get('iv_threshold', 0.25)
        score = 0.0
        if trend == 'bullish' and momentum == 'positive':
            score += 2.0
        if iv >= iv_th:
            score += 1.0
        return score

    def run(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        trend = data.get('trend')
        momentum = data.get('momentum')
        if trend != 'bullish' or momentum != 'positive':
            logging.info(f"CoveredCall: requires bullish positive momentum; got {trend}, {momentum}")
            return []
        ticker = data['ticker']
        price = data['price']
        expiration = data['expiration']  # type: date
        atm = round(price)
        symbol = format_option_symbol(ticker, expiration, atm, 'call')
        order = {
            'symbol': symbol,
            'qty': 1,
            'side': 'sell',
            'type': 'market',
            'time_in_force': 'day'
        }
        logging.info(f"CoveredCall sell call: {order}")
        return [order]


class ProtectivePut(Strategy):
    phase = 2
    """
    Protective Put strategy: buy ATM put when trend is bearish and momentum is negative, and IV is high.
    """
    @classmethod
    def score(cls, data: Dict[str, Any]) -> float:
        trend = data.get('trend')
        momentum = data.get('momentum')
        iv = data.get('iv', 0.0)
        iv_th = data.get('iv_threshold', 0.25)
        score = 0.0
        if trend == 'bearish' and momentum == 'negative':
            score += 2.0
        if iv >= iv_th:
            score += 1.0
        return score

    def run(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        trend = data.get('trend')
        momentum = data.get('momentum')
        if trend != 'bearish' or momentum != 'negative':
            logging.info(f"ProtectivePut: requires bearish negative momentum; got {trend}, {momentum}")
            return []
        ticker = data['ticker']
        price = data['price']
        expiration = data['expiration']  # type: date
        atm = round(price)
        symbol = format_option_symbol(ticker, expiration, atm, 'put')
        order = {
            'symbol': symbol,
            'qty': 1,
            'side': 'buy',
            'type': 'market',
            'time_in_force': 'day'
        }
        logging.info(f"ProtectivePut buy put: {order}")
        return [order]




class RatioBackspread(Strategy):
    phase = 2
    """
    Ratio Backspread strategy: sell 1 ATM option and buy 2 OTM options when directional trend and low IV.
    Supports calls on bullish momentum, puts on bearish momentum.
    """
    @classmethod
    def score(cls, data: Dict[str, Any]) -> float:
        trend = data.get('trend')
        momentum = data.get('momentum')
        iv = data.get('iv', 0.0)
        iv_th = data.get('iv_threshold', 0.25)
        score = 0.0
        # directional move
        if trend == 'bullish' and momentum == 'positive':
            score += 2.0
        elif trend == 'bearish' and momentum == 'negative':
            score += 2.0
        # buy when IV low
        if iv < iv_th:
            score += 1.0
        return score

    def run(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        momentum = data.get('momentum')
        ticker = data['ticker']
        price = data['price']
        expiration = data['expiration']  # type: date
        atm = round(price)
        width = 2
        orders: List[Dict[str, Any]] = []
        if momentum == 'positive':
            # call backspread
            sell_strike = atm
            buy_strike = atm + width
            legs = [
                (sell_strike, 'call', 'sell'),
                (buy_strike, 'call', 'buy'),
                (buy_strike, 'call', 'buy'),
            ]
        elif momentum == 'negative':
            # put backspread
            sell_strike = atm
            buy_strike = atm - width
            if buy_strike <= 0:
                logging.error(f"RatioBackspread: invalid put strike {buy_strike}")
                return []
            legs = [
                (sell_strike, 'put', 'sell'),
                (buy_strike, 'put', 'buy'),
                (buy_strike, 'put', 'buy'),
            ]
        else:
            logging.info(f"RatioBackspread: requires directional momentum; got {momentum}")
            return []
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
            logging.info(f"RatioBackspread {opt_type} {side}: {order}")
        return orders


class Collar(Strategy):
    phase = 2
    """
    Collar strategy: buy protective put and sell covered call when trend is neutral and IV is high.
    """
    @classmethod
    def score(cls, data: Dict[str, Any]) -> float:
        trend = data.get('trend')
        iv = data.get('iv', 0.0)
        iv_th = data.get('iv_threshold', 0.25)
        score = 0.0
        if trend == 'neutral':
            score += 2.0
        if iv >= iv_th:
            score += 1.0
        return score

    def run(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        trend = data.get('trend')
        if trend != 'neutral':
            logging.info(f"Collar: requires neutral trend; got {trend}")
            return []
        ticker = data['ticker']
        price = data['price']
        expiration = data['expiration']  # type: date
        atm = round(price)
        width = 2
        put_strike = atm - width
        call_strike = atm + width
        if put_strike <= 0:
            logging.error(f"Collar: invalid put strike {put_strike}")
            return []
        orders: List[Dict[str, Any]] = []
        # sell call
        symbol_call = format_option_symbol(ticker, expiration, call_strike, 'call')
        orders.append({
            'symbol': symbol_call,
            'qty': 1,
            'side': 'sell',
            'type': 'market',
            'time_in_force': 'day'
        })
        logging.info(f"Collar sell call: {orders[-1]}")
        # buy put
        symbol_put = format_option_symbol(ticker, expiration, put_strike, 'put')
        orders.append({
            'symbol': symbol_put,
            'qty': 1,
            'side': 'buy',
            'type': 'market',
            'time_in_force': 'day'
        })
        logging.info(f"Collar buy put: {orders[-1]}")
        return orders



