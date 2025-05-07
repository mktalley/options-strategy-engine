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

