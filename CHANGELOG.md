# Changelog

## [Unreleased]

## [0.1.0] - 2025-05-07

### Added
- ATR-based dynamic stop-loss and take-profit multipliers in RiskManager
- Trailing stop percentage flag in RiskManager
- Volatility-based position sizing floor in RiskManager
- Unit tests for volatility sizing floor, ATR-based stops, and trailing stop flag in `tests/test_risk_manager.py`
- ModelManager methods: `extract_features`, `predict_proba`, `predict`, and `train_model` for offline model training and inference
- Unit tests for ModelManager in `tests/test_model_manager.py`
