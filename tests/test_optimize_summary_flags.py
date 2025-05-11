import subprocess
import sys
import os
import pandas as pd
import pytest
from pathlib import Path

SCRIPT_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', 'optimize_backtest.py')
)

def test_optimize_summary_includes_risk_and_news(tmp_path):
    """
    Test that optimize_backtest.py generates a summary.csv with correct headers,
    number of rows, and includes risk and news toggles columns.
    """
    tickers = 'AAPL'
    # Use invalid dates to force early exit in backtest.py
    start = 'invalid'
    end = 'invalid'
    output_dir = tmp_path / 'opt'

    # Run optimize_backtest.py with minimal grid: one iv, one end-buffer, one capital
    args = [
        sys.executable, SCRIPT_PATH,
        '--tickers', tickers,
        '--start', start,
        '--end', end,
        '--iv-thresholds', '0.2',
        '--end-buffer-minutes', '5',
        '--initial-capitals', '1000',
        '--output-dir', str(output_dir)
    ]
    result = subprocess.run(args, capture_output=True, text=True)
    assert result.returncode == 0, f"Optimization script failed: {result.stderr}"

    summary_path = output_dir / 'summary.csv'
    assert summary_path.exists(), "summary.csv was not created"

    # Read the summary CSV
    df = pd.read_csv(summary_path)
    # Expected columns
    expected_cols = [
        'iv_threshold',
        'end_buffer',
        'initial_capital',
        'enable_ml',
        'enable_scanning',
        'enable_risk_management',
        'enable_news_risk',
        'net_pl'
    ]
    assert list(df.columns) == expected_cols, f"Unexpected columns: {df.columns.tolist()}"

    # Number of rows should equal 2^4 combos = 16
    assert len(df) == 16, f"Expected 16 rows for 16 flag combos, got {len(df)}"

    # Check that enable_risk_management and enable_news_risk columns include both True and False
    # Since backtest.py exits early, net_pl should be empty/NaN
    # Columns are read as boolean or object; convert to string for comparison
    risk_vals = df['enable_risk_management'].astype(str).unique().tolist()
    news_vals = df['enable_news_risk'].astype(str).unique().tolist()
    assert set(risk_vals) == {'True', 'False'}, f"Unexpected risk flag values: {risk_vals}"
    assert set(news_vals) == {'True', 'False'}, f"Unexpected news flag values: {news_vals}"

    # net_pl should be NaN for all rows
    assert df['net_pl'].isna().all(), "Expected net_pl to be NaN for early-exit backtests"
