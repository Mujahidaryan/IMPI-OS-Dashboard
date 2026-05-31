import time
import logging
import numpy as np
import redis.asyncio as aioredis

from services.ingestor.models import Candle, AnomalyEvent
from services.features.candle_aggregator import CandleAggregator

logger = logging.getLogger("ManipulationDetector")


class ManipulationDetector:
    """
    Analyzes candlestick structures and order patterns to detect wicks,
    fake breakouts, and cross-feed gold price deviations.
    """

    def __init__(self, aggregator: CandleAggregator, redis_client: aioredis.Redis):
        self.aggregator = aggregator
        self.redis = redis_client

    async def calculate_manipulation_score(self, symbol: str, timeframe: str) -> float:
        """
        Computes a composite manipulation score (0.0 to 1.0) for the symbol.
        """
        candles = await self.aggregator.get_candles(symbol, timeframe, count=30)
        if len(candles) < 25:
            return 0.0

        closes = np.array([c.close for c in candles], dtype=float)
        highs = np.array([c.high for c in candles], dtype=float)
        lows = np.array([c.low for c in candles], dtype=float)
        opens = np.array([c.open for c in candles], dtype=float)

        # 1. Abnormal Wick Detection on the latest candle
        latest_candle = candles[-1]
        upper_wick = latest_candle.high - max(latest_candle.open, latest_candle.close)
        lower_wick = min(latest_candle.open, latest_candle.close) - latest_candle.low
        candle_range = latest_candle.high - latest_candle.low + 1e-9
        
        wick_ratio = max(upper_wick, lower_wick) / candle_range
        
        # Calculate ATR for scaling
        tr = np.zeros(len(candles))
        tr[0] = highs[0] - lows[0]
        for i in range(1, len(candles)):
            tr[i] = max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i - 1]),
                abs(lows[i] - closes[i - 1])
            )
        atr = np.mean(tr[-14:])
        
        spike_score = 0.0
        is_spike = False
        if wick_ratio > 0.85 and candle_range > 2.0 * atr:
            spike_score = min((wick_ratio - 0.85) / 0.15, 1.0) * 0.5
            is_spike = True

        # Track consecutive spike wicks
        consecutive_key = f"manipulation:consecutive_spikes:{symbol}"
        consecutive_spikes = int(await self.redis.get(consecutive_key) or 0)
        if is_spike:
            consecutive_spikes += 1
            await self.redis.set(consecutive_key, str(consecutive_spikes), ex=3600)
        else:
            await self.redis.set(consecutive_key, "0", ex=3600)

        consecutive_penalty = 0.0
        if consecutive_spikes >= 3:
            consecutive_penalty = 0.2

        # 2. Fake Breakout Detection
        # Compare last two candles against previous 20-candle high/low bounds
        recent_high_20 = max(highs[-22:-2])
        recent_low_20 = min(lows[-22:-2])
        
        breakout_up = (closes[-2] > recent_high_20) and (closes[-1] < recent_high_20)
        breakout_down = (closes[-2] < recent_low_20) and (closes[-1] > recent_low_20)
        
        fake_breakout_score = 0.45 if (breakout_up or breakout_down) else 0.0

        # 3. Gold Cross-feed Divergence Score
        divergence_score = 0.0
        if symbol.startswith("XAU"):
            arb_div = float(await self.redis.get("gold:arbitrage:divergence") or 0.0)
            divergence_score = min(arb_div * 20.0, 0.5)  # 2.5% divergence limits score to 0.5

        # 4. Composite Manipulation Score
        manipulation_probability = float(
            np.clip(
                spike_score + fake_breakout_score + divergence_score + consecutive_penalty,
                0.0, 1.0
            )
        )

        # Trigger Alerts and confidence adjustments
        if manipulation_probability > 0.70:
            anomaly = AnomalyEvent(
                symbol=symbol,
                anomaly_type="high_manipulation",
                severity=manipulation_probability,
                description=f"Critical microstructural manipulation detected! Score: {manipulation_probability:.2f}",
                raw_value=manipulation_probability,
                expected_range=(0.0, 0.70),
                timestamp_ms=int(time.time() * 1000)
            )
            await self.redis.publish("channel:anomalies", anomaly.to_bytes())
        elif manipulation_probability > 0.40:
            anomaly = AnomalyEvent(
                symbol=symbol,
                anomaly_type="moderate_manipulation",
                severity=manipulation_probability,
                description=f"Moderate microstructural anomalies. Score: {manipulation_probability:.2f}",
                raw_value=manipulation_probability,
                expected_range=(0.0, 0.40),
                timestamp_ms=int(time.time() * 1000)
            )
            await self.redis.publish("channel:anomalies", anomaly.to_bytes())

        return manipulation_probability
