import logging
import inspect
import strategies
from strategies import Strategy as _Strategy

class StrategySelector:
    """
    Dynamically selects an options trading strategy based on market metrics and allowed phases.

    phase: integer phase threshold; only strategies with phase <= this are considered.
    iv_threshold: threshold for IV-based scoring.
    """
    def __init__(self, iv_threshold: float = 0.25, phase: int = 1):
        """Initialize selector with an IV threshold and maximum phase to include."""
        self.iv_threshold = iv_threshold
        self.phase = phase

    def select(self, trend: str, iv: float, momentum: str):
        """
        Given market metrics, select and return the best Strategy instance.
        """
        logging.info(f"Selecting strategy: trend={trend}, iv={iv:.2f}, momentum={momentum}")
        # Build data dict for scoring
        data = {
            'trend': trend,
            'iv': iv,
            'momentum': momentum,
            'iv_threshold': self.iv_threshold,
        }
        # Discover all Strategy subclasses up to this.phase
        strategy_classes = [
            obj for obj in vars(strategies).values()
            if inspect.isclass(obj)
            and issubclass(obj, _Strategy)
            and obj is not _Strategy
            and getattr(obj, 'phase', 1) <= self.phase
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
        # Select the best-scoring strategy
        best_cls = max(scores, key=scores.get)
        best_score = scores[best_cls]
        logging.info(f"Chosen strategy: {best_cls.__name__} with score {best_score:.2f}")
        return best_cls()
