import math
import logging
import asyncio
import numpy as np
import redis.asyncio as aioredis
from typing import Dict, Any

from services.learning.prediction_store import PredictionStore

logger = logging.getLogger("WeightUpdater")


class StrategyWeightUpdater:
    """
    Applies online gradient-like exponential updates on strategy weights
    based on individual strategy predictive accuracy.
    """

    def __init__(self, db: PredictionStore, redis_client: aioredis.Redis):
        self.db = db
        self.redis = redis_client
        
        # In-memory strategy weights (defaults)
        self._weights: Dict[str, float] = {
            "trend": 0.58,
            "mean_reversion": 0.54,
            "momentum": 0.55,
            "volatility": 0.52,
            "order_flow": 0.56,
            "sentiment": 0.57,
            "macro_news": 0.50,
            "intermarket": 0.53,
        }
        
        # Track consecutive failures per strategy for pruning/flooring
        self._consecutive_failures: Dict[str, int] = {k: 0 for k in self._weights.keys()}

        # Decay params
        self.halflife = 20.0
        self.decay_lambda = math.log(2.0) / self.halflife  # 0.03466
        self.alpha = 1.0 - math.exp(-self.decay_lambda)      # 0.0340

    async def initialize(self):
        """Warm start weights from database on system startup."""
        try:
            stored_weights = await self.db.get_latest_strategy_weights()
            for strategy, weight in stored_weights.items():
                if strategy in self._weights:
                    self._weights[strategy] = weight
            
            # Sync weights to Redis cache
            for strategy, weight in self._weights.items():
                await self.redis.set(f"strategy_weight:{strategy}", str(weight))
            
            logger.info("Strategy weights loaded and synchronized: %s", self._weights)
        except Exception as e:
            logger.error("Failed to initialize strategy weights: %s", str(e))

    async def get_weight(self, strategy_name: str) -> float:
        return self._weights.get(strategy_name, 0.55)

    async def observe_outcome(self, prediction_id: int, actual_direction: str, strategy_signals: dict):
        """
        Updates weights for each strategy based on its alignment with actual direction.
        strategy_signals is a dict mapping: strategy_name -> direction_string ("long"/"short" etc)
        """
        for name in self._weights.keys():
            sig = strategy_signals.get(name)
            if not sig:
                continue

            pred_dir = sig.get("direction")
            if not pred_dir:
                continue

            # Check if this strategy was correct
            correct = (pred_dir == actual_direction)
            
            # Consecutive failures logic for pruning
            if correct:
                self._consecutive_failures[name] = 0
            else:
                self._consecutive_failures[name] += 1

            w_old = self._weights[name]
            w_new = (1.0 - self.alpha) * w_old + self.alpha * float(correct)
            w_new = float(np.clip(w_new, 0.30, 0.85))

            # Strategy pruning trigger
            if self._consecutive_failures[name] >= 50:
                w_new = 0.30  # Floor weight, never let it drop to 0.0
                logger.warning(
                    "Strategy %s has hit 50 consecutive failures! Weight floored to 0.30.",
                    name
                )
                # Emit anomaly alert
                alert_payload = {
                    "alert": f"Strategy {name} performance degraded (50 consecutive failures). Weight floored to 0.30."
                }
                await self.redis.publish("channel:alerts", json.dumps(alert_payload))

            self._weights[name] = w_new
            await self.redis.set(f"strategy_weight:{name}", str(w_new))

        # Save new weights asynchronously to database
        asyncio.create_task(self.db.save_strategy_weights(self._weights))
        logger.info("Strategy weights updated: %s", self._weights)
