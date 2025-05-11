import os
import time
import datetime
import logging
import pytest

# Ensure GET_BARS_TIMEOUT is respected
from backtest import get_bars

class SlowClient:
    def get_stock_bars(self, req):
        # Simulate long-running call
        time.sleep(5)
        return {'DUMMY': []}

@pytest.fixture(autouse=True)
def set_timeout_env(monkeypatch):
    # Set a short timeout for testing
    monkeypatch.setenv('GET_BARS_TIMEOUT', '1')
    return


def test_get_bars_timeout(monkeypatch, caplog):
    caplog.set_level(logging.ERROR)
    client = SlowClient()
    start = datetime.datetime(2025, 1, 1)
    end = datetime.datetime(2025, 1, 2)
    # Should return empty list quickly (timeout ~1s)
    t0 = time.time()
    bars = get_bars(client, 'DUMMY', start, end)
    elapsed = time.time() - t0
    assert bars == []
    # Ensure elapsed time is less than full sleep (i.e., timeout triggered)
    assert elapsed < 3, f"Timeout did not trigger: elapsed={elapsed}"
    # Check error log
    assert any('Timeout fetching bars for DUMMY' in rec.getMessage() for rec in caplog.records)
