from typing import Dict


class NewsManager:
    """
    News and economic calendar risk filter.
    """
    def __init__(self):
        # Placeholder for calendar feed initialization
        pass

    def is_trade_allowed(self, symbol: str, data: Dict) -> bool:
        """
        Check economic calendar and news sentiment for the symbol.
        Return False to skip trading if high-impact event or extreme sentiment.
        Stub: always allow.
        """
        # TODO: integrate calendar API and sentiment analysis
        return True
