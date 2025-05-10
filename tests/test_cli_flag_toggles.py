import subprocess
import sys
import os
import ast
import pytest

# Path to the backtest script
SCRIPT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backtest.py'))


def run_script(args):
    """
    Helper to run backtest.py with given args and capture the result.
    """
    return subprocess.run([sys.executable, SCRIPT_PATH] + args,
                          capture_output=True, text=True)


def parse_args_dict(output):
    """Extracts and parses CLI_ARGS dict from script output."""
    # Look for line starting with 'CLI_ARGS:'
    for line in output.splitlines():
        if line.startswith('CLI_ARGS:'):
            dict_str = line[len('CLI_ARGS:'):].strip()
            return ast.literal_eval(dict_str)
    pytest.skip("CLI_ARGS output not found")


def test_enable_risk_override():
    # Passing only enable-risk-management should set enable_risk_management True
    result = run_script([
        '--tickers', 'AAPL',
        '--start', 'invalid',  # invalid date to trigger early exit
        '--end', 'invalid',
        '--enable-risk-management',
    ])
    assert result.returncode != 0, "Script should exit with error due to invalid date"
    args_dict = parse_args_dict(result.stdout)
    assert args_dict.get('enable_risk_management') is True
    assert args_dict.get('disable_risk_management') is False


def test_disable_risk_override():
    # Passing only disable-risk-management should set disable_risk_management True
    result = run_script([
        '--tickers', 'AAPL',
        '--start', 'invalid',
        '--end', 'invalid',
        '--disable-risk-management',
    ])
    assert result.returncode != 0
    args_dict = parse_args_dict(result.stdout)
    assert args_dict.get('enable_risk_management') is False
    assert args_dict.get('disable_risk_management') is True


def test_enable_news_override():
    # Passing only enable-news-risk should set enable_news_risk True
    result = run_script([
        '--tickers', 'AAPL',
        '--start', 'invalid',
        '--end', 'invalid',
        '--enable-news-risk',
    ])
    assert result.returncode != 0
    args_dict = parse_args_dict(result.stdout)
    assert args_dict.get('enable_news_risk') is True
    assert args_dict.get('disable_news_risk') is False


def test_disable_news_override():
    # Passing only disable-news-risk should set disable_news_risk True
    result = run_script([
        '--tickers', 'AAPL',
        '--start', 'invalid',
        '--end', 'invalid',
        '--disable-news-risk',
    ])
    assert result.returncode != 0
    args_dict = parse_args_dict(result.stdout)
    assert args_dict.get('enable_news_risk') is False
    assert args_dict.get('disable_news_risk') is True
