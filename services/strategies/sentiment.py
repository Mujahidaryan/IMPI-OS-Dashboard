import asyncio
import logging
import numpy as np
import httpx
import redis.asyncio as aioredis

from services.strategies.base import BaseStrategy, StrategySignal
from services.features.feature_engine import FeatureVector

logger = logging.getLogger("SentimentStrategy")


class SentimentStrategy(BaseStrategy):
    """
    Funding Rate + Open Interest shifts + Global Long/Short contrarian ratio.
    """

    def __init__(self, redis_client: aioredis.Redis):
        super().__init__("sentiment")
        self.redis = redis_client
        self._running = False
        self._poll_task: asyncio.Task | None = None

    async def start(self):
        self._running = True
        self._poll_task = asyncio.create_task(self._poll_loop())
        logger.info("Sentiment Strategy background polling started.")

    async def stop(self):
        self._running = False
        if self._poll_task:
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass
        logger.info("Sentiment Strategy background polling stopped.")

    async def _poll_loop(self):
        """Poll Binance REST API for Open Interest and Long/Short Ratio every 60s."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            while self._running:
                # Poll for XAUUSDT and BTCUSDT
                for symbol in ["BTCUSDT", "XAUUSDT"]:
                    try:
                        # 1. Poll Open Interest
                        oi_url = "https://fapi.binance.com/fapi/v1/openInterest"
                        oi_resp = await client.get(oi_url, params={"symbol": symbol})
                        if oi_resp.status_code == 200:
                            oi_now = float(oi_resp.json()["openInterest"])
                            
                            # Retrieve previous and update
                            oi_prev_raw = await self.redis.get(f"oi_current:{symbol}")
                            if oi_prev_raw:
                                await self.redis.set(f"oi_prev:{symbol}", oi_prev_raw, ex=300)
                            else:
                                await self.redis.set(f"oi_prev:{symbol}", str(oi_now), ex=300)
                                
                            await self.redis.set(f"oi_current:{symbol}", str(oi_now), ex=300)
                        
                        # 2. Poll Long/Short Ratio
                        ls_url = "https://fapi.binance.com/futures/data/globalLongShortAccountRatio"
                        ls_resp = await client.get(ls_url, params={"symbol": symbol, "period": "5m", "limit": 1})
                        if ls_resp.status_code == 200:
                            ls_data = ls_resp.json()
                            if ls_data:
                                ls_ratio = float(ls_data[0]["longShortRatio"])
                                await self.redis.set(f"ls_ratio:{symbol}", str(ls_ratio), ex=300)

                    except Exception as e:
                        logger.error("Error polling sentiment REST data for %s: %s", symbol, str(e))
                
                await asyncio.sleep(60)

    async def generate_signal(self, symbol: str, features: FeatureVector) -> StrategySignal:
        # Determine sentiment symbol: Exness Gold uses Binance Gold data
        sentiment_symbol = "XAUUSDT" if symbol.startswith("XAU") else symbol

        # 1. Funding Rate (from Redis)
        funding_raw = float(await self.redis.get(f"funding:{sentiment_symbol}") or 0.0001)
        funding_norm = np.tanh(funding_raw * 10000.0)

        # 2. Open Interest
        oi_now_raw = await self.redis.get(f"oi_current:{sentiment_symbol}")
        oi_prev_raw = await self.redis.get(f"oi_prev:{sentiment_symbol}")
        
        oi_change_pct = 0.0
        if oi_now_raw and oi_prev_raw:
            oi_now = float(oi_now_raw)
            oi_prev = float(oi_prev_raw)
            oi_change_pct = ((oi_now - oi_prev) / (oi_prev + 1e-9)) * 100.0

        # 3. Long/Short ratio
        ls_ratio_raw = await self.redis.get(f"ls_ratio:{sentiment_symbol}")
        ls_ratio = float(ls_ratio_raw) if ls_ratio_raw else 1.0
        
        ls_contrarian = 1.0 / (1.0 + np.exp(-(ls_ratio - 1.5) * 2.0))
        ls_bull = 1.0 - ls_contrarian
        ls_bear = ls_contrarian

        # Price trend alignment
        price_trend = "up" if features.close > features.ema21 else "down"
        oi_confirms = (price_trend == "up" and oi_change_pct > 0.3) or \
                      (price_trend == "down" and oi_change_pct > 0.3)

        # Signal logit logic
        funding_contrarian = -funding_norm * 0.4
        oi_signal = 0.5 if oi_confirms else -0.2

        bull_logit = max(funding_contrarian + oi_signal + ls_bull * 0.4, 0.0)
        bear_logit = max(-funding_contrarian - oi_signal + ls_bear * 0.4, 0.0)

        # Gold Dual-feed arbitrage adjustment
        if symbol.startswith("XAU"):
            gold_arbitrage_score = float(await self.redis.get("gold:arbitrage:divergence") or 0.0)
            arb_penalty = max(1.0 - gold_arbitrage_score * 20.0, 0.5)
            bull_logit *= arb_penalty
            bear_logit *= arb_penalty

        return StrategySignal(
            name=self.name,
            bull_logit=float(bull_logit),
            bear_logit=float(bear_logit),
            reversal_logit=0.1,
            breakout_logit=0.1,
            base_reliability=0.57
        )
