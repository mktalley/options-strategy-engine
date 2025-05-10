import subprocess
import sys
import os
import ast

def test_cli_flag_overrides(tmp_path):
    # Path to the backtest script
    script = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, 'backtest.py'))
    # Prepare arguments with full overrides and invalid dates to force early exit after parsing
    args = [
        sys.executable, script,
        '--tickers', 'AAPL,msft',
        '--start', 'invalid',  # invalid date to trigger exit before run_backtest
        '--end', 'invalid',
        '--time-open', '10:15',
        '--time-close', '15:45',
        '--tz-name', 'Europe/London',
        '--end-buffer-minutes', '25',
        '--scanner-api-key', 'scan-key',
        '--scanner-secret-key', 'scan-secret',
        '--scanner-base-url', 'scan-base',
        '--scanner-data-url', 'scan-data',
        '--scanner-max-iv', '0.33',
        '--scanner-top-n', '7',
        '--scanner-cache-ttl', '200',
        '--scanner-cache-file', str(tmp_path / 'cache.json'),
        '--scanner-tickers-override', 'NFLX,AMZN',
    ]
    # Run the script and capture output
    result = subprocess.run(args, capture_output=True, text=True)
    # Expect a non-zero exit due to invalid date parsing
    assert result.returncode != 0
    # Capture and parse the printed CLI_ARGS
    stdout = result.stdout.strip()
    assert stdout.startswith('CLI_ARGS:'), f"Unexpected stdout: {stdout}"
    # Extract the dict string and parse
    dict_str = stdout[len('CLI_ARGS: '):]
    args_dict = ast.literal_eval(dict_str)
    # Assertions for TimeFilter overrides
    assert args_dict['time_open'] == '10:15'
    assert args_dict['time_close'] == '15:45'
    assert args_dict['tz_name'] == 'Europe/London'
    assert args_dict['end_buffer_minutes'] == 25
    # Assertions for Scanner overrides
    assert args_dict['scanner_api_key'] == 'scan-key'
    assert args_dict['scanner_secret_key'] == 'scan-secret'
    assert args_dict['scanner_base_url'] == 'scan-base'
    assert args_dict['scanner_data_url'] == 'scan-data'
    assert args_dict['scanner_max_iv'] == 0.33
    assert args_dict['scanner_top_n'] == 7
    assert args_dict['scanner_cache_ttl'] == 200
    assert args_dict['scanner_cache_file'] == str(tmp_path / 'cache.json')
    assert args_dict['scanner_tickers_override'] == 'NFLX,AMZN'