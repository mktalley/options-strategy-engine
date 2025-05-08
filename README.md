# Options Strategy Engine

Automated options trading bot that selects and executes option strategies based on market metrics (IV, trend, momentum).

---

## Features

- Phase-1 strategies: LongCall, LongPut, Straddle, IronCondor, VerticalSpread
- Phase-2 strategies: BullCallSpread, BearPutSpread, CalendarSpread, IronButterfly
- Stub strategies (to be implemented): GammaScalping, Wheel, ZeroDTE
- Scheduler: runs 9:30–16:00 ET, Monday–Friday via APScheduler
- Dry-run mode to preview orders without submission
- Retry logic on order submission via Tenacity
- Dockerized for easy deployment

## Prerequisites

- Docker (v20+) and Docker Compose (v1.29+)
- Alpaca credentials (paper-trading API key & secret)

## Configuration

1. Copy `.env.example` to `.env` in the project root:
   ```bash
   cp .env.example .env
   ```
2. Edit `.env` and fill in your credentials and desired tickers:
   ```ini
   ALPACA_API_KEY=PKSZ...YOURKEY
   ALPACA_SECRET_KEY=d91h...YOURSECRET
   # Paper trading base URL
   ALPACA_API_BASE_URL=https://paper-api.alpaca.markets
   # Optional data override
   # ALPACA_DATA_BASE_URL=https://data.alpaca.markets
   TICKERS=SPY
   # (You can add multiple, comma-separated)
   ```

## Feature Toggles and Email Summary Configuration

You can enable or disable additional features using environment variables in your `.env` file. By default, all features are disabled (`false`):

- `ENABLE_TIME_FILTER`: Time-based trading conditions (pre-market, after-hours, end-of-day buffer)
- `ENABLE_SCANNING`: Dynamic multi-symbol scanning and sector analysis
- `ENABLE_RISK_MANAGEMENT`: Risk management adjustments (trailing stops, position sizing, stop-loss/profit-taking)
- `ENABLE_NEWS_RISK`: News and event risk management (economic calendar checks, sentiment analysis)
- `ENABLE_ML`: AI/ML-based trade prediction and dynamic strategy adjustments
- `ENABLE_ALERTS`: Real-time alerts on trades and market changes

## Backtest Pipeline Behavior
When running `backtest.py`, the engine applies the following steps in order, driven by feature toggles:

1. **Scanning** (`ENABLE_SCANNING`): Determine the list of tickers dynamically via `Scanner.scan()` when enabled.
2. **Time Filter** (`ENABLE_TIME_FILTER`): Skip bars outside regular market hours, including pre-market, after-hours, and end-of-day buffer.
3. **Strategy Selection**: Select a strategy based on IV, trend, and momentum metrics.
4. **Order Generation**: Generate orders via the selected strategy.
5. **Risk Management** (`ENABLE_RISK_MANAGEMENT`): Adjust orders for position sizing, stop-loss, take-profit, and trailing stops.
6. **News Risk** (`ENABLE_NEWS_RISK`): Block trades around high-impact events or negative sentiment.
7. **ML Adjustments** (`ENABLE_ML`): Filter or adjust orders using the trained ML model.
8. **Dry-Run Execution**: Execute orders in dry-run mode to return simulated responses.
9. **Alerts** (`ENABLE_ALERTS`): Send trade alerts with execution details and notional thresholds.
10. **Record P/L**: Simulate entry/exit prices for P/L calculation and output results to CSV.
11. **Equity Curve Generation**: Simulate and save an equity curve PNG using the specified starting capital via `--initial-capital`.


To enable a feature, set the variable to `true` in your `.env` file. For example:

```ini
ENABLE_TIME_FILTER=true
ENABLE_SCANNING=true
ENABLE_RISK_MANAGEMENT=true
ENABLE_NEWS_RISK=true
ENABLE_ML=true
ENABLE_ALERTS=true
```
## Alert Manager Configuration

When `ENABLE_ALERTS` is enabled, configure the Alert Manager's external alert channels, notional threshold, and rate limiting using the following environment variables in your `.env` file (defaults shown in `.env.example`):

- `ALERT_WEBHOOK_URL`: Slack/Webhook URL for external alerts (default: None)
- `ALERT_TELEGRAM_BOT_TOKEN`: Telegram Bot API token for external alerts (default: None)
- `ALERT_TELEGRAM_CHAT_ID`: Telegram chat ID for external alerts (default: None)
- `ALERT_MIN_NOTIONAL`: Minimum trade notional (price × quantity) to trigger external alerts; trades below this notional are suppressed (default: 0)
- `ALERT_RATE_LIMIT_PER_MIN`: Maximum number of external alerts allowed within the rate limit window (default: 60)
- `ALERT_RATE_LIMIT_WINDOW`: Rate limit window in seconds over which `ALERT_RATE_LIMIT_PER_MIN` applies (default: 60)

## News & Calendar Risk Management

## Time-based Trading Conditions

When `ENABLE_TIME_FILTER` is enabled, the bot will only initiate trades during the configured trading window, excluding pre-market, after-hours, and an end-of-day buffer. Configure these parameters in your `.env` file:

- `MARKET_OPEN_TIME`: Market open time in `HH:MM` (America/New_York), default `09:30`
- `MARKET_CLOSE_TIME`: Market close time in `HH:MM` (America/New_York), default `16:00`
- `TIME_FILTER_END_BUFFER_MINUTES`: Minutes before market close to stop new trades, default `10`
- `PRE_MARKET_START`: Optional pre-market session start time in `HH:MM`, default `04:00`
- `AFTER_HOURS_END`: Optional after-hours session end time in `HH:MM`, default `20:00`


When `ENABLE_NEWS_RISK` is enabled, ensure the following environment variables are set in your `.env` file (defaults shown in `.env.example`):

- `ECONOMIC_CALENDAR_API_KEY`: FinancialModelingPrep API key for economic calendar (required).
- `FINNHUB_API_KEY`: Finnhub API key for company news (required).
- `ECONOMIC_CALENDAR_LOOKAHEAD_DAYS`: Number of days ahead to fetch calendar events (integer, default 2).
- `NEWS_SENTIMENT_WINDOW_DAYS`: Number of days back to fetch news for sentiment analysis (integer, default 1).
- `NEWS_SENTIMENT_THRESHOLD`: Average sentiment threshold; trades blocked if average sentiment is below this value (float, default -0.3).
- `NEWS_RISK_KEYWORDS`: Comma-separated list of keywords; trades blocked if headlines contain any of these (default: fomc, non farm, nfp, fed, layoffs, bankruptcy, ceo change, merger, acquisition, geopolitical, earthquake, hurricane, scandal).


## Fetching Historical Data

Use the `scripts/fetch_data.py` script to pull daily OHLCV CSV data from Alpaca for one or more tickers:

```bash
# Install dependencies (if not already installed)
pip install -r requirements.txt

# Fetch data for SPY and QQQ from 2020-01-01 to 2025-01-01
eval "$(which python3) scripts/fetch_data.py \
  --tickers SPY,QQQ \
  --start 2020-01-01 \
  --end 2025-01-01 \
  --outdir data"
```

This will save CSV files (e.g., `data/SPY.csv`, `data/QQQ.csv`) containing `Date,Open,High,Low,Close,Volume` columns, ready to feed into the Backtrader engine or any other backtest.



## Backtesting with Backtrader

Use the `scripts/backtrader_engine.py` script to run backtests on your CSV data:

```bash
# Ensure dependencies are installed
pip install -r requirements.txt

# Backtest using SPY and QQQ data
python scripts/backtrader_engine.py \
  --csv data/SPY.csv data/QQQ.csv \
  --iv-threshold 0.25 \
  --cash 100000
```

This will output starting and final portfolio values and generate a plot of equity over time.

## Training the ML Model

Once you have a `backtest_results.csv` from `backtest.py`, train the ML model:

```bash
python scripts/train_model.py \
  --input backtest_results.csv \
  --output model.joblib
```

The trained model will be saved as `model.joblib` and can be used in production (set `ENABLE_ML=true` in `.env`).

## End-to-End Pipeline Example

```bash
# 1. Fetch historical OHLCV data
python scripts/fetch_data.py \
  --tickers SPY,QQQ \
  --start 2020-01-01 \
  --end 2025-01-01 \
  --outdir data

# 2. Run backtest, export features, and generate equity curve
python backtest.py --tickers SPY,QQQ \
  --start 2020-01-01 --end 2025-01-01 --initial-capital 100000




# 3. Train ML model
python scripts/train_model.py --input backtest_results.csv --output model.joblib
```

After training, point your production bot at `model.joblib` (or update `ML_MODEL_PATH` in `.env`) and enable ML via `ENABLE_ML=true`.
## Running with Docker Compose

All commands assume you are in the project directory containing `docker-compose.yml`.

- Build the image:
  ```bash
  docker-compose build
  ```

- Dry-run a single execution (no real orders):
  ```bash
  docker-compose run --rm options-bot python main.py --once --dry-run
  ```

- Dry-run Phase 2 strategies (no real orders, include Phase 2 classes):
  ```bash
  docker-compose run --rm options-bot python main.py --once --dry-run --phase 2
  ```

- Run the scheduled bot (runs during market hours):
  ```bash
  docker-compose up -d
  ```

- To view logs:
  ```bash
  docker-compose logs -f
  ```

- Stop the bot:
  ```bash
  docker-compose down
  ```

## Testing

You can run the existing pytest suite inside the container:
```bash
docker-compose run --rm options-bot pytest
```

## Extending & Going Live

- Once you’re comfortable with paper trading, remove `--dry-run` and switch `ALPACA_API_BASE_URL` to the live endpoint.
- Implement or tune stub strategies in `strategies.py`.
- Add risk guardrails (daily P/L, circuit breakers, position limits) as needed in the code.

---

Happy trading! 🚀