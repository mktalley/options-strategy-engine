import os
import sys
import subprocess
import pandas as pd
import pytest
from pathlib import Path

SCRIPT_PATH = Path(__file__).parent.parent / "scripts" / "train_model.py"

def test_train_model_cli_default_output_from_env(tmp_path, monkeypatch):
    # Create sample backtest_results.csv
    df = pd.DataFrame({
        'iv': [0.1, 0.2],
        'trend': ['bullish', 'bearish'],
        'momentum': ['positive', 'negative'],
        'price': [100, 110],
        'days_to_exp': [1, 2],
        'pl': [5, -3]
    })
    input_csv = tmp_path / "sample.csv"
    df.to_csv(input_csv, index=False)

    # Set environment variable for default output path
    default_model = tmp_path / "default_model.joblib"
    monkeypatch.setenv('ML_MODEL_PATH', str(default_model))

    # Run the training script without --output
    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH),
         "--input", str(input_csv),
         # speed up training
         "--n-estimators", "10",
         "--max-depth", "3"],
        capture_output=True,
        text=True
    )
    # Should complete successfully
    assert result.returncode == 0, f"stdout: {result.stdout}, stderr: {result.stderr}"
    # Model file should be created at env-default location
    assert default_model.exists(), f"Expected model at {default_model}"
    # Output message should mention saved path
    assert str(default_model) in result.stdout
