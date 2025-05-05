#!/usr/bin/env python3
"""
Streamlit dashboard to display current Alpaca positions and active strategy per ticker.
Run with:
    streamlit run dashboard.py --server.port 51673 --server.address 0.0.0.0
"""
import os
import sys
import streamlit as st
import pandas as pd
from dotenv import load_dotenv
from alpaca.trading.client import TradingClient
from zoneinfo import ZoneInfo
from utils import get_market_data, get_iv, get_trend, get_momentum, get_next_friday
from strategy_selector import StrategySelector

# Load environment variables
load_dotenv('.env')
API_KEY = os.getenv('ALPACA_API_KEY')
SECRET_KEY = os.getenv('ALPACA_SECRET_KEY')
BASE_URL = os.getenv('ALPACA_API_BASE_URL')

# Check for required credentials
has_creds = all([API_KEY, SECRET_KEY, BASE_URL])
if not has_creds:
    st.warning('Missing ALPACA_API_KEY, ALPACA_SECRET_KEY or ALPACA_API_BASE_URL in .env. Dashboard will display empty data.')

# Initialize Alpaca client if credentials are present
if has_creds:
    client = TradingClient(API_KEY, SECRET_KEY, paper=True, base_url=BASE_URL)
else:
    client = None

# Strategy selector (independent of credentials)
selector = StrategySelector()

def fetch_positions():
    """Fetch current positions from Alpaca."""
    try:
        positions = client.get_all_positions()
    except Exception as e:
        st.error(f'Error fetching positions: {e}')
        return pd.DataFrame()
    rows = []
    for p in positions:
        rows.append({
            'Symbol': p.symbol,
            'Quantity': float(p.qty),
            'Avg Entry': float(p.avg_entry_price),
            'Market Value': float(p.market_value),
            'Unrealized P/L': float(p.unrealized_pl),
            'Realized P/L': float(p.realized_pl)
        })
    return pd.DataFrame(rows)


def fetch_strategies(tickers):
    """Compute current strategy for each ticker."""
    try:
        data = get_market_data(tickers, API_KEY, SECRET_KEY, BASE_URL)
    except Exception as e:
        st.error(f'Error fetching market data: {e}')
        return pd.DataFrame()
    rows = []
    for symbol, d in data.items():
        d['ticker'] = symbol
        d['expiration'] = get_next_friday()
        iv = get_iv(d)
        trend = get_trend(d)
        momentum = get_momentum(d)
        strat = selector.select(trend, iv, momentum)
        rows.append({
            'Symbol': symbol,
            'Strategy': type(strat).__name__,
            'IV': iv,
            'Trend': trend,
            'Momentum': momentum
        })
    return pd.DataFrame(rows)

# App layout
st.title('Options Strategy Engine Dashboard')

# Section: Positions
st.header('Current Positions')
df_pos = fetch_positions()
if df_pos.empty:
    st.write('No open positions.')
else:
    st.dataframe(df_pos)

# Section: Active Strategies
st.header('Current Strategy per Ticker')
# Determine tickers from env or from positions
env_tickers = os.getenv('TICKERS', '') or ''
ticker_list = [t.strip().upper() for t in env_tickers.split(',') if t.strip()]
if not ticker_list and not df_pos.empty:
    ticker_list = df_pos['Symbol'].tolist()

if not ticker_list:
    st.write('No tickers configured.')
else:
    df_strat = fetch_strategies(ticker_list)
    st.dataframe(df_strat)
