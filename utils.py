import os
import requests
import numpy as np
import pandas as pd
from datetime import date, timedelta


def get_market_data(tickers, api_key, secret_key, base_url, data_url=None):
    """
    Fetch latest price and historical close prices for given tickers using Alpaca Python client.
    Returns dict: {ticker: {'price': float, 'close_prices': list[float]}}
    """
    # Initialize data client
    from alpaca.data.historical.stock import StockHistoricalDataClient, StockBarsRequest, StockLatestTradeRequest
    from alpaca.data.timeframe import TimeFrame

    # Determine data API URL override (if provided)
    # Determine data API URL override (priority: base_url param, explicit data_url, env var)
    # Prefer explicit data_url or env var for market-data API, fallback to trading base_url
    url_override = data_url or os.getenv("ALPACA_DATA_BASE_URL") or base_url
    client = StockHistoricalDataClient(
        api_key=api_key,
        secret_key=secret_key,
        raw_data=False,
        url_override=url_override
    )
    market_data = {}
    for ticker in tickers:
        # Fetch latest trade using StockLatestTradeRequest
        trade_resp = client.get_stock_latest_trade(
            StockLatestTradeRequest(symbol_or_symbols=ticker)
        )
        # trade_resp may be a dict mapping symbol->trade object
        if isinstance(trade_resp, dict):
            trade = trade_resp.get(ticker)
        else:
            # fallback: if resp is a single object
            trade = trade_resp
        price = getattr(trade, 'price', None)

        # Fetch historical bars using StockBarsRequest
        bars_resp = client.get_stock_bars(
            StockBarsRequest(
                symbol_or_symbols=ticker,
                timeframe=TimeFrame.Day,
                limit=30
            )
        )
        # bars_resp may be a BarSet or a dict
        if hasattr(bars_resp, 'data'):
            bars_mapping = bars_resp.data
        elif isinstance(bars_resp, dict):
            bars_mapping = bars_resp
        else:
            # fallback: convert to dict if possible
            bars_mapping = bars_resp.dict() if hasattr(bars_resp, 'dict') else {}
        bars = bars_mapping.get(ticker) or []
        # Extract close prices
        close_prices = [getattr(bar, 'c', 0.0) for bar in bars]

        market_data[ticker] = {
            'price': price,
            'close_prices': close_prices
        }
    return market_data


def get_iv(data):
    """
    Calculate historical volatility (annualized) based on log returns.
    """
    close_prices = data.get('close_prices', [])
    if len(close_prices) < 2:
        return 0.0
    log_returns = np.diff(np.log(close_prices))
    hist_vol = np.std(log_returns) * np.sqrt(252)
    return float(hist_vol)

def get_trend(data):
    """
    Determine trend based on price vs 20-day moving average.
    """
    close_prices = data.get('close_prices', [])
    price = data.get('price', 0)
    if len(close_prices) < 20 or price is None:
        return 'neutral'
    ma20 = np.mean(close_prices[-20:])
    if price > ma20:
        return 'bullish'
    elif price < ma20:
        return 'bearish'
    return 'neutral'

def get_momentum(data):
    """
    Simple momentum: positive if last close > previous close, else negative.
    """
    close_prices = data.get('close_prices', [])
    if len(close_prices) < 2:
        return 'neutral'
    return 'positive' if close_prices[-1] > close_prices[-2] else 'negative'

def get_next_friday(reference_date=None):
    """
    Return the next upcoming Friday date relative to reference_date (defaults to today).
    """
    ref = reference_date if reference_date is not None else date.today()
    # Monday=0, Friday=4
    days_ahead = 4 - ref.weekday()
    if days_ahead <= 0:
        days_ahead += 7
    return ref + timedelta(days=days_ahead)

def format_option_symbol(ticker, expiration_date, strike, option_type):
    """
    Format OCC option symbol: {ticker}{YYMMDD}{C/P}{strike*1000 padded 8 digits}.
    expiration_date: datetime.date
    strike: float
    option_type: 'call' or 'put'
    """
    exp_str = expiration_date.strftime('%y%m%d')
    type_letter = 'C' if option_type.lower() == 'call' else 'P'
    # Alpaca expects strike * 1000, zero-padded to 8 digits
    strike_int = int(strike * 1000)
    strike_str = f"{strike_int:08d}"
    return f"{ticker}{exp_str}{type_letter}{strike_str}"
