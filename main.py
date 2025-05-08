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
import os
# Feature toggles via environment variables
ENABLE_TIME_FILTER = os.getenv('ENABLE_TIME_FILTER', 'false').lower() in ('true', '1')
ENABLE_RISK_MANAGEMENT = os.getenv('ENABLE_RISK_MANAGEMENT', 'false').lower() in ('true', '1')
ENABLE_NEWS_RISK = os.getenv('ENABLE_NEWS_RISK', 'false').lower() in ('true', '1')
ENABLE_ML = os.getenv('ENABLE_ML', 'false').lower() in ('true', '1')
ENABLE_ALERTS = os.getenv('ENABLE_ALERTS', 'false').lower() in ('true', '1')
ENABLE_SCANNING = os.getenv('ENABLE_SCANNING', 'false').lower() in ('true', '1')

from logging.handlers import TimedRotatingFileHandler
from zoneinfo import ZoneInfo
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from utils import get_market_data, get_iv, get_trend, get_momentum, get_next_friday
from time_filter import TimeFilter
from scanner import Scanner
from risk_manager import RiskManager
from news_manager import NewsManager
from model_manager import ModelManager
from alert_manager import AlertManager
from alpaca.trading.client import TradingClient
from strategy_selector import StrategySelector
from trade_executor import TradeExecutor
from summary_manager import SummaryManager
from alpaca.trading.stream import TradingStream

# Instantiate feature modules based on feature toggles
time_filter = TimeFilter() if ENABLE_TIME_FILTER else None
scanner = Scanner() if ENABLE_SCANNING else None
risk_manager = RiskManager() if ENABLE_RISK_MANAGEMENT else None
news_manager = NewsManager() if ENABLE_NEWS_RISK else None
model_manager = ModelManager() if ENABLE_ML else None
alert_manager = AlertManager() if ENABLE_ALERTS else None

# Summary manager: record trades for daily summary
summary_manager = SummaryManager()




def configure_logging():
    """
    Configure root logger to output JSON-formatted logs to stdout and to a rotating file.
    """
    root = logging.getLogger()
    fmt = '%(asctime)s %(levelname)s %(name)s %(message)s'
    from datetime import datetime
    from zoneinfo import ZoneInfo
    # set log timestamps to Pacific (America/Los_Angeles) timezone
    local_tz = ZoneInfo('America/Los_Angeles')
    class LocalTimeJsonFormatter(jsonlogger.JsonFormatter):
        def formatTime(self, record, datefmt=None):
            dt = datetime.fromtimestamp(record.created, tz=local_tz)
            if datefmt:
                return dt.strftime(datefmt)
            return dt.isoformat()
    json_fmt = LocalTimeJsonFormatter(fmt)

    # console handler
    sh = logging.StreamHandler()
    sh.setFormatter(json_fmt)
    root.addHandler(sh)

        # file handler with daily rotation
    fh = TimedRotatingFileHandler('server.log', when='midnight', interval=1, backupCount=7)
    fh.setFormatter(json_fmt)
    root.addHandler(fh)

    root.setLevel(logging.INFO)


async def scheduled_run(selector, executor, api_key, secret_key, base_url, tickers):
    """Fetch market data, compute metrics, select strategies, and execute orders."""
    import time
    # Metrics for performance monitoring
    start_time = time.monotonic()
    trades_before = len(summary_manager.trades)
    symbols_processed = 0
    orders_attempted = 0
    orders_executed = 0
    total_notional = 0.0
    # Time-based filter: skip run if market is closed
    if time_filter and not time_filter.is_market_open():
        logging.info("Market closed. Skipping scheduled run")
        return
    # Dynamic ticker scanning
    run_tickers = scanner.scan() if scanner else tickers
    try:
        market_data = get_market_data(run_tickers, api_key, secret_key, base_url)

    except Exception as e:
        logging.error(f"Failed to fetch market data: {e}")
        market_data = {}


    for symbol, data in market_data.items():
        symbols_processed += 1
        try:
            data['ticker'] = symbol
            data['expiration'] = get_next_friday()
            iv = get_iv(data)
            trend = get_trend(data)
            momentum = get_momentum(data)
            data.update({'iv': iv, 'trend': trend, 'momentum': momentum})
            logging.info(f"Metrics for {symbol}: IV={iv:.2f}, trend={trend}, momentum={momentum}")
            # News risk management: skip if not allowed
            if news_manager and not news_manager.is_trade_allowed(symbol, data):
                logging.info(f"Trade for {symbol} blocked by news risk manager")
                continue
            strategy = selector.select(trend, iv, momentum)
            orders = strategy.run(data)
            if not orders:
                logging.info(f"No orders generated for {symbol}")
                continue
            # Risk management adjustments
            if risk_manager:
                orders = risk_manager.adjust_orders(orders, data)
            # ML model adjustments
            if model_manager:
                orders = model_manager.adjust_orders(orders, data)
            if not orders:
                logging.info(f"No orders remaining after adjustments for {symbol}")
                continue
            orders_attempted += len(orders)
            logging.info(f"Executing {len(orders)} orders for {symbol}: {orders}")
            results = executor.execute(orders)
            # Update executed orders and notional
            orders_executed += len(results)
            for r in results:
                price = getattr(r, 'filled_avg_price', None)
                qty = getattr(r, 'filled_qty', None)
                if price is not None and qty is not None:
                    try:
                        total_notional += float(price) * float(qty)
                    except Exception:
                        pass
            logging.info(f"Execution results for {symbol}: {results}")
            # Record trade for summary
            summary_manager.record_trade(symbol, strategy.__class__.__name__, orders, results, data)
            # Alerts
            if alert_manager:
                alert_manager.send_trade_alert(symbol, orders, results, data)
        except Exception:
            logging.exception(f"Error processing {symbol}")

    logging.info("Batch processing complete")
    # Metrics logging
    batch_latency = time.monotonic() - start_time
    try:
        # Emit structured metrics for monitoring
        logging.info("Batch metrics", extra={
            "trades_before": trades_before,
            "symbols_processed": symbols_processed,
            "orders_attempted": orders_attempted,
            "orders_executed": orders_executed,
            "total_notional": total_notional,
            "batch_latency": batch_latency
        })
    except Exception:
        logging.exception("Failed to log batch metrics")


async def stream_listener(selector, executor, api_key, secret_key, base_url, tickers):
    """Listen to Alpaca trade updates and rerun strategies on each update."""
    stream = TradingStream(
        api_key,
        secret_key,
        paper=True,
        raw_data=False
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
    # Daily summary email at market close
    scheduler.add_job(
        summary_manager.send_summary_email,
        'cron',
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
    configure_logging()
    """Parse args, validate env, and start event loop or one-off run."""

    load_dotenv('.env')

    parser = argparse.ArgumentParser(description='Options Strategy Engine (event-driven)')
    parser.add_argument('--once', action='store_true', help='Run once and exit')
    parser.add_argument('--dry-run', action='store_true', help='Dry-run mode (no real orders)')
    parser.add_argument('--phase', type=int, default=1, help='Strategy phase to include (default 1)')
    args = parser.parse_args()

    api_key = os.getenv('ALPACA_API_KEY')
    secret_key = os.getenv('ALPACA_SECRET_KEY')
    base_url = os.getenv('ALPACA_API_BASE_URL')
    tickers_env = os.getenv('TICKERS') or ''
    tickers = [t.strip().upper() for t in tickers_env.split(',') if t.strip()]

    if not validate_env(api_key, secret_key, base_url, tickers):
        sys.exit(1)

    selector = StrategySelector(phase=args.phase)
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
