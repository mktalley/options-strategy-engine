#!/usr/bin/env python3
"""
options-strategy-engine main: event-driven strategy engine with AsyncIO scheduler and Alpaca WebSocket streaming.
"""
import os
import sys
import asyncio
import logging
import argparse
from dotenv import load_dotenv
from pythonjsonlogger import jsonlogger
from zoneinfo import ZoneInfo
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from utils import get_market_data, get_iv, get_trend, get_momentum, get_next_friday
from alpaca.trading.client import TradingClient
from strategy_selector import StrategySelector
from trade_executor import TradeExecutor
from alpaca.trading.stream import TradingStream


def configure_logging():
    """
    Configure root logger to output JSON-formatted logs to stdout.
    """
    root = logging.getLogger()
    handler = logging.StreamHandler()
    fmt = '%(asctime)s %(levelname)s %(name)s %(message)s'
    handler.setFormatter(jsonlogger.JsonFormatter(fmt))
    root.addHandler(handler)
    root.setLevel(logging.INFO)


async def scheduled_run(selector, executor, api_key, secret_key, base_url, tickers):
    """Fetch market data, compute metrics, select strategies, and execute orders."""
    try:
        market_data = get_market_data(tickers, api_key, secret_key, base_url)
    except Exception as e:
        logging.error(f"Failed to fetch market data: {e}")
        return

    for symbol, data in market_data.items():
        try:
            data['ticker'] = symbol
            data['expiration'] = get_next_friday()
            iv = get_iv(data)
            trend = get_trend(data)
            momentum = get_momentum(data)
            data.update({'iv': iv, 'trend': trend, 'momentum': momentum})
            logging.info(f"Metrics for {symbol}: IV={iv:.2f}, trend={trend}, momentum={momentum}")
            strategy = selector.select(trend, iv, momentum)
            orders = strategy.run(data)
            if not orders:
                logging.info(f"No orders generated for {symbol}")
                continue
            logging.info(f"Executing {len(orders)} orders for {symbol}: {orders}")
            results = executor.execute(orders)
            logging.info(f"Execution results for {symbol}: {results}")
        except Exception:
            logging.exception(f"Error processing {symbol}")

    logging.info("Batch processing complete")


async def stream_listener(selector, executor, api_key, secret_key, base_url, tickers):
    """Listen to Alpaca trade updates and rerun strategies on each update."""
    stream = TradingStream(
        api_key,
        secret_key,
        paper=True,
        raw_data=False,
        url_override=base_url
    )

    @stream.subscribe_trade_updates
    async def on_trade_update(update):
        logging.info(f"Trade update event: {update}")
        await scheduled_run(selector, executor, api_key, secret_key, base_url, tickers)

    logging.info("Starting trade updates stream")
    await stream._run_forever()


async def event_loop(selector, executor, api_key, secret_key, base_url, tickers):
    """Set up AsyncIO scheduler and run the WebSocket listener."""
    tz = ZoneInfo('America/New_York')
    scheduler = AsyncIOScheduler(timezone=tz)

    # market open: 9:30-9:59 ET
    scheduler.add_job(
        scheduled_run,
        'cron',
        args=[selector, executor, api_key, secret_key, base_url, tickers],
        day_of_week='mon-fri', hour=9, minute='30-59'
    )
    # continuous: 10:00-15:59 ET
    scheduler.add_job(
        scheduled_run,
        'cron',
        args=[selector, executor, api_key, secret_key, base_url, tickers],
        day_of_week='mon-fri', hour='10-15', minute='*'
    )
    # market close: 16:00 ET
    scheduler.add_job(
        scheduled_run,
        'cron',
        args=[selector, executor, api_key, secret_key, base_url, tickers],
        day_of_week='mon-fri', hour=16, minute=0
    )

    scheduler.start()
    await stream_listener(selector, executor, api_key, secret_key, base_url, tickers)


def validate_env(api_key, secret_key, base_url, tickers):
    """Ensure required environment variables are set."""
    missing = []
    if not api_key:
        missing.append('ALPACA_API_KEY')
    if not secret_key:
        missing.append('ALPACA_SECRET_KEY')
    if not base_url:
        missing.append('ALPACA_API_BASE_URL')
    if not tickers:
        missing.append('TICKERS')
    if missing:
        logging.error(f"Missing configuration: {', '.join(missing)} in .env")
        return False
    return True


def main():
    """Parse args, validate env, and start event loop or one-off run."""
    configure_logging()
    load_dotenv('.env')

    parser = argparse.ArgumentParser(description='Options Strategy Engine (event-driven)')
    parser.add_argument('--once', action='store_true', help='Run once and exit')
    parser.add_argument('--dry-run', action='store_true', help='Dry-run mode (no real orders)')
    args = parser.parse_args()

    api_key = os.getenv('ALPACA_API_KEY')
    secret_key = os.getenv('ALPACA_SECRET_KEY')
    base_url = os.getenv('ALPACA_API_BASE_URL')
    tickers_env = os.getenv('TICKERS') or ''
    tickers = [t.strip().upper() for t in tickers_env.split(',') if t.strip()]

    if not validate_env(api_key, secret_key, base_url, tickers):
        sys.exit(1)

    selector = StrategySelector()
    executor = TradeExecutor(dry_run=args.dry_run)

    if args.once:
        asyncio.run(scheduled_run(selector, executor, api_key, secret_key, base_url, tickers))
    else:
        try:
            asyncio.run(event_loop(selector, executor, api_key, secret_key, base_url, tickers))
        except (KeyboardInterrupt, SystemExit):
            logging.getLogger().info('Shutdown requested, stopping event loop.')

if __name__ == '__main__':
    main()
