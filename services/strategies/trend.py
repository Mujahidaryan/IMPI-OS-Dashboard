from services.strategies.base import BaseStrategy, StrategySignal
from services.features.feature_engine import FeatureVector


class TrendStrategy(BaseStrategy):
    """
    EMA Crossovers (9, 21, 50) + ADX trend strength + Supertrend confirmation.
    """

    def __init__(self):
        super().__init__("trend")

    async def generate_signal(self, symbol: str, features: FeatureVector) -> StrategySignal:
        adx = features.adx
        ema9 = features.ema9
        ema21 = features.ema21
        ema50 = features.ema50
        st_bull = features.supertrend_bullish

        # Trend Strength Calculation
        if adx > 25.0 and ema9 > ema21 > ema50:
            trend_strength = min((adx - 25.0) / 75.0, 1.0)
        elif adx > 25.0 and ema9 < ema21 < ema50:
            trend_strength = -min((adx - 25.0) / 75.0, 1.0)
        else:
            trend_strength = 0.0

        supertrend_mult = 1.25 if st_bull else 0.75
        
        bull_logit = max(trend_strength, 0.0) * supertrend_mult
        bear_logit = max(-trend_strength, 0.0) * (2.0 - supertrend_mult)

        return StrategySignal(
            name=self.name,
            bull_logit=float(bull_logit),
            bear_logit=float(bear_logit),
            reversal_logit=0.1,
            breakout_logit=0.1,
            base_reliability=0.58
        )
