import logging
import inspect
import strategies
from strategies import Strategy as _Strategy

class StrategySelector:
    """
    Dynamically selects an options trading strategy based on market metrics.
    It introspects all Strategy subclasses and picks the one with the highest score().

    To extend: add new Strategy subclasses in strategies.py with a @classmethod score(data) -> float.
    """

    def __init__(self, iv_threshold: float = 0.25):
        """Initialize selector with an IV threshold for scoring."""
        self.iv_threshold = iv_threshold

    def select(self, trend: str, iv: float, momentum: str):
        """
        Scores each registered Strategy subclass based on supplied market metrics and returns the highest-scoring one.

        Args:
            trend: 'bullish', 'bearish', or 'neutral'
            iv: current implied volatility
            momentum: 'positive' or 'negative'

        Returns:
            An instance of the selected Strategy subclass.
        """
        logging.info(f"Selecting strategy: trend={trend}, iv={iv:.2f}, momentum={momentum}")
        # Build data dict for scoring
        data = {
            'trend': trend,
            'iv': iv,
            'momentum': momentum,
            'iv_threshold': self.iv_threshold,
        }
        # Discover all Strategy subclasses
        strategy_classes = [
            obj for obj in vars(strategies).values()
            if inspect.isclass(obj) and issubclass(obj, _Strategy) and obj is not _Strategy
        ]
        # Compute scores
        scores = {}
        for cls in strategy_classes:
            try:
                score = cls.score(data)
            except Exception as e:
                logging.warning(f"Failed to score strategy {cls.__name__}: {e}")
                score = float('-inf')
            scores[cls] = score
            logging.debug(f"Score for {cls.__name__}: {score}")
        # Select best
        best_cls = max(scores, key=scores.get)
        best_score = scores[best_cls]
        logging.info(f"Chosen strategy: {best_cls.__name__} with score {best_score:.2f}")
        return best_cls()
