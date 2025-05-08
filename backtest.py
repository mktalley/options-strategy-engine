import os
import argparse
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv
import pandas as pd

import numpy as np
from utils import get_iv, get_trend, get_momentum, get_next_friday
from strategy_selector import StrategySelector
from trade_executor import TradeExecutor

# Alpaca data client imports
from alpaca.data.historical.stock import StockHistoricalDataClient, StockBarsRequest
from alpaca.data.historical.option import OptionHistoricalDataClient, OptionBarsRequest
from alpaca.data.timeframe import TimeFrame


def get_bars(client, ticker: str, start: datetime, end: datetime):
    """
    Fetch daily bars for a ticker between start and end dates (inclusive).
    Returns a list of bar objects sorted by timestamp.
    """
    req = StockBarsRequest(
        symbol_or_symbols=ticker,
        timeframe=TimeFrame.Day,
        start=start.isoformat(),
        end=end.isoformat()
    )
    resp = client.get_stock_bars(req)
    # bars_resp may have .data mapping or be a dict
    if hasattr(resp, 'data'):
        bars = resp.data.get(ticker, [])
    elif isinstance(resp, dict):
        bars = resp.get(ticker, [])
    else:
        bars = []
    # sort by timestamp attribute if present
    try:
        bars = sorted(bars, key=lambda b: getattr(b, 't', None))
    except Exception:
        pass
    return bars


def run_backtest(
    tickers,
    start_date: datetime,
    end_date: datetime,
    api_key: str,
    secret_key: str,
    base_url: str,
    data_url: str,
    iv_threshold: float
):
    """
    Run a backtest dry-run over the given date range.
    Writes results to backtest_results.csv and prints summary.
    """
    # Initialize data client
    url_override = data_url or os.getenv("ALPACA_DATA_BASE_URL") or base_url
    data_client = StockHistoricalDataClient(
        api_key=api_key,
        secret_key=secret_key,
        raw_data=False,
        url_override=url_override
    )
    # Options data client for P/L simulation
    option_client = OptionHistoricalDataClient(
        api_key=api_key,
        secret_key=secret_key,
        raw_data=False,
        url_override=url_override
    )

    selector = StrategySelector(iv_threshold=iv_threshold)
    executor = TradeExecutor(dry_run=True)

    records = []
    for ticker in tickers:
        logging.info(f"Fetching bars for {ticker} from {start_date.date()} to {end_date.date()}")
        bars = get_bars(data_client, ticker, start_date, end_date)
        if len(bars) < 21:
            logging.warning(f"Not enough data for {ticker}: need at least 21 bars, got {len(bars)}")
            continue
        # Rolling window
        for i in range(20, len(bars)):
            # Build rolling window of last 20 closes
            window = bars[i-20+1:i+1]
            close_prices = []
            for b in window:
                # Prefer attribute 'c' or fallback to 'close'
                c = getattr(b, 'c', None)
                if c is None:
                    c = getattr(b, 'close', None)
                if c is None:
                    logging.warning(f"Skipping {ticker}: missing close price for bar {getattr(b, 't', None)}")
                    break
                close_prices.append(c)
            # Skip if incomplete window
            if len(close_prices) != 20:
                continue

            # Determine last bar and price
            last_bar = bars[i]
            # Extract bar_date
            bar_date = getattr(last_bar, 't', None) or getattr(last_bar, 'timestamp', None)
            if bar_date is None:
                logging.warning(f"Skipping {ticker}: missing timestamp for bar {last_bar}")
                continue
            if hasattr(bar_date, 'date'):
                bar_date = bar_date.date()
            price = getattr(last_bar, 'c', None) or getattr(last_bar, 'close', None)
            if price is None:
                logging.warning(f"Skipping {ticker}: missing price for bar {getattr(last_bar, 't', None)}")
                continue

            # Compute metrics
            iv = get_iv({'close_prices': close_prices})
            trend = get_trend({'price': price, 'close_prices': close_prices})
            momentum = get_momentum({'close_prices': close_prices})

            data = {
                'ticker': ticker,
                'price': price,
                'close_prices': close_prices,
                'iv': iv,
                'trend': trend,
                'momentum': momentum,
                # expiration is next Friday relative to bar date
                'expiration': get_next_friday(bar_date)
            }

            strategy = selector.select(trend, iv, momentum)
            orders = strategy.run(data)
            if not orders:
                continue
            # Dry-run execution (requests are returned)
            reqs = executor.execute(orders)
            # Record each trade detail
            if orders:
                # Simulated dry-run, record each individual order for P/L simulation
                for order in orders:
                    # Fetch entry mid-price
                    try:
                        entry_req = OptionBarsRequest(
                            symbol_or_symbols=order['symbol'],
                            timeframe=TimeFrame.Day,
                            start=bar_date.isoformat(),
                            end=bar_date.isoformat()
                        )
                        entry_resp = option_client.get_option_bars(entry_req)
                        if hasattr(entry_resp, 'data'):
                            entry_map = entry_resp.data
                        elif isinstance(entry_resp, dict):
                            entry_map = entry_resp
                        else:
                            entry_map = {}
                        entry_bars = entry_map.get(order['symbol'], [])
                        entry_price = getattr(entry_bars[0], 'c', None) if entry_bars else None
                    except Exception as e:
                        logging.warning(f"Failed to fetch entry price for {order['symbol']} on {bar_date}: {e}")
                        entry_price = None
                    # Fetch exit mid-price
                    try:
                        exit_date = data['expiration']
                        exit_req = OptionBarsRequest(
                            symbol_or_symbols=order['symbol'],
                            timeframe=TimeFrame.Day,
                            start=exit_date.isoformat(),
                            end=exit_date.isoformat()
                        )
                        exit_resp = option_client.get_option_bars(exit_req)
                        if hasattr(exit_resp, 'data'):
                            exit_map = exit_resp.data
                        elif isinstance(exit_resp, dict):
                            exit_map = exit_resp
                        else:
                            exit_map = {}
                        exit_bars = exit_map.get(order['symbol'], [])
                        exit_price = getattr(exit_bars[-1], 'c', None) if exit_bars else None
                    except Exception as e:
                        logging.warning(f"Failed to fetch exit price for {order['symbol']} on {exit_date}: {e}")
                        exit_price = None
                    # Compute P/L (contracts multiplier=100)
                    pl = None
                    if entry_price is not None and exit_price is not None:
                        multiplier = 100
                        qty = order.get('qty', 0)
                        side = order.get('side', '').lower()
                        if side == 'buy':
                            pl = (exit_price - entry_price) * qty * multiplier
                        else:
                            pl = (entry_price - exit_price) * qty * multiplier
                    records.append({
                        'entry_date': bar_date,
                        'ticker': ticker,
                        'symbol': order['symbol'],
                        'side': order['side'],
                        'qty': order['qty'],
                        'strategy': strategy.__class__.__name__,
                        'expiration': data['expiration'],
                        'entry_price': entry_price,
                        'exit_price': exit_price,
                        'iv': iv,
                        'trend': trend,
                        'momentum': momentum,
                        'price': price,
                        'days_to_exp': (data['expiration'] - bar_date).days,
                        'pl': pl
                    })


            records.append({
                'date': bar_date,
                'ticker': ticker,
                'strategy': strategy.__class__.__name__,
                'order_count': len(orders)
            })

    # Build DataFrame
    df = pd.DataFrame(records)
    if df.empty:
        logging.info("No orders were generated during backtest.")
        return df

    # Print summary metrics
    total_trades = len(df)
    trades_by_strategy = df['strategy'].value_counts()

    print(f"Total trade signals: {total_trades}")
    print("Trades by strategy:")
    print(trades_by_strategy)

    # Save to CSV
    out_csv = "backtest_results.csv"
    df.to_csv(out_csv, index=False)
    print(f"Detailed results written to {out_csv}")
    return df


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Backtest options strategy signal generation")
    parser.add_argument("--tickers", required=True,
                        help="Comma-separated list of tickers to backtest")
    parser.add_argument("--start", required=True,
                        help="Start date YYYY-MM-DD")
    parser.add_argument("--end", required=True,
                        help="End date YYYY-MM-DD")
    parser.add_argument("--iv-threshold", type=float, default=0.25,
                        help="IV threshold for high/low decision in StrategySelector")
    args = parser.parse_args()

    # Load environment
    load_dotenv()  # loads .env in cwd
    api_key = os.getenv('ALPACA_API_KEY')
    secret_key = os.getenv('ALPACA_SECRET_KEY')
    base_url = os.getenv('ALPACA_API_BASE_URL')
    data_url = os.getenv('ALPACA_DATA_BASE_URL')

    tickers = [t.strip().upper() for t in args.tickers.split(',') if t.strip()]
    try:
        start_date = datetime.fromisoformat(args.start)
        end_date = datetime.fromisoformat(args.end)
    except ValueError:
        logging.error("Invalid date format. Use YYYY-MM-DD.")
        exit(1)

    run_backtest(
        tickers=tickers,
        start_date=start_date,
        end_date=end_date,
        api_key=api_key,
        secret_key=secret_key,
        base_url=base_url,
        data_url=data_url,
        iv_threshold=args.iv_threshold
    )
