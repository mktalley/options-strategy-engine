#!/usr/bin/env python3
"""
monitor.py: Real-time streaming of trade updates via Alpaca WebSocket (paper trading mode).
"""
import os
import asyncio
import logging
from dotenv import load_dotenv
from pythonjsonlogger import jsonlogger
from alpaca.trading.stream import TradingStream


def configure_logging():
    """
    Configure root logger to output JSON-formatted logs to stdout.
    """
    root_logger = logging.getLogger()
    handler = logging.StreamHandler()
    fmt = '%(asctime)s %(levelname)s %(name)s %(message)s'
    formatter = jsonlogger.JsonFormatter(fmt)
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.INFO)


async def main():
    # Load environment variables from .env
    load_dotenv('.env')
    api_key = os.getenv('ALPACA_API_KEY')
    secret_key = os.getenv('ALPACA_SECRET_KEY')
    base_url = os.getenv('ALPACA_API_BASE_URL')

    if not api_key or not secret_key:
        logging.error('Missing Alpaca API credentials in environment')
        return

    # Initialize trading stream in paper mode
    stream = TradingStream(
        api_key,
        secret_key,
        paper=True,
        raw_data=False,
        url_override=base_url
    )

    @stream.subscribe_trade_updates
    async def on_trade_update(update):
        # update is a TradeUpdate object
        logging.info(f"Trade update received: {update}")

    logging.info('Starting trade updates stream (paper trading)')
    # Run the WebSocket listener until killed
    await stream._run_forever()


if __name__ == '__main__':
    configure_logging()
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.getLogger().info('Trade updates monitoring stopped.')
