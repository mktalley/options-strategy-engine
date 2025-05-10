import os
import sys
import subprocess
import pandas as pd
import pytest
from pathlib import Path

SCRIPT_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', 'optimize_backtest.py')
)

def run_minimal_optimize(output_dir_arg=None):
    # Common args for minimal grid: one iv, one end-buffer, one capital
    args = [
        sys.executable, SCRIPT_PATH,
        '--tickers', 'AAPL',
        '--start', 'invalid',
        '--end', 'invalid',
        '--iv-thresholds', '0.2',
        '--end-buffer-minutes', '5',
        '--initial-capitals', '1000'
    ]
    if output_dir_arg is not None:
        args += ['--output-dir', str(output_dir_arg)]
    result = subprocess.run(args, capture_output=True, text=True)
    assert result.returncode == 0, f"Optimize script failed: {result.stderr}"

@pytest.mark.parametrize("use_env_var", [True, False])
def test_optimize_backtest_default_and_override_output_dir(tmp_path, monkeypatch, use_env_var):
    # Prepare environment or CLI override
    cli_override_dir = tmp_path / 'cli_dir'
    env_dir = tmp_path / 'env_dir'
    monkeypatch.delenv('OPTIMIZE_OUTPUT_DIR', raising=False)
    if use_env_var:
        # Test default via env var
        monkeypatch.setenv('OPTIMIZE_OUTPUT_DIR', str(env_dir))
        run_minimal_optimize(output_dir_arg=None)
        summary_dir = env_dir
    else:
        # Test CLI override
        run_minimal_optimize(output_dir_arg=cli_override_dir)
        summary_dir = cli_override_dir

    summary_path = Path(summary_dir) / 'summary.csv'
    assert summary_path.exists(), f"summary.csv not found in {summary_dir}"
    # Check header
    df = pd.read_csv(summary_path)
    expected_cols = [
        'iv_threshold', 'end_buffer', 'initial_capital',
        'enable_ml', 'enable_scanning',
        'enable_risk_management', 'enable_news_risk', 'net_pl'
    ]
    assert list(df.columns) == expected_cols
