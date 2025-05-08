import os
import logging
from typing import List, Dict
from joblib import load
from datetime import date

class ModelManager:
    """
    AI/ML module for trade prediction and dynamic strategy adjustments.
    """
    def __init__(self, model_path: str = None):
        # Determine model path from env or argument
        model_path = model_path or os.getenv("ML_MODEL_PATH", "model.joblib")
        try:
            self.model = load(model_path)
            logging.info(f"Loaded ML model from {model_path}")
        except Exception as e:
            logging.error(f"Failed to load model at {model_path}: {e}")
            self.model = None
        # Confidence threshold for filtering (probability of positive outcome)
        try:
            self.threshold = float(os.getenv("ML_CONFIDENCE_THRESHOLD", "0.5"))
        except ValueError:
            self.threshold = 0.5
            logging.warning("Invalid ML_CONFIDENCE_THRESHOLD, defaulting to 0.5")

    def adjust_orders(self, orders: List[Dict], data: Dict) -> List[Dict]:
        """
        Adjust or filter orders based on model predictions.
        Blocks orders if confidence < threshold, else scales qty by confidence.
        """
        if not self.model:
            return orders
        # Feature engineering
        iv = data.get("iv", 0.0)
        trend_map = {"bullish": 1, "neutral": 0, "bearish": -1}
        momentum_map = {"positive": 1, "neutral": 0, "negative": -1}
        trend_score = trend_map.get(data.get("trend"), 0)
        momentum_score = momentum_map.get(data.get("momentum"), 0)
        price = data.get("price", 0.0)
        expiration = data.get("expiration")
        # Days to expiration
        try:
            days_to_exp = (expiration - date.today()).days if isinstance(expiration, date) else 0
        except Exception:
            days_to_exp = 0
        features = [iv, trend_score, momentum_score, price, days_to_exp]
        # Model inference
        try:
            proba = self.model.predict_proba([features])[0][1]
        except Exception as e:
            logging.error(f"ML model inference failed: {e}")
            return orders
        # Filter based on threshold
        if proba < self.threshold:
            logging.info(f"ML filtered out {data.get('ticker')} (p={proba:.2f} < {self.threshold})")
            return []
        # Scale quantities by confidence
        for o in orders:
            original_qty = o.get("qty", 1)
            scaled_qty = max(1, int(original_qty * proba))
            o["qty"] = scaled_qty
        return orders


    def extract_features(self, data: Dict) -> List[float]:
        """
        Extract feature vector from market data for model inference.
        """
        iv = data.get("iv", 0.0)
        trend_map = {"bullish": 1, "neutral": 0, "bearish": -1}
        momentum_map = {"positive": 1, "neutral": 0, "negative": -1}
        trend_score = trend_map.get(data.get("trend"), 0)
        momentum_score = momentum_map.get(data.get("momentum"), 0)
        price = data.get("price", 0.0)
        expiration = data.get("expiration")
        try:
            days_to_exp = (expiration - date.today()).days if isinstance(expiration, date) else 0
        except Exception:
            days_to_exp = 0
        return [iv, trend_score, momentum_score, price, days_to_exp]

    def predict_proba(self, data: Dict) -> float:
        """
        Predict probability of positive outcome for given market data.
        """
        if not self.model:
            raise RuntimeError("Model not loaded")
        features = self.extract_features(data)
        try:
            proba = self.model.predict_proba([features])[0][1]
        except Exception as e:
            logging.error(f"Error in predict_proba: {e}")
            raise
        return proba

    def predict(self, data: Dict) -> int:
        """
        Predict binary decision (1=positive) based on confidence threshold.
        """
        p = self.predict_proba(data)
        return int(p >= self.threshold)

    def train_model(self, input_csv: str, output_path: str = None, n_estimators: int = 100, max_depth: int = None) -> None:
        """
        Train a RandomForestClassifier on historical backtest results and persist model.
        """
        import pandas as pd
        from sklearn.ensemble import RandomForestClassifier
        from joblib import dump

        df = pd.read_csv(input_csv)
        if df.empty:
            raise ValueError(f"No data found in {input_csv}")
        # Map textual trends and momentum to numeric scores
        trend_map = {"bullish": 1, "neutral": 0, "bearish": -1}
        momentum_map = {"positive": 1, "neutral": 0, "negative": -1}
        df['trend_score'] = df['trend'].map(trend_map).fillna(0)
        df['momentum_score'] = df['momentum'].map(momentum_map).fillna(0)
        # Define features and target
        feature_cols = ['iv', 'trend_score', 'momentum_score', 'price', 'days_to_exp']
        X = df[feature_cols]
        y = (df['pl'] > 0).astype(int)
        # Train model
        clf = RandomForestClassifier(n_estimators=n_estimators, max_depth=max_depth, random_state=42)
        clf.fit(X, y)
        # Persist model
        out = output_path or os.getenv("ML_MODEL_PATH", "model.joblib")
        dump(clf, out)
        self.model = clf
        logging.info(f"Trained and saved model to {out}")

