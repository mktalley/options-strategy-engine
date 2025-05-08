import os
import datetime
import pytest
from news_manager import NewsManager

# Helper to create dummy news items
def make_news_item(headline, summary=None):
    item = {'headline': headline}
    if summary is not None:
        item['summary'] = summary
    return item

@pytest.fixture(autouse=True)
def set_env(monkeypatch):
    # Clear and set environment variables for NewsManager
    for var in [
        'ECONOMIC_CALENDAR_API_KEY',
        'FINNHUB_API_KEY',
        'ECONOMIC_CALENDAR_LOOKAHEAD_DAYS',
        'NEWS_SENTIMENT_WINDOW_DAYS',
        'NEWS_SENTIMENT_THRESHOLD',
        'NEWS_RISK_KEYWORDS'
    ]:
        monkeypatch.delenv(var, raising=False)
    # Provide dummy API keys
    monkeypatch.setenv('ECONOMIC_CALENDAR_API_KEY', 'dummy')
    monkeypatch.setenv('FINNHUB_API_KEY', 'dummy')
    # Defaults
    monkeypatch.setenv('ECONOMIC_CALENDAR_LOOKAHEAD_DAYS', '2')
    monkeypatch.setenv('NEWS_SENTIMENT_WINDOW_DAYS', '1')
    monkeypatch.setenv('NEWS_SENTIMENT_THRESHOLD', '-0.3')
    monkeypatch.setenv('NEWS_RISK_KEYWORDS', 'fomc,non farm,nfp,fed')
    return monkeypatch


def test_calendar_event_blocks(monkeypatch):
    manager = NewsManager()
    # Simulate calendar event present
    monkeypatch.setattr(manager, '_has_calendar_event', lambda symbol: True)
    monkeypatch.setattr(manager, '_fetch_news', lambda symbol: [])
    assert not manager.is_trade_allowed('AAPL', {})


def test_negative_sentiment_blocks(monkeypatch):
    manager = NewsManager()
    monkeypatch.setattr(manager, '_has_calendar_event', lambda symbol: False)
    # Create fake news items
    items = [make_news_item('Bad performance', 'terrible results') for _ in range(2)]
    monkeypatch.setattr(manager, '_fetch_news', lambda symbol: items)
    # Force negative sentiment below threshold
    monkeypatch.setattr(manager, '_compute_sentiment', lambda text: -0.5)
    assert not manager.is_trade_allowed('AAPL', {})


def test_keyword_blocks(monkeypatch):
    manager = NewsManager()
    monkeypatch.setattr(manager, '_has_calendar_event', lambda symbol: False)
    # Create news item with keyword 'fed' in headline
    items = [make_news_item('Federal Reserve (Fed) update')]
    monkeypatch.setattr(manager, '_fetch_news', lambda symbol: items)
    # Even positive sentiment should block
    monkeypatch.setattr(manager, '_compute_sentiment', lambda text: 0.8)
    assert not manager.is_trade_allowed('AAPL', {})


def test_allow_good_sentiment(monkeypatch):
    manager = NewsManager()
    monkeypatch.setattr(manager, '_has_calendar_event', lambda symbol: False)
    # Positive news with no risk keywords
    items = [make_news_item('Great earnings report', 'beat expectations')]
    monkeypatch.setattr(manager, '_fetch_news', lambda symbol: items)
    monkeypatch.setattr(manager, '_compute_sentiment', lambda text: 0.7)
    assert manager.is_trade_allowed('AAPL', {})


def test_no_news_allows(monkeypatch):
    manager = NewsManager()
    monkeypatch.setattr(manager, '_has_calendar_event', lambda symbol: False)
    monkeypatch.setattr(manager, '_fetch_news', lambda symbol: [])
    assert manager.is_trade_allowed('AAPL', {})
