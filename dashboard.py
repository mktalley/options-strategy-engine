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

import threading
import time
import logging
from alpaca.trading.requests import OrderRequest
logging.basicConfig(level=logging.INFO)
# Automation state
last_strategies = {}
# Interval in seconds between automatic scans (env AUTO_INTERVAL)
AUTOMATION_INTERVAL = int(os.getenv('AUTO_INTERVAL', '60'))

def monitor_loop():
    """Background loop: fetch data, select strategy, deploy on change."""
    logging.info("Background monitor loop starting")
    while True:
        try:
            env_tix = os.getenv('TICKERS', '')
            ticker_list = [t.strip().upper() for t in env_tix.split(',') if t.strip()]
            if not has_creds or not ticker_list:
                logging.info(f"Automation paused: has_creds={has_creds}, tickers={ticker_list}")
                time.sleep(AUTOMATION_INTERVAL)
                continue
            data = get_market_data(ticker_list, API_KEY, SECRET_KEY, BASE_URL)
            for symbol, d in data.items():
                d['ticker'] = symbol
                d['expiration'] = get_next_friday()
                iv = get_iv(d)
                trend = get_trend(d)
                momentum = get_momentum(d)
                strat = selector.select(trend, iv, momentum)
                strat_name = type(strat).__name__
                prev = last_strategies.get(symbol)
                if strat_name != prev:
                    logging.info(f"Strategy changed for {symbol}: {prev} -> {strat_name}. Deploying...")
                    orders = strat.run(d)
                    for order in orders:
                        try:
                            req = OrderRequest(**order)
                            resp = client.submit_order(req)
                            logging.info(f"Auto submitted {order['side']} {order['qty']} {order['symbol']}: {resp.status}")
                        except Exception as err:
                            logging.error(f"Error auto submitting {order}: {err}")
                    last_strategies[symbol] = strat_name
                else:
                    logging.info(f"No change for {symbol}: still {strat_name}")
            time.sleep(AUTOMATION_INTERVAL)
        except Exception as e:
            logging.exception(f"Unexpected error in monitor_loop: {e}")
            time.sleep(AUTOMATION_INTERVAL)
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
    client = TradingClient(API_KEY, SECRET_KEY, paper=True, url_override=BASE_URL)
else:
    client = None

# Strategy selector (independent of credentials)
selector = StrategySelector()
# Start background automation monitor
threading.Thread(target=monitor_loop, daemon=True).start()
logging.info(f"Automation monitor started: scanning every {AUTOMATION_INTERVAL} seconds")


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
            'Realized P/L': float(getattr(p, 'realized_pl', 0.0)),  # fallback if attribute missing
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

# Section: Deploy Strategies
st.header('Deploy Selected Strategies')
if st.button('Deploy Strategies'):
    if not has_creds:
        st.error('Missing Alpaca credentials. Cannot deploy orders.')
    elif not ticker_list:
        st.warning('No tickers configured.')
    else:
        with st.spinner('Deploying strategies...'):
            try:
                market_data = get_market_data(ticker_list, API_KEY, SECRET_KEY, BASE_URL)
            except Exception as e:
                st.error(f'Error fetching market data for deployment: {e}')
            else:
                for symbol, d in market_data.items():
                    d['ticker'] = symbol
                    d['expiration'] = get_next_friday()
                    iv = get_iv(d)
                    trend = get_trend(d)
                    momentum = get_momentum(d)
                    strat = selector.select(trend, iv, momentum)
                    orders = strat.run(d)
                    for order in orders:
                        try:
                            req = OrderRequest(**order)
                            resp = client.submit_order(req)
                            st.success(f"Submitted {order['side']} {order['qty']} of {order['symbol']}")
                        except Exception as e:
                            st.error(f"Error submitting order {order}: {e}")

