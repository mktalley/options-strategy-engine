import subprocess
import sys
import os
import pytest

# Path to the backtest script
SCRIPT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backtest.py'))


def run_script(args):
    """
    Helper to run backtest.py with given args and capture the result.
    """
    return subprocess.run([sys.executable, SCRIPT_PATH] + args,
                          capture_output=True, text=True)


def test_conflicting_risk_flags():
    # Passing both enable and disable for risk management should error
    result = run_script([
        '--tickers', 'AAPL',
        '--start', '2025-01-01',
        '--end', '2025-01-02',
        '--enable-risk-management',
        '--disable-risk-management',
    ])
    assert result.returncode != 0, "Script should exit with error when both risk flags are set"
    stderr = result.stderr or result.stdout
    assert 'Cannot specify both --enable-risk-management and --disable-risk-management' in stderr


def test_conflicting_news_flags():
    # Passing both enable and disable for news risk should error
    result = run_script([
        '--tickers', 'AAPL',
        '--start', '2025-01-01',
        '--end', '2025-01-02',
        '--enable-news-risk',
        '--disable-news-risk',
    ])
    assert result.returncode != 0, "Script should exit with error when both news flags are set"
    stderr = result.stderr or result.stdout
    assert 'Cannot specify both --enable-news-risk and --disable-news-risk' in stderr
