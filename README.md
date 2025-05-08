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

To enable a feature, set the variable to `true` in your `.env` file. For example:

```ini
ENABLE_TIME_FILTER=true
ENABLE_SCANNING=true
ENABLE_RISK_MANAGEMENT=true
ENABLE_NEWS_RISK=true
ENABLE_ML=true
ENABLE_ALERTS=true
```
## News & Calendar Risk Management

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

# 2. Run backtest and export features
python backtest.py --tickers SPY,QQQ \
  --start 2020-01-01 --end 2025-01-01

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