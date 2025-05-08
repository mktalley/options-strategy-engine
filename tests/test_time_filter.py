import pytest
from datetime import datetime
from zoneinfo import ZoneInfo
from time_filter import TimeFilter


def test_default_time_filter(monkeypatch):
    # Clear any env overrides
    for var in ("MARKET_OPEN_TIME", "MARKET_CLOSE_TIME", "TIME_FILTER_END_BUFFER_MINUTES", "PRE_MARKET_START", "AFTER_HOURS_END"):
        monkeypatch.delenv(var, raising=False)
    tf = TimeFilter()
    tz = ZoneInfo('America/New_York')
    # Default window: 09:30 <= t < 16:00 - 10min buffer => < 15:50
    cases = [
        (datetime(2025,5,7,9,29, tzinfo=tz), False),   # before open
        (datetime(2025,5,7,9,30, tzinfo=tz), True),    # at open
        (datetime(2025,5,7,12,0, tzinfo=tz), True),    # mid session
        (datetime(2025,5,7,15,49, tzinfo=tz), True),   # just before buffer
        (datetime(2025,5,7,15,50, tzinfo=tz), False),  # at buffer start
        (datetime(2025,5,7,16,0, tzinfo=tz), False),   # at close
        (datetime(2025,5,7,17,0, tzinfo=tz), False),   # after close
    ]
    for dt, expected in cases:
        assert tf.is_market_open(dt) == expected, f"Time {dt.time()} expected {expected}"


def test_custom_time_window(monkeypatch):
    # Override env vars
    monkeypatch.setenv('MARKET_OPEN_TIME', '10:00')
    monkeypatch.setenv('MARKET_CLOSE_TIME', '15:00')
    monkeypatch.setenv('TIME_FILTER_END_BUFFER_MINUTES', '30')
    # Clear optional env
    for var in ('PRE_MARKET_START', 'AFTER_HOURS_END'):
        monkeypatch.delenv(var, raising=False)
    tf = TimeFilter()
    tz = ZoneInfo('America/New_York')
    # Custom window: 10:00 <= t < 15:00 - 30min buffer => < 14:30
    assert not tf.is_market_open(datetime(2025,5,7,9,59, tzinfo=tz))
    assert tf.is_market_open(datetime(2025,5,7,10,0, tzinfo=tz))
    assert tf.is_market_open(datetime(2025,5,7,12,0, tzinfo=tz))
    assert tf.is_market_open(datetime(2025,5,7,14,29, tzinfo=tz))
    assert not tf.is_market_open(datetime(2025,5,7,14,30, tzinfo=tz))
    assert not tf.is_market_open(datetime(2025,5,7,15,0, tzinfo=tz))
