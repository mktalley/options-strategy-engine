import os
import json
import time
import pytest
import scanner

# Fake trading client for tests
def test_override_tickers(monkeypatch):
    monkeypatch.setenv('ALPACA_API_KEY', 'key')
    monkeypatch.setenv('ALPACA_SECRET_KEY', 'sec')
    # Override tickers
    monkeypatch.setenv('TICKERS', 'AAA, bbb ,CCC')
    s = scanner.Scanner()
    result = s.scan()
    assert result == ['AAA', 'BBB', 'CCC']


def test_cache_usage(monkeypatch, tmp_path):
    monkeypatch.setenv('ALPACA_API_KEY', 'k')
    monkeypatch.setenv('ALPACA_SECRET_KEY', 's')
    # Create cache file with fresh timestamp
    cache_file = tmp_path / 'cache.json'
    content = {'timestamp': time.time(), 'tickers': ['X', 'Y']}
    cache_file.write_text(json.dumps(content))
    monkeypatch.setenv('SCANNER_CACHE_FILE', str(cache_file))
    monkeypatch.setenv('SCANNER_CACHE_TTL', '1000')
    # Ensure no override and stub TradingClient to avoid real API
    monkeypatch.delenv('TICKERS', raising=False)
    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass
        def get_all_assets(self, status, asset_class):
            pytest.skip("Should use cache, not call API")
    monkeypatch.setattr(scanner, 'TradingClient', FakeClient)
    s = scanner.Scanner()
    result = s.scan()
    assert result == ['X', 'Y']


def test_no_assets_creates_empty_cache(monkeypatch, tmp_path):
    monkeypatch.setenv('ALPACA_API_KEY', 'k')
    monkeypatch.setenv('ALPACA_SECRET_KEY', 's')
    monkeypatch.env = monkeypatch  # noqa: F841
    cache_file = tmp_path / 'empty_cache.json'
    monkeypatch.setenv('SCANNER_CACHE_FILE', str(cache_file))
    # Set TTL to zero to skip loading non-existing cache
    monkeypatch.setenv('SCANNER_CACHE_TTL', '0')
    monkeypatch.delenv('TICKERS', raising=False)
    # Stub TradingClient to return no assets
    class EmptyClient:
        def __init__(self, *args, **kwargs):
            pass
        def get_all_assets(self, status, asset_class):
            return []
    monkeypatch.setattr(scanner, 'TradingClient', EmptyClient)
    s = scanner.Scanner()
    result = s.scan()
    assert result == []
    # Verify cache file created with empty list
    saved = json.loads(cache_file.read_text())
    assert saved['tickers'] == []
    assert 'timestamp' in saved


def test_filtering_sorting_top_n(monkeypatch):
    monkeypatch.setenv('ALPACA_API_KEY', 'k')
    monkeypatch.setenv('ALPACA_SECRET_KEY', 's')
    monkeypatch.delenv('TICKERS', raising=False)
    # Shorten TTL to skip caching
    monkeypatch.setenv('SCANNER_CACHE_TTL', '0')
    # Stub client to provide assets A, B, C
    class FakeAsset:
        def __init__(self, symbol):
            self.symbol = symbol
            self.status = 'active'
            self.tradable = True
    class FakeClient2:
        def __init__(self, *args, **kwargs): pass
        def get_all_assets(self, status, asset_class):
            return [FakeAsset('A'), FakeAsset('B'), FakeAsset('C')]
    monkeypatch.setattr(scanner, 'TradingClient', FakeClient2)
    # Stub market data with iv values
    def fake_market_data(symbols, api, secret, base, data_url):
        return {'A': {'iv': 0.5}, 'B': {'iv': 1.5}, 'C': {'iv': 0.3}}
    monkeypatch.setattr(scanner, 'get_market_data', fake_market_data)
    # Stub metrics to use iv, and always bullish/positive
    monkeypatch.setattr(scanner, 'get_iv', lambda d: d['iv'])
    monkeypatch.setattr(scanner, 'get_trend', lambda d: 'bullish')
    monkeypatch.setattr(scanner, 'get_momentum', lambda d: 'positive')
    # Default max_iv=1.0, top_n=10
    s = scanner.Scanner()
    result = s.scan()
    # Should filter B (iv=1.5) and sort by iv: C (0.3), A (0.5)
    assert result == ['C', 'A']
