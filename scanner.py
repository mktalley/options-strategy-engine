import os
import logging
import time
import json

from alpaca.trading.client import TradingClient
from utils import get_market_data, get_iv, get_trend, get_momentum

class Scanner:
    '''
    Dynamic scanning and sector analysis module.
    Fetches active assets via Alpaca API, filters by volatility, trend, momentum, and returns top N tickers.
    Configurable via environment variables:
    - SCANNER_MAX_IV: maximum historical volatility threshold
    - SCANNER_TOP_N: number of top symbols to return
    - SCANNER_CACHE_TTL: cache time-to-live in seconds
    - SCANNER_CACHE_FILE: path to cache file
    - TICKERS: optional override comma-separated list
    '''
    def __init__(self):
        self.api_key = os.getenv('ALPACA_API_KEY')
        self.secret_key = os.getenv('ALPACA_SECRET_KEY')
        self.base_url = os.getenv('ALPACA_API_BASE_URL')
        self.data_url = os.getenv('ALPACA_DATA_BASE_URL')
        self.max_iv = float(os.getenv('SCANNER_MAX_IV', '1.0'))
        self.top_n = int(os.getenv('SCANNER_TOP_N', '10'))
        self.cache_ttl = int(os.getenv('SCANNER_CACHE_TTL', '300'))
        self.cache_file = os.getenv('SCANNER_CACHE_FILE', '/tmp/scanner_cache.json')
        if not all([self.api_key, self.secret_key]):
            raise ValueError('Alpaca API credentials must be set for Scanner')
        self.trading_client = TradingClient(
            self.api_key,
            self.secret_key,
            paper=True,
            url_override=self.base_url if self.base_url else None
        )

    def _load_cache(self):
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r') as f:
                    cache = json.load(f)
                ts = cache.get('timestamp', 0)
                if time.time() - ts < self.cache_ttl:
                    return cache.get('tickers', [])
            except Exception as e:
                logging.warning(f'Cache load failed: {e}')
        return None

    def _save_cache(self, tickers):
        try:
            with open(self.cache_file, 'w') as f:
                json.dump({'timestamp': time.time(), 'tickers': tickers}, f)
        except Exception as e:
            logging.warning(f'Cache save failed: {e}')

    def scan(self):
        override = os.getenv('TICKERS', '')
        if override:
            tickers = [t.strip().upper() for t in override.split(',') if t.strip()]
            logging.info(f'Scanner using override tickers: {tickers}')
            return tickers

        cached = self._load_cache()
        if cached is not None:
            logging.info(f'Scanner using cached tickers: {cached}')
            return cached

        assets = self.trading_client.get_all_assets(status='active', asset_class='us_equity')
        symbols = [a.symbol for a in assets if getattr(a, 'status', '') == 'active' and getattr(a, 'tradable', False)]
        if not symbols:
            self._save_cache([])
            return []

        data = get_market_data(symbols, self.api_key, self.secret_key, self.base_url, self.data_url)
        candidates = []
        for sym, d in data.items():
            iv = get_iv(d)
            trend = get_trend(d)
            momentum = get_momentum(d)
            if iv > self.max_iv or trend != 'bullish' or momentum != 'positive':
                continue
            candidates.append({'symbol': sym, 'iv': iv})

        sorted_c = sorted(candidates, key=lambda x: x['iv'])
        top = [c['symbol'] for c in sorted_c[:self.top_n]]
        logging.info(f'Scanner returning top {len(top)} symbols: {top}')
        self._save_cache(top)
        return top
