import os
import sys
import subprocess
import pytest
from pathlib import Path

def test_backtest_cli_creates_output_dirs(tmp_path):
    # Use invalid dates to stop before API calls, but after dirs are created
    base = tmp_path / 'out'
    script = os.path.abspath(
        os.path.join(os.path.dirname(__file__), os.pardir, 'backtest.py')
    )
    tickers = 'AAPL,MSFT'
    start = 'invalid'
    end = 'invalid'
    args = [
        sys.executable,
        script,
        '--tickers', tickers,
        '--start', start,
        '--end', end,
        '--output-dir', str(base)
    ]
    result = subprocess.run(args, capture_output=True, text=True)
    # Expect non-zero exit due to invalid dates
    assert result.returncode != 0

    # Calculate expected run folder
    run_id = f"{start}_to_{end}_{tickers.replace(',', '_')}"
    run_folder = base / run_id

    # Verify that the base and subdirectories exist
    assert run_folder.exists(), f"Run folder {run_folder} was not created"
    assert (run_folder / 'results_csv').exists(), "results_csv folder missing"
    assert (run_folder / 'equity_curves').exists(), "equity_curves folder missing"
    # Verify log file was redirected inside run folder
    log_file = run_folder / 'backtest.log'
    assert log_file.exists(), f"Log file {log_file} was not created"

    # There should be no CSV yet since backtest didn't run
    csv_files = list((run_folder / 'results_csv').glob('*.csv'))
    assert not csv_files, "Unexpected CSV file created"