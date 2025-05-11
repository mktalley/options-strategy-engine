import os
import argparse
import logging
from datetime import datetime, timedelta, time
import sys
from dotenv import load_dotenv
import pandas as pd
load_dotenv()
import socket
# Ensure network calls timeout to avoid hanging on DNS errors
socket.setdefaulttimeout(10)


from simulate_equity import simulate_equity  # integrate equity simulation


import numpy as np
from time_filter import TimeFilter
from scanner import Scanner
from risk_manager import RiskManager
from news_manager import NewsManager
from model_manager import ModelManager
from alert_manager import AlertManager
from utils import get_iv, get_trend, get_momentum, get_next_friday
from strategy_selector import StrategySelector
from trade_executor import TradeExecutor

# Alpaca data client imports
from alpaca.data.historical.stock import StockHistoricalDataClient, StockBarsRequest
from alpaca.data.historical.option import OptionHistoricalDataClient, OptionBarsRequest
from alpaca.data.timeframe import TimeFrame

# Configure logging to write to file and console
log_file = os.getenv('BACKTEST_LOG', 'backtest.log')
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(log_file, mode='w'),
        logging.StreamHandler()
    ]
)

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
    try:
        resp = client.get_stock_bars(req)
    except Exception as e:
        logging.error(f"Error fetching bars for {ticker}: {e}")
        return []
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
    iv_threshold: float,
    results_file: str = "backtest_results.csv",
    phase: int = 1,
    allowed_strategies: list = None,
    enable_scanning: bool = False,
    enable_risk_management: bool = False,
    enable_news_risk: bool = False,
    enable_ml: bool = False,
    enable_alerts: bool = False,
    stop_loss_pct: float = 0.01,
    take_profit_pct: float = 0.08,
    atr_stop_multiplier: float = 1.5,
    atr_take_profit_multiplier: float = 2.5,
    trailing_stop_pct: float = 0.02,
    time_open: str = "09:30",
    time_close: str = "16:00",
    tz_name: str = "America/New_York",
    end_buffer_minutes: int = None,
    ml_threshold: float = 0.5,
    # Scanner parameters
    scanner_api_key: str = None,
    scanner_secret_key: str = None,
    scanner_base_url: str = None,
    scanner_data_url: str = None,
    scanner_max_iv: float = None,
    scanner_top_n: int = None,
    scanner_cache_ttl: int = None,
    scanner_cache_file: str = None,
    scanner_tickers_override: str = None,
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

    # Feature toggles via environment
    ENABLE_TIME_FILTER = os.getenv('ENABLE_TIME_FILTER', 'true').lower() in ('true', '1')  # default enabled
    ENABLE_SCANNING = os.getenv('ENABLE_SCANNING', 'false').lower() in ('true', '1')
    ENABLE_RISK_MANAGEMENT = os.getenv('ENABLE_RISK_MANAGEMENT', 'false').lower() in ('true', '1')
    ENABLE_NEWS_RISK = os.getenv('ENABLE_NEWS_RISK', 'false').lower() in ('true', '1')
    ENABLE_ML = os.getenv('ENABLE_ML', 'false').lower() in ('true', '1')
    ENABLE_ALERTS = os.getenv('ENABLE_ALERTS', 'false').lower() in ('true', '1')
    # Override feature toggles from CLI flags (tri-state override)
    if enable_scanning is not None:
        ENABLE_SCANNING = enable_scanning
    if enable_ml is not None:
        ENABLE_ML = enable_ml
    if enable_risk_management is not None:
        ENABLE_RISK_MANAGEMENT = enable_risk_management
    if enable_news_risk is not None:
        ENABLE_NEWS_RISK = enable_news_risk


    # Instantiate modules based on toggles
    # Global skip flag for option P/L simulation (avoid hitting rate limits)
    SKIP_OPTION_PRICES = os.getenv('SKIP_OPTION_PRICES', 'false').lower() in ('true', '1')
    # Instantiate modules based on toggles
    time_filter = TimeFilter(
        time_open=time_open,
        time_close=time_close,
        tz_name=tz_name,
        end_buffer_minutes=end_buffer_minutes
    ) if ENABLE_TIME_FILTER else None
    scanner_mod = Scanner(
        api_key=scanner_api_key,
        secret_key=scanner_secret_key,
        base_url=scanner_base_url,
        data_url=scanner_data_url,
        max_iv=scanner_max_iv,
        top_n=scanner_top_n,
        cache_ttl=scanner_cache_ttl,
        cache_file=scanner_cache_file,
        tickers_override=scanner_tickers_override
    ) if ENABLE_SCANNING else None
    risk_manager = RiskManager() if ENABLE_RISK_MANAGEMENT else None
    news_manager = NewsManager() if ENABLE_NEWS_RISK else None
    model_manager = ModelManager() if ENABLE_ML else None
    alert_manager = AlertManager() if ENABLE_ALERTS else None

    # Determine tickers for backtest
    run_tickers = scanner_mod.scan() if scanner_mod else tickers
    selector = StrategySelector(iv_threshold=iv_threshold)
    executor = TradeExecutor(dry_run=True)

    records = []
    for ticker in run_tickers:
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

            
            # Time filter: skip bar if market closed
            if time_filter and not time_filter.is_market_open(datetime.combine(bar_date, time(12, 0))):
                logging.info(f"Market closed on {bar_date}. Skipping trade generation for {ticker}")
                continue

            # Strategy selection and order generation
            strategy = selector.select(trend, iv, momentum)
            orders = strategy.run(data)
            if not orders:
                continue

            # Risk management adjustments
            if risk_manager:
                orders = risk_manager.adjust_orders(orders, data)
            # News risk management: skip if not allowed
            if news_manager and not news_manager.is_trade_allowed(ticker, data):
                logging.info(f"Trade for {ticker} on {bar_date} blocked by news risk manager")
                continue

            # ML model adjustments
            if model_manager:
                orders = model_manager.adjust_orders(orders, data)
            if not orders:
                continue

            # Dry-run execution (requests are returned)
            reqs = executor.execute(orders)

            # Alerts
            if alert_manager:
                alert_manager.send_trade_alert(ticker, orders, reqs, data)
            # Record each trade detail
            if orders:
                if SKIP_OPTION_PRICES:
                    logging.info("Skipping option price fetches due to SKIP_OPTION_PRICES flag")
                else:
                    # Simulated dry-run, record each individual order for P/L simulation
                    for order in orders:
                        # Fetch entry mid-price
                        try:
                            entry_start = datetime.combine(bar_date, time(0, 0))
                            entry_end = datetime.combine(bar_date, time(23, 59))
                            entry_req = OptionBarsRequest(
                                symbol_or_symbols=[order['symbol']],
                                timeframe=TimeFrame.Minute,
                                start=entry_start,
                                end=entry_end,
                                limit=1000,
                                sort="asc"
                            )
                            entry_resp = option_client.get_option_bars(entry_req)
                            if hasattr(entry_resp, 'data'):
                                entry_map = entry_resp.data
                            elif isinstance(entry_resp, dict):
                                entry_map = entry_resp
                            else:
                                entry_map = {}
                            entry_bars = entry_map.get(order['symbol'], [])
                            entry_price = getattr(entry_bars[0], 'close', None) if entry_bars else None
                        except Exception as e:
                            logging.warning(f"Failed to fetch entry price for {order['symbol']} on {bar_date}: {e}")
                            entry_price = None
                        # Fetch exit mid-price
                        try:
                            exit_date = data['expiration']
                            exit_start = datetime.combine(exit_date, time(0, 0))
                            exit_end = datetime.combine(exit_date, time(23, 59))
                            exit_req = OptionBarsRequest(
                                symbol_or_symbols=[order['symbol']],
                                timeframe=TimeFrame.Minute,
                                start=exit_start,
                                end=exit_end,
                                limit=1000,
                                sort="asc"
                            )
                            exit_resp = option_client.get_option_bars(exit_req)
                            if hasattr(exit_resp, 'data'):
                                exit_map = exit_resp.data
                            elif isinstance(exit_resp, dict):
                                exit_map = exit_resp
                            else:
                                exit_map = {}
                            exit_bars = exit_map.get(order['symbol'], [])
                            exit_price = getattr(exit_bars[-1], 'close', None) if exit_bars else None
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
                'entry_date': bar_date,
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

    # Total P/L across all trades
    total_pl = df['pl'].sum()
    print(f"Total P/L: ${total_pl:.2f}")

    # P/L breakdown by strategy
    print("P/L by strategy:")
    pl_group = df.groupby('strategy')['pl']
    pl_summary = pl_group.agg(total_pl='sum', avg_pl='mean', trades='count')
    wins = pl_group.apply(lambda x: (x > 0).sum()).rename('wins')
    losses = pl_group.apply(lambda x: (x <= 0).sum()).rename('losses')
    pl_summary = pl_summary.join(wins).join(losses)
    pl_summary['win_rate'] = pl_summary['wins'] / pl_summary['trades']
    print(pl_summary)

    # Save to CSV
    out_csv = results_file
    df.to_csv(out_csv, index=False)
    print(f"Detailed results written to {out_csv}")
    return df


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Backtest options strategy signal generation")
    parser.add_argument("--tickers", required=True,
                        help="Comma-separated list of tickers to backtest")
    parser.add_argument("--start", required=True,
                        help="Start date YYYY-MM-DD")
    parser.add_argument("--time-open", type=str, default=None,
                        help="Market open time HH:MM, overrides env MARKET_OPEN_TIME")
    parser.add_argument("--time-close", type=str, default=None,
                        help="Market close time HH:MM, overrides env MARKET_CLOSE_TIME")
    parser.add_argument("--tz-name", type=str, default="America/New_York",
                        help="Timezone name for time filter, overrides default America/New_York")
    parser.add_argument("--end-buffer-minutes", type=int, default=None,
                        help="Minutes before market close to stop new trades, overrides env TIME_FILTER_END_BUFFER_MINUTES")
    # Scanner parameters
    parser.add_argument("--scanner-api-key", type=str, default=None,
                        help="Alpaca API key for Scanner, overrides env ALPACA_API_KEY")
    parser.add_argument("--scanner-secret-key", type=str, default=None,
                        help="Alpaca secret key for Scanner, overrides env ALPACA_SECRET_KEY")
    parser.add_argument("--scanner-base-url", type=str, default=None,
                        help="Alpaca base URL for Scanner, overrides env ALPACA_API_BASE_URL")
    parser.add_argument("--scanner-data-url", type=str, default=None,
                        help="Data URL for Scanner, overrides env ALPACA_DATA_BASE_URL")
    parser.add_argument("--scanner-max-iv", type=float, default=None,
                        help="Maximum IV threshold for Scanner, overrides env SCANNER_MAX_IV")
    parser.add_argument("--scanner-top-n", type=int, default=None,
                        help="Number of top symbols for Scanner, overrides env SCANNER_TOP_N")
    parser.add_argument("--scanner-cache-ttl", type=int, default=None,
                        help="Cache TTL in seconds for Scanner, overrides env SCANNER_CACHE_TTL")
    parser.add_argument("--scanner-cache-file", type=str, default=None,\
                        help="Cache file path for Scanner, overrides env SCANNER_CACHE_FILE")
    # CLI feature toggles: override env settings
    parser.add_argument("--enable-scanning", action="store_true",
                        help="Override env, force enable Scanner")
    parser.add_argument("--disable-scanning", action="store_true",
                        help="Override env, force disable Scanner")
    parser.add_argument("--enable-ml", action="store_true",
                        help="Override env, force enable ML filtering")
    parser.add_argument("--disable-ml", action="store_true",
                        help="Override env, force disable ML filtering")
    parser.add_argument("--enable-risk-management", action="store_true",
                        help="Override env, force enable risk management")
    parser.add_argument("--disable-risk-management", action="store_true",
                        help="Override env, force disable risk management")
    parser.add_argument("--enable-news-risk", action="store_true",
                        help="Override env, force enable news risk")
    parser.add_argument("--disable-news-risk", action="store_true",
                        help="Override env, force disable news risk")

    parser.add_argument("--scanner-tickers-override", type=str, default=None,
                        help="Override tickers for Scanner, comma-separated or list, overrides env TICKERS")

    parser.add_argument("--end", required=True,
                        help="End date YYYY-MM-DD")
    parser.add_argument("--iv-threshold", type=float, default=0.25,
                        help="IV threshold for high/low decision in StrategySelector")
    parser.add_argument("--initial-capital", type=float, default=100000.0, help="Starting capital for equity simulation")
    parser.add_argument("--results-file", default="backtest_results.csv", help="Path to write backtest results CSV")
    parser.add_argument("--output-dir", default=os.getenv('BACKTEST_OUTPUT_DIR', 'outputs/backtests'), help="Base directory for backtest outputs (results and equity_curves subdirectories) [env: BACKTEST_OUTPUT_DIR]")
    # Strategy and feature flags


    args = parser.parse_args()
    # Debug: print parsed CLI args for integration testing
    
    print(f"CLI_ARGS: {vars(args)}")

    # Organize output directories
    # Determine base output directory (CLI flag or default)
    base_output = args.output_dir
    # Create run-specific directory under base output
    run_id = f"{args.start}_to_{args.end}_{args.tickers.replace(',', '_')}"
    run_folder = os.path.join(base_output, run_id)
    # Subdirectories for CSV results and equity curves
    results_dir = os.path.join(run_folder, "results_csv")
    equity_dir = os.path.join(run_folder, "equity_curves")
    os.makedirs(results_dir, exist_ok=True)
    os.makedirs(equity_dir, exist_ok=True)
    # Override results_file to write in organized folder with descriptive filename
    csv_filename = f"backtest_{run_id}.csv"
    args.results_file = os.path.join(results_dir, csv_filename)
    # Set equity output directory for simulate_equity
    os.environ["EQUITY_OUTPUT_DIR"] = equity_dir
    # Redirect log file into the run-specific output folder
    # Remove default file handlers (from initial basicConfig)
    for handler in logging.root.handlers[:]:
        if isinstance(handler, logging.FileHandler):
            logging.root.removeHandler(handler)
    # Add new file handler pointing to the run folder
    run_log = os.path.join(run_folder, 'backtest.log')
    fh = logging.FileHandler(run_log, mode='w')
    fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logging.root.addHandler(fh)
    logging.info(f"Backtest logs will be written to {run_log}")

    # Determine CLI overrides for feature toggles (tri-state): scanning and ML and risk and news risk
    if args.enable_scanning and args.disable_scanning:
        parser.error("Cannot specify both --enable-scanning and --disable-scanning")
    if args.enable_scanning:
        scanning_override = True
    elif args.disable_scanning:
        scanning_override = False
    else:
        scanning_override = None
    
    if args.enable_ml and args.disable_ml:
        parser.error("Cannot specify both --enable-ml and --disable-ml")
    if args.enable_ml:
        ml_override = True
    elif args.disable_ml:
        ml_override = False
    else:
        ml_override = None

    # Determine CLI overrides for risk management toggle
    if args.enable_risk_management and args.disable_risk_management:
        parser.error("Cannot specify both --enable-risk-management and --disable-risk-management")
    if args.enable_risk_management:
        risk_override = True
    elif args.disable_risk_management:
        risk_override = False
    else:
        risk_override = None

    # Determine CLI overrides for news risk toggle
    if args.enable_news_risk and args.disable_news_risk:
        parser.error("Cannot specify both --enable-news-risk and --disable-news-risk")
    if args.enable_news_risk:
        news_override = True
    elif args.disable_news_risk:
        news_override = False
    else:
        news_override = None

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

    df = run_backtest(
        tickers,
        start_date=start_date,
        end_date=end_date,
        api_key=api_key,
        secret_key=secret_key,
        base_url=base_url,
        data_url=data_url,
        iv_threshold=args.iv_threshold,
        results_file=args.results_file,
        time_open=args.time_open,
        time_close=args.time_close,
        tz_name=args.tz_name,
        end_buffer_minutes=args.end_buffer_minutes,
        scanner_api_key=args.scanner_api_key,
        scanner_secret_key=args.scanner_secret_key,
        scanner_base_url=args.scanner_base_url,
        scanner_data_url=args.scanner_data_url,
        scanner_max_iv=args.scanner_max_iv,
        scanner_top_n=args.scanner_top_n,
        scanner_cache_ttl=args.scanner_cache_ttl,
        scanner_cache_file=args.scanner_cache_file,
        scanner_tickers_override=args.scanner_tickers_override,
        enable_scanning=scanning_override,
        enable_ml=ml_override,
        enable_risk_management=risk_override,
        enable_news_risk=news_override,
    )

    # Simulate equity curve from results
    if df is not None and not df.empty:
        simulate_equity(args.results_file, args.start, args.end, args.initial_capital)
