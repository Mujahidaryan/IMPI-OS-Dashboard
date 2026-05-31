from services.strategies.base import BaseStrategy, StrategySignal
from services.features.feature_engine import FeatureVector


class VolatilityStrategy(BaseStrategy):
    """
    BB/KC squeeze release breakout strategy.
    """

    def __init__(self):
        super().__init__("volatility")

    async def generate_signal(self, symbol: str, features: FeatureVector) -> StrategySignal:
        vol_ratio = features.vol_ratio
        squeeze_release = features.is_squeeze_release
        close = features.close
        kc_mid = features.kc_mid  # kc_mid is EMA20

        if squeeze_release:
            breakout_logit = vol_ratio * 1.5
            ema_dir = close > kc_mid
            bull_logit = breakout_logit if ema_dir else 0.1
            bear_logit = breakout_logit if not ema_dir else 0.1
        else:
            breakout_logit = 0.1
            bull_logit = bear_logit = 0.2

        return StrategySignal(
            name=self.name,
            bull_logit=float(bull_logit),
            bear_logit=float(bear_logit),
            reversal_logit=0.1,
            breakout_logit=float(breakout_logit),
            base_reliability=0.52
        )
