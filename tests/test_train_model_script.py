import subprocess
import sys
import pandas as pd
import pytest
from pathlib import Path

def test_train_model_script_success(tmp_path):
    # Create sample backtest_results.csv
    df = pd.DataFrame({
        'iv': [0.1, 0.2, 0.3, 0.4],
        'trend': ['bullish', 'neutral', 'bearish', 'bullish'],
        'momentum': ['positive', 'negative', 'neutral', 'positive'],
        'price': [100, 110, 120, 130],
        'days_to_exp': [1, 2, 3, 4],
        'pl': [10, -5, 0, 8]
    })
    input_csv = tmp_path / "sample.csv"
    df.to_csv(input_csv, index=False)
    output_model = tmp_path / "model_out.joblib"
    # Run the training script
    result = subprocess.run(
        [sys.executable, str(Path(__file__).parent.parent / "scripts" / "train_model.py"),
         "--input", str(input_csv),
         "--output", str(output_model),
         "--n-estimators", "10",  # smaller for test speed
         "--max-depth", "3"],
        capture_output=True,
        text=True
    )
    # Script should complete successfully
    assert result.returncode == 0, f"stdout: {result.stdout}, stderr: {result.stderr}"
    # Model file should be created
    assert output_model.exists()
    # Output message should mention model saved
    assert "saved to" in result.stdout or "Model trained" in result.stdout


def test_train_model_script_empty(tmp_path):
    # Create empty CSV with headers
    input_csv = tmp_path / "empty.csv"
    input_csv.write_text('iv,trend,momentum,price,days_to_exp,pl\n')
    output_model = tmp_path / "model_empty.joblib"
    # Run the training script
    result = subprocess.run(
        [sys.executable, str(Path(__file__).parent.parent / "scripts" / "train_model.py"),
         "--input", str(input_csv),
         "--output", str(output_model)],
        capture_output=True,
        text=True
    )
    # Script should complete without error
    assert result.returncode == 0
    # Should print no data found
    assert "No data found" in result.stdout
    # No model file created
    assert not output_model.exists()
