import os
import sys
import subprocess
import pandas as pd
import pytest
from pathlib import Path

@pytest.fixture(autouse=True)
def cleanup_env(monkeypatch):
     # Ensure no stray EQUITY_OUTPUT_DIR influences tests
     monkeypatch.delenv('EQUITY_OUTPUT_DIR', raising=False)
     yield


def test_simulate_equity_cli_writes_png_with_flag(tmp_path, capfd):
     # Prepare a simple backtest CSV with two trades
     csv_file = tmp_path / 'trades.csv'
     df = pd.DataFrame({
         'entry_date': ['2025-01-01', '2025-01-02'],
         'expiration': ['2025-01-02', '2025-01-03'],
         'pl': [100.0, -50.0]
     })
     df.to_csv(csv_file, index=False)

     # Define output directory for PNG
     out_dir = tmp_path / 'equity_out'
     # Call the CLI
     cmd = [
         sys.executable,
         os.path.abspath('simulate_equity.py'),
         '--csv', str(csv_file),
         '--start', '2025-01-01',
         '--end', '2025-01-04',
         '--initial-capital', '1000',
         '--output-dir', str(out_dir)
     ]
     result = subprocess.run(cmd, capture_output=True, text=True)
     assert result.returncode == 0, f"CLI failed: {result.stderr}"

     # Verify PNG file exists
     expected_png = out_dir / 'equity_curve_2025-01-01_to_2025-01-04.png'
     assert expected_png.exists(), f"Expected PNG at {expected_png}"
     # Check stdout messages
     out = result.stdout
     assert 'Start capital' in out
     assert 'Equity curve saved to' in out


def test_simulate_equity_cli_writes_png_with_env(monkeypatch, tmp_path):
     # Same CSV, but use environment variable
     csv_file = tmp_path / 'trades2.csv'
     df = pd.DataFrame({
         'entry_date': ['2025-02-01'],
         'expiration': ['2025-02-02'],
         'pl': [500.0]
     })
     df.to_csv(csv_file, index=False)

     # Set EQUITY_OUTPUT_DIR
     env_dir = tmp_path / 'env_eq'
     monkeypatch.setenv('EQUITY_OUTPUT_DIR', str(env_dir))

     cmd = [
         sys.executable,
         os.path.abspath('simulate_equity.py'),
         '--csv', str(csv_file),
         '--start', '2025-02-01',
         '--end', '2025-02-03',
         '--initial-capital', '2000'
     ]
     result = subprocess.run(cmd, capture_output=True, text=True)
     assert result.returncode == 0, f"CLI failed: {result.stderr}"

     # Verify PNG in env-based directory
     expected_png = env_dir / 'equity_curve_2025-02-01_to_2025-02-03.png'
     assert expected_png.exists(), f"Expected PNG at {expected_png}"
     # Ensure that default dir fallback is not used
     cwd_png = Path.cwd() / expected_png.name
     assert not cwd_png.exists()
