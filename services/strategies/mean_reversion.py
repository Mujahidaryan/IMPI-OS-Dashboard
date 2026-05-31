from services.strategies.base import BaseStrategy, StrategySignal
from services.features.feature_engine import FeatureVector


class MeanReversionStrategy(BaseStrategy):
    """
    Bollinger Bands %b + Z-score deviation + RSI divergence.
    """

    def __init__(self):
        super().__init__("mean_reversion")

    async def generate_signal(self, symbol: str, features: FeatureVector) -> StrategySignal:
        z = features.z_score
        bb_pct = features.bb_pct
        bull_div = features.rsi_bull_divergence
        bear_div = features.rsi_bear_divergence

        # Z-score signals
        if z < -2.0:
            rev_bull = min(abs(z) / 3.0, 1.0)
            rev_bear = 0.0
        elif z > 2.0:
            rev_bear = min(abs(z) / 3.0, 1.0)
            rev_bull = 0.0
        else:
            rev_bull = rev_bear = 0.0

        # Bollinger Band signals
        bb_bull = max(1.0 - 2.0 * bb_pct, 0.0)
        bb_bear = max(2.0 * bb_pct - 1.0, 0.0)

        div_boost = 0.35
        bull_logit = (rev_bull + bb_bull) * 0.5 + (div_boost if bull_div else 0.0)
        bear_logit = (rev_bear + bb_bear) * 0.5 + (div_boost if bear_div else 0.0)
        
        reversal_logit = max(bull_logit, bear_logit)

        return StrategySignal(
            name=self.name,
            bull_logit=float(bull_logit),
            bear_logit=float(bear_logit),
            reversal_logit=float(reversal_logit),
            breakout_logit=0.1,
            base_reliability=0.54
        )
