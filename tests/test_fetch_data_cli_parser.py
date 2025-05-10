import os
import pytest
from scripts.fetch_data import get_cli_args

def test_fetch_data_default_outdir_from_env(monkeypatch, tmp_path):
    # Set environment variable for default output directory
    env_dir = tmp_path / "env_data"
    monkeypatch.setenv('FETCH_DATA_OUTDIR', str(env_dir))
    # Parse CLI args without explicit --outdir
    args = get_cli_args(['--tickers', 'AAPL', '--start', '2025-01-01', '--end', '2025-01-02'])
    assert args.outdir == str(env_dir)

def test_fetch_data_override_outdir(monkeypatch, tmp_path):
    # Ensure env var is not set
    monkeypatch.delenv('FETCH_DATA_OUTDIR', raising=False)
    custom_dir = tmp_path / 'custom_out'
    args = get_cli_args([
        '--tickers', 'GOOG',
        '--start', '2025-02-01',
        '--end', '2025-02-05',
        '--outdir', str(custom_dir)
    ])
    assert args.outdir == str(custom_dir)
