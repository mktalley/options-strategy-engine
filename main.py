import os
import logging
import argparse
from dotenv import load_dotenv
from pythonjsonlogger import jsonlogger
from utils import get_market_data, get_iv, get_trend, get_momentum, get_next_friday
from strategy_selector import StrategySelector
from trade_executor import TradeExecutor

def main(dry_run=False):
    # Load environment variables
    load_dotenv('.env')

    api_key = os.getenv('ALPACA_API_KEY')
    secret_key = os.getenv('ALPACA_SECRET_KEY')
    base_url = os.getenv('ALPACA_API_BASE_URL')
    tickers_env = os.getenv('TICKERS') or os.getenv('tickers')
    if not api_key or not secret_key or not tickers_env:
        logging.error('Missing configuration: ensure ALPACA_API_KEY, ALPACA_SECRET_KEY, and TICKERS are set in .env')
        return

    # Parse tickers list
    tickers = [t.strip().upper() for t in tickers_env.split(',') if t.strip()]
    if not tickers:
        logging.error('No valid tickers provided')
        return

    # Fetch market data
    try:
        market_data = get_market_data(tickers, api_key, secret_key, base_url)
    except Exception as e:
        logging.error(f'Failed to fetch market data: {e}')
        return

    selector = StrategySelector()
    try:
        executor = TradeExecutor(dry_run=dry_run)
    except Exception as e:
        logging.error(f'Failed to initialize TradeExecutor: {e}')
        return

    # Process each ticker
    for ticker, data in market_data.items():
        try:
            data['ticker'] = ticker
            data['expiration'] = get_next_friday()
            iv = get_iv(data)
            trend = get_trend(data)
            momentum = get_momentum(data)
            data.update({'iv': iv, 'trend': trend, 'momentum': momentum})

            logging.info(f"Metrics for {ticker}: IV={iv:.2f}, trend={trend}, momentum={momentum}")

            # Select and run strategy
            strategy = selector.select(trend, iv, momentum)
            orders = strategy.run(data)
            if not orders:
                logging.info(f'No orders generated for {ticker}')
                continue

            logging.info(f'Executing {len(orders)} order(s) for {ticker}: {orders}')
            results = executor.execute(orders)
            logging.info(f'Execution results for {ticker}: {results}')
        except Exception as e:
            logging.error(f'Error processing {ticker}: {e}', exc_info=True)

    logging.info('All strategies processed')


def configure_logging():
    # JSON logging formatter
    root_logger = logging.getLogger()
    handler = logging.StreamHandler()
    fmt = '%(asctime)s %(levelname)s %(name)s %(message)s'
    formatter = jsonlogger.JsonFormatter(fmt)
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.INFO)


if __name__ == '__main__':
    configure_logging()

    parser = argparse.ArgumentParser(description='Options Trading Bot')
    parser.add_argument('--once', action='store_true', help='Run the strategy once and exit')
    parser.add_argument('--dry-run', action='store_true', help='Enable dry-run mode (no real orders)')
    args = parser.parse_args()
    dry_run = args.dry_run

    if args.once:
        main(dry_run=dry_run)
    else:
        # Setup scheduler for US market hours (Monday-Friday, 9:30-16:00 ET)
        from apscheduler.schedulers.blocking import BlockingScheduler
        from zoneinfo import ZoneInfo
        tz = ZoneInfo('America/New_York')
        scheduler = BlockingScheduler(timezone=tz)
        # 9:30-9:59
        scheduler.add_job(lambda: main(dry_run=dry_run), 'cron', day_of_week='mon-fri', hour=9, minute='30-59')
        # 10:00-15:59
        scheduler.add_job(lambda: main(dry_run=dry_run), 'cron', day_of_week='mon-fri', hour='10-15', minute='*')
        # 16:00
        scheduler.add_job(lambda: main(dry_run=dry_run), 'cron', day_of_week='mon-fri', hour=16, minute=0)
        logging.getLogger().info('Scheduler started: running during US market hours')
        try:
            scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            logging.getLogger().info('Scheduler stopped.')
