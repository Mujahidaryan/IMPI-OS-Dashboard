import numpy as np
from typing import Optional

from services.strategies.base import BaseStrategy, StrategySignal
from services.features.feature_engine import FeatureVector
from services.features.candle_aggregator import CandleAggregator
from services.features.technical import calculate_macd


class MomentumStrategy(BaseStrategy):
    """
    MACD histogram strength + ROC(10) + Williams %R.
    """

    def __init__(self, aggregator: CandleAggregator):
        super().__init__("momentum")
        self.aggregator = aggregator

    async def generate_signal(self, symbol: str, features: FeatureVector) -> StrategySignal:
        # Fetch recent candles to calculate standard deviation and crossovers
        candles = await self.aggregator.get_candles(symbol, features.timeframe, count=50)
        if len(candles) < 30:
            return StrategySignal(
                name=self.name, bull_logit=0.0, bear_logit=0.0,
                reversal_logit=0.0, breakout_logit=0.0, base_reliability=0.55
            )

        closes = np.array([c.close for c in candles], dtype=float)
        _, _, histogram = calculate_macd(closes, 12, 26, 9)

        hist_std = np.std(histogram[-20:]) if len(histogram) >= 20 else 1.0
        hist_strength = np.tanh(histogram[-1] / (hist_std + 1e-9))

        # Check histogram cross
        hist_cross_bull = (histogram[-1] > 0.0 >= histogram[-2]) if len(histogram) >= 2 else False
        hist_cross_bear = (histogram[-1] < 0.0 <= histogram[-2]) if len(histogram) >= 2 else False

        # ROC(10) and Williams %R
        roc = features.roc_10
        roc_norm = np.tanh(roc / 0.5)  # 0.5% move saturation at ~0.76

        wr = features.williams_r
        wr_bull = max((-80.0 - wr) / 20.0, 0.0) if wr < -80.0 else 0.0
        wr_bear = max((wr + 20.0) / 20.0, 0.0) if wr > -20.0 else 0.0

        cross_boost = 0.4 if hist_cross_bull else (-0.4 if hist_cross_bear else 0.0)

        bull_logit = max(hist_strength + roc_norm, 0.0) * 0.5 + wr_bull * 0.3 + max(cross_boost, 0.0)
        bear_logit = max(-hist_strength - roc_norm, 0.0) * 0.5 + wr_bear * 0.3 + max(-cross_boost, 0.0)

        return StrategySignal(
            name=self.name,
            bull_logit=float(bull_logit),
            bear_logit=float(bear_logit),
            reversal_logit=0.1,
            breakout_logit=0.1,
            base_reliability=0.55
        )
