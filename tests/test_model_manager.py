import os
from datetime import date
import joblib
import pytest

from model_manager import ModelManager


class DummyModel:
    def predict_proba(self, X):
        # Always return probability of positive class = 0.8
        return [[0.2, 0.8]]



class LowProbModel:
    def predict_proba(self, X):
        # Always return low probability for positive class
        return [[0.8, 0.3]]

def test_adjust_orders_scaling(monkeypatch, tmp_path):
    # Create a dummy model file
    model_file = tmp_path / "dummy_model.joblib"
    joblib.dump(DummyModel(), str(model_file))
    # Point ModelManager to dummy model
    monkeypatch.setenv("ML_MODEL_PATH", str(model_file))
    # Use default threshold 0.5
    mm = ModelManager()
    assert mm.model is not None
    # Prepare a sample order and data
    orders = [{"qty": 3}]
    data = {
        "iv": 0.1,
        "trend": "bullish",
        "momentum": "positive",
        "price": 100.0,
        "expiration": date.today(),
        "ticker": "TEST"
    }
    adjusted = mm.adjust_orders(orders.copy(), data)
    # Probability is 0.8, so scaled_qty = int(3 * 0.8) = int(2.4) = 2
    assert len(adjusted) == 1
    assert adjusted[0]["qty"] == 2


def test_filter_orders_below_threshold(monkeypatch, tmp_path):

    model_file = tmp_path / "low_model.joblib"
    joblib.dump(LowProbModel(), str(model_file))
    monkeypatch.setenv("ML_MODEL_PATH", str(model_file))
    monkeypatch.setenv("ML_CONFIDENCE_THRESHOLD", "0.5")
    mm = ModelManager()
    orders = [{"qty": 5}]
    data = {"iv": 0.2, "trend": "neutral", "momentum": "neutral", "price": 50.0, "expiration": date.today(), "ticker": "TEST2"}
    adjusted = mm.adjust_orders(orders.copy(), data)
    # Probability 0.3 < 0.5 threshold => orders filtered out
    assert adjusted == []


if __name__ == "__main__":
    pytest.main()