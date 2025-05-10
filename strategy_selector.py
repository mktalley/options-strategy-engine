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
    def __init__(self, iv_threshold: float = 0.25, phase: int = 1, allowed_strategies: list = None):
        """Initialize selector with an IV threshold, phase, and optional whitelist of strategy names."""
        self.iv_threshold = iv_threshold
        self.phase = phase
        self.allowed_strategies = allowed_strategies or []
        """Initialize selector with an IV threshold and maximum phase to include."""
        self.iv_threshold = iv_threshold
        self.phase = phase

    def select(self, trend: str, iv: float, momentum: str):
        """
        Given market metrics, select and return the best Strategy instance or None.
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

        best_score = max(scores.values())
        # Skip low-confidence signals (score < 2) in advanced phases only
        if self.phase > 1 and best_score < 2:
            logging.info(f"No strong signal (score {best_score:.2f}), skipping trade")
            return None

        # Identify top-scoring strategies
        best_classes = [cls for cls, s in scores.items() if s == best_score]

        # Tie-breaker if multiple
        if len(best_classes) > 1:
            if self.phase > 1:
                # Special tie-breaker for neutral trend & high IV: prefer Collar
                if trend == 'neutral' and iv >= self.iv_threshold and strategies.Collar in best_classes:
                    best_cls = strategies.Collar
                else:
                    # Break ties by highest number of legs
                    runs = {}
                    for c in best_classes:
                        try:
                            orders = c().run(data)
                        except Exception as e:
                            logging.warning(f"Error running strategy {c.__name__} for tie-breaker: {e}")
                            orders = []
                        runs[c] = orders
                    max_legs = max(len(o) for o in runs.values())
                    leg_winners = [c for c, o in runs.items() if len(o) == max_legs]
                    if len(leg_winners) == 1:
                        best_cls = leg_winners[0]
                    else:
                        best_cls = sorted(leg_winners, key=lambda c: c.__name__)[0]
            else:
                # Phase 1: default first-scored strategy
                best_cls = best_classes[0]
            logging.info(f"Tie between {[c.__name__ for c in best_classes]}, selecting {best_cls.__name__}")
        else:
            best_cls = best_classes[0]

        # Skip bearish put strategies to reduce losses (advanced phases only)
        if self.phase > 1 and best_cls == strategies.LongPut:
            logging.info("Skipping LongPut strategy to avoid bearish trades")
            return None

        logging.info(f"Chosen strategy: {best_cls.__name__} with score {best_score:.2f}")
        return best_cls()
