import os
import logging
import time
import json

from alpaca.trading.client import TradingClient
from utils import get_market_data, get_iv, get_trend, get_momentum

class Scanner:
    """
    Dynamic scanning and sector analysis module.
    Fetches active assets via Alpaca API, filters by volatility, trend, momentum, and returns top N tickers.
    Configurable via constructor arguments or environment variables:
    - api_key, secret_key: Alpaca API credentials
    - base_url, data_url: endpoints for trading and market data
    - max_iv: maximum historical volatility threshold
    - top_n: number of top symbols to return
    - cache_ttl: cache time-to-live in seconds
    - cache_file: path to cache file
    - tickers_override: list or comma-separated string of tickers to force-scan
    """

    def __init__(
        self,
        api_key: str = None,
        secret_key: str = None,
        base_url: str = None,
        data_url: str = None,
        max_iv: float = None,
        top_n: int = None,
        cache_ttl: int = None,
        cache_file: str = None,
        tickers_override=None,
    ):
        # Credentials and endpoints
        self.api_key = api_key or os.getenv('ALPACA_API_KEY')
        self.secret_key = secret_key or os.getenv('ALPACA_SECRET_KEY')
        self.base_url = base_url or os.getenv('ALPACA_API_BASE_URL')
        self.data_url = data_url or os.getenv('ALPACA_DATA_BASE_URL')
        # Scanning thresholds and limits
        self.max_iv = max_iv if max_iv is not None else float(os.getenv('SCANNER_MAX_IV', '1.0'))
        self.top_n = top_n if top_n is not None else int(os.getenv('SCANNER_TOP_N', '10'))
        # Cache settings
        self.cache_ttl = cache_ttl if cache_ttl is not None else int(os.getenv('SCANNER_CACHE_TTL', '300'))
        self.cache_file = cache_file or os.getenv('SCANNER_CACHE_FILE', '/tmp/scanner_cache.json')
        # Tickers override
        self.tickers_override = tickers_override if tickers_override is not None else os.getenv('TICKERS')
        if isinstance(self.tickers_override, list):
            # join list into comma-separated string
            self.tickers_override = ",".join(self.tickers_override)
        # Validate required credentials
        if not all([self.api_key, self.secret_key]):
            raise ValueError('Alpaca API credentials must be set for Scanner')
        # Initialize trading client
        self.trading_client = TradingClient(
            self.api_key,
            self.secret_key,
            paper=True,
            url_override=self.base_url or None
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
        # Override via constructor or ENV
        if self.tickers_override:
            if isinstance(self.tickers_override, str):
                tickers = [t.strip().upper() for t in self.tickers_override.split(',') if t.strip()]
            else:
                tickers = [str(t).strip().upper() for t in self.tickers_override]
            logging.info(f'Scanner using override tickers: {tickers}')
            return tickers

        # Use cached tickers if valid
        cached = self._load_cache()
        if cached is not None:
            logging.info(f'Scanner using cached tickers: {cached}')
            return cached

        # Fetch active assets
        assets = self.trading_client.get_all_assets(status='active', asset_class='us_equity')
        symbols = [
            a.symbol
            for a in assets
            if getattr(a, 'status', '') == 'active' and getattr(a, 'tradable', False)
        ]
        if not symbols:
            self._save_cache([])
            return []

        # Fetch market data
        data = get_market_data(symbols, self.api_key, self.secret_key, self.base_url, self.data_url)
        candidates = []
        for sym, d in data.items():
            iv = get_iv(d)
            trend = get_trend(d)
            momentum = get_momentum(d)
            if iv > self.max_iv or trend != 'bullish' or momentum != 'positive':
                continue
            candidates.append({'symbol': sym, 'iv': iv})

        # Sort by IV ascending and select top N
        sorted_c = sorted(candidates, key=lambda x: x['iv'])
        top = [c['symbol'] for c in sorted_c[:self.top_n]]
        logging.info(f'Scanner returning top {len(top)} symbols: {top}')
        self._save_cache(top)
        return top
