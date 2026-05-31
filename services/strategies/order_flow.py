from collections import defaultdict
import numpy as np
import redis.asyncio as aioredis

from services.strategies.base import BaseStrategy, StrategySignal
from services.features.feature_engine import FeatureVector
from services.features.candle_aggregator import CandleAggregator


class OrderFlowStrategy(BaseStrategy):
    """
    Cumulative Volume Delta (CVD) slope + Tick Imbalance + Volume Profile POC + Book Imbalance.
    """

    def __init__(self, aggregator: CandleAggregator, redis_client: aioredis.Redis):
        super().__init__("order_flow")
        self.aggregator = aggregator
        self.redis = redis_client

    async def generate_signal(self, symbol: str, features: FeatureVector) -> StrategySignal:
        # 1. Fetch raw trade deltas from Redis
        cvd_raw = await self.redis.lrange(f"cvd_ticks:{symbol}", 0, 999)
        if not cvd_raw:
            # If no WS ticks yet, attempt to fall back to candle volume delta or return neutral
            return StrategySignal(
                name=self.name, bull_logit=0.0, bear_logit=0.0,
                reversal_logit=0.0, breakout_logit=0.0, base_reliability=0.56
            )

        deltas = [float(d) for d in cvd_raw]
        cvd = np.cumsum(deltas)
        cvd_slope = (cvd[-1] - cvd[-min(50, len(cvd))]) / 50.0
        cvd_norm = np.tanh(cvd_slope / (np.std(deltas) + 1e-9))

        # 2. Tick Imbalance
        signs = np.sign(deltas[-100:])
        upticks = np.sum(signs > 0)
        downticks = np.sum(signs < 0)
        imbalance = (upticks - downticks) / (upticks + downticks + 1e-9)

        # 3. Volume Profile (last 50 candles)
        candles = await self.aggregator.get_candles(symbol, features.timeframe, count=55)
        at_poc = False
        if len(candles) >= 50:
            recent_candles = candles[-50:]
            highs = [c.high for c in recent_candles]
            lows = [c.low for c in recent_candles]
            
            price_min = min(lows)
            price_max = max(highs)
            price_range = price_max - price_min
            
            if price_range > 0:
                n_bins = 20
                bin_size = price_range / n_bins
                vol_at_price = defaultdict(float)
                for c in recent_candles:
                    bin_idx = int((c.close - price_min) / bin_size)
                    bin_idx = min(max(bin_idx, 0), n_bins - 1)
                    vol_at_price[bin_idx] += c.volume
                    
                poc_bin = max(vol_at_price, key=vol_at_price.get)
                poc_price = price_min + poc_bin * bin_size + bin_size / 2.0
                at_poc = abs(features.close - poc_price) / poc_price < 0.001

        # 4. Order Book Imbalance (from Redis)
        ob_imbalance = float(await self.redis.get(f"ob_imbalance:{symbol}") or 0.0)

        # Signal computation
        flow_score = cvd_norm * 0.5 + imbalance * 0.3 + ob_imbalance * 0.2
        poc_penalty = 0.5 if at_poc else 1.0  # Reduce conviction in high-congestion zones
        
        bull_logit = max(flow_score, 0.0) * poc_penalty
        bear_logit = max(-flow_score, 0.0) * poc_penalty

        return StrategySignal(
            name=self.name,
            bull_logit=float(bull_logit),
            bear_logit=float(bear_logit),
            reversal_logit=0.1,
            breakout_logit=0.1,
            base_reliability=0.56
        )
