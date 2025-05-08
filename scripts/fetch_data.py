#!/usr/bin/env python3
"""
Fetch historical daily OHLCV data for given tickers from Alpaca and save as CSV files.
"""
import os
import argparse
from datetime import datetime
import pandas as pd
from dotenv import load_dotenv
from alpaca.data.historical.stock import StockHistoricalDataClient, StockBarsRequest
from alpaca.data.timeframe import TimeFrame


def fetch_and_save(tickers, start_date, end_date, outdir, url_override=None):
    # Load Alpaca credentials from environment
    load_dotenv()
    api_key = os.getenv('ALPACA_API_KEY')
    secret_key = os.getenv('ALPACA_SECRET_KEY')
    base_url = os.getenv('ALPACA_API_BASE_URL')
    data_url = os.getenv('ALPACA_DATA_BASE_URL')
    url_override = url_override or data_url or base_url

    client = StockHistoricalDataClient(
        api_key=api_key,
        secret_key=secret_key,
        raw_data=False,
        url_override=url_override
    )

    os.makedirs(outdir, exist_ok=True)
    for ticker in tickers:
        print(f"Fetching {ticker} from {start_date.date()} to {end_date.date()}...")
        req = StockBarsRequest(
            symbol_or_symbols=ticker,
            timeframe=TimeFrame.Day,
            start=start_date,
            end=end_date
        )
        resp = client.get_stock_bars(req)
        # normalize response
        if hasattr(resp, 'data'):
            data_map = resp.data
        elif isinstance(resp, dict):
            data_map = resp
        else:
            data_map = {}

        bars = data_map.get(ticker, [])
        if not bars:
            print(f"No data returned for {ticker}")
            continue

        # Build DataFrame
        rows = []
        for bar in bars:
            rows.append({
                'Date': bar.t.strftime('%Y-%m-%d'),
                'Open': bar.o,
                'High': bar.h,
                'Low': bar.l,
                'Close': bar.c,
                'Volume': bar.v
            })
        df = pd.DataFrame(rows)
        df.set_index('Date', inplace=True)

        out_path = os.path.join(outdir, f"{ticker}.csv")
        df.to_csv(out_path)
        print(f"Saved {out_path} ({len(df)} bars)")


def main():
    parser = argparse.ArgumentParser(description='Fetch OHLCV CSV data from Alpaca')
    parser.add_argument(
        '--tickers', required=True,
        help='Comma-separated list of ticker symbols (e.g. SPY,QQQ)'
    )
    parser.add_argument(
        '--start', required=True,
        help='Start date in YYYY-MM-DD'
    )
    parser.add_argument(
        '--end', required=True,
        help='End date in YYYY-MM-DD'
    )
    parser.add_argument(
        '--outdir', default='data',
        help='Output directory for CSV files'
    )
    parser.add_argument(
        '--url-override', default=None,
        help='Optional override for Alpaca data API URL'
    )
    args = parser.parse_args()

    tickers = [t.strip().upper() for t in args.tickers.split(',') if t.strip()]
    try:
        start_date = datetime.fromisoformat(args.start)
        end_date = datetime.fromisoformat(args.end)
    except ValueError as e:
        parser.error(f"Invalid date format: {e}")

    fetch_and_save(tickers, start_date, end_date, args.outdir, args.url_override)


if __name__ == '__main__':
    main()
