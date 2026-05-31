from abc import ABC, abstractmethod
from dataclasses import dataclass

from services.features.feature_engine import FeatureVector


@dataclass(slots=True)
class StrategySignal:
    name: str
    bull_logit: float
    bear_logit: float
    reversal_logit: float
    breakout_logit: float
    base_reliability: float


class BaseStrategy(ABC):
    """
    Abstract base class for all quantitative decision models.
    """

    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    async def generate_signal(self, symbol: str, features: FeatureVector) -> StrategySignal:
        """
        Calculates output logits based on the compiled feature vector.
        """
        pass
