import logging
import inspect
import strategies
from datetime import date
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
            # Dummy fields for tie-breaker run
            'ticker': 'DUMMY',
            'price': 100.0,
            'expiration': date.today(),
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
                        # Determine best-scoring strategy with tie-breaker
        best_score = max(scores.values())
        # Find all strategy classes with the top score
        best_classes = [cls for cls, s in scores.items() if s == best_score]
        if len(best_classes) > 1:
            # Phase-based tie-breaker
            if self.phase > 1:
                # Special tie-breaker for neutral trend & high IV: prefer Collar
                if trend == 'neutral' and iv >= self.iv_threshold and strategies.Collar in best_classes:
                    return strategies.Collar()
                # For phase 2+, break ties by number of legs (run output length)
                # Safely run each candidate (catch missing data) and compare number of orders
                runs = {}
                for cls in best_classes:
                    try:
                        orders = cls().run(data)
                    except Exception as e:
                        logging.warning(f"Error running strategy {cls.__name__} for tie-breaker: {e}")
                        orders = []
                    runs[cls] = orders
                max_legs = max(len(orders) for orders in runs.values())
                leg_winners = [cls for cls, orders in runs.items() if len(orders) == max_legs]
                if len(leg_winners) == 1:
                    best_cls = leg_winners[0]
                else:
                    # Fallback to alphabetical order of class name
                    best_cls = sorted(leg_winners, key=lambda c: c.__name__)[0]
            else:
                # Tie-break alphabetically by class name (pick lexicographically highest)
                best_cls = max(best_classes, key=lambda c: c.__name__)
            logging.info(f"Tie between {[c.__name__ for c in best_classes]}, selecting {best_cls.__name__}")
        else:
            best_cls = best_classes[0]
        logging.info(f"Chosen strategy: {best_cls.__name__} with score {best_score:.2f}")
        return best_cls()
