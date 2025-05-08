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


def test_extract_features_defaults():
    mm = ModelManager(model_path="nonexistent-model.joblib")
    data = {}
    feats = mm.extract_features(data)
    # Default values: iv=0.0, trend_score=0, momentum_score=0, price=0.0, days_to_exp=0
    assert feats == [0.0, 0, 0, 0.0, 0]


def test_extract_features_values():
    mm = ModelManager(model_path="nonexistent-model.joblib")
    from datetime import timedelta
    exp = date.today() + timedelta(days=5)
    data = {'iv': 0.15, 'trend': 'bearish', 'momentum': 'positive', 'price': 250.0, 'expiration': exp}
    feats = mm.extract_features(data)
    # trend_score = -1, momentum_score = 1, days_to_exp = 5
    assert feats == [0.15, -1, 1, 250.0, 5]


def test_predict_proba_and_predict():
    class DummyModel2:
        def predict_proba(self, X):
            return [[0.3, 0.7] for _ in X]
    mm = ModelManager(model_path="nonexistent-model.joblib")
    mm.model = DummyModel2()
    data = {'iv': 0.0, 'trend': 'neutral', 'momentum': 'neutral', 'price': 0.0, 'expiration': date.today()}
    p = mm.predict_proba(data)
    assert p == pytest.approx(0.7)
    # Default threshold 0.5 => predict 1
    assert mm.predict(data) == 1
    mm.threshold = 0.9
    assert mm.predict(data) == 0


def test_train_model_creates_and_saves(tmp_path):
    import pandas as pd
    from datetime import timedelta
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
    mm = ModelManager(model_path="nonexistent-model.joblib")
    mm.train_model(str(input_csv), output_path=str(output_model), n_estimators=5, max_depth=2)
    # Model file created
    assert output_model.exists()
    from sklearn.ensemble import RandomForestClassifier
    assert isinstance(mm.model, RandomForestClassifier)
    data = {'iv': 0.2, 'trend': 'bullish', 'momentum': 'positive', 'price': 115.0, 'expiration': date.today()}
    p = mm.predict_proba(data)
    assert 0.0 <= p <= 1.0


def test_train_model_empty_raises(tmp_path):
    input_csv = tmp_path / "empty.csv"
    input_csv.write_text('iv,trend,momentum,price,days_to_exp,pl\n')
    mm = ModelManager(model_path="nonexistent-model.joblib")
    with pytest.raises(ValueError):
        mm.train_model(str(input_csv))



if __name__ == "__main__":
    pytest.main()