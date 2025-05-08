from typing import Dict


import os
import requests
import datetime
from typing import Dict, List
from textblob import TextBlob


class NewsManager:
    """
    News and economic calendar risk filter.

    Blocks trading when high-impact events are scheduled or recent sentiment is too negative.
    """
    def __init__(self):
        # Load API keys
        self.fmp_api_key = os.getenv('ECONOMIC_CALENDAR_API_KEY')
        self.finnhub_api_key = os.getenv('FINNHUB_API_KEY')
        # Calendar lookahead (days ahead to fetch events)
        try:
            self.calendar_lookahead_days = int(os.getenv('ECONOMIC_CALENDAR_LOOKAHEAD_DAYS', '2'))
        except (TypeError, ValueError):
            self.calendar_lookahead_days = 2
        # News sentiment window (days back to fetch news)
        try:
            self.news_window_days = int(os.getenv('NEWS_SENTIMENT_WINDOW_DAYS', '1'))
        except (TypeError, ValueError):
            self.news_window_days = 1
        # Sentiment threshold
        try:
            self.sentiment_threshold = float(os.getenv('NEWS_SENTIMENT_THRESHOLD', '-0.3'))
        except (TypeError, ValueError):
            self.sentiment_threshold = -0.3
        # High-impact keywords to block on (defaults include FOMC, NFP, M&A, natural disasters, scandals, etc.)
        kw_str = os.getenv(
            'NEWS_RISK_KEYWORDS',
            'fomc,non farm,nfp,fed,layoffs,bankruptcy,ceo change,merger,acquisition,geopolitical,earthquake,hurricane,scandal'
        )
        self.keywords = [k.strip().lower() for k in kw_str.split(',') if k.strip()]
        # Cache calendar events by date
        self.calendar_events: List[Dict] = []
        self._last_event_fetch_date = None

    def _fetch_calendar_events(self):
        """
        Fetch earnings, IPO, and stock split events for today and tomorrow.
        """
        if not self.fmp_api_key:
            self.calendar_events = []
            return
        today = datetime.date.today()
        if self._last_event_fetch_date == today:
            return
        from_date = today.isoformat()
        to_date = (today + datetime.timedelta(days=self.calendar_lookahead_days)).isoformat()
        events: List[Dict] = []
        endpoints = ['earnings_calendar', 'ipo_calendar', 'stock_split_calendar']
        for endpoint in endpoints:
            url = (
                f"https://financialmodelingprep.com/api/v3/{endpoint}"  \
                f"?from={from_date}&to={to_date}&apikey={self.fmp_api_key}"
            )
            try:
                resp = requests.get(url, timeout=5)
                resp.raise_for_status()
                data = resp.json()
                if isinstance(data, list):
                    events.extend(data)
            except Exception:
                # On any failure, skip this feed
                continue
        self.calendar_events = events
        self._last_event_fetch_date = today

    def _has_calendar_event(self, symbol: str) -> bool:
        """
        Return True if there is any calendar event for the symbol in our cache.
        """
        self._fetch_calendar_events()
        for ev in self.calendar_events:
            if ev.get('symbol') == symbol:
                return True
        return False

    def _fetch_news(self, symbol: str) -> List[Dict]:
        """
        Fetch recent company news from Finnhub for the past `news_window_days` days.
        """
        if not self.finnhub_api_key:
            return []
        today = datetime.date.today()
        from_date = (today - datetime.timedelta(days=self.news_window_days)).isoformat()
        to_date = today.isoformat()
        url = (
            f"https://finnhub.io/api/v1/company-news?symbol={symbol}"
            f"&from={from_date}&to={to_date}&token={self.finnhub_api_key}"
        )
        try:
            resp = requests.get(url, timeout=5)
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, list):
                return data
        except Exception:
            pass
        return []

    def _compute_sentiment(self, text: str) -> float:
        """
        Return polarity score [-1.0, 1.0] for given text.
        """
        return TextBlob(text).sentiment.polarity

    def is_trade_allowed(self, symbol: str, data: Dict) -> bool:
        """
        Check calendar events and news sentiment to decide if trading is allowed.

        Returns False to skip trading when:
          - There is an earnings, IPO, or split event for this symbol today.
          - Recent average sentiment < threshold.
          - Headlines contain certain high-impact keywords (FOMC, NFP, Fed).
        """
        # 1) Calendar risk check
        if self._has_calendar_event(symbol):
            return False
        # 2) News sentiment check
        news_items = self._fetch_news(symbol)
        if news_items:
            scores: List[float] = []
            for item in news_items[:5]:
                text = item.get('summary') or item.get('headline', '')
                if text:
                    scores.append(self._compute_sentiment(text))
            # If we collected any scores, block on low average
            if scores:
                avg = sum(scores) / len(scores)
                if avg < self.sentiment_threshold:
                    return False
            # Block on high-impact keywords
            for item in news_items[:5]:
                title = (item.get('headline') or '').lower()
                for kw in self.keywords:
                    if kw in title:
                        return False
        # Otherwise, allow
        return True
