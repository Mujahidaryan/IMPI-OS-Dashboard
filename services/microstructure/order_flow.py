import numpy as np
import redis.asyncio as aioredis
from typing import Dict, Tuple


class MicrostructureOrderFlow:
    """
    Analyzes tick-by-tick trades to detect aggressive buying/selling clusters
    and identify institutional block flow imbalances.
    """

    def __init__(self, redis_client: aioredis.Redis):
        self.redis = redis_client

    async def analyze_trade_clusters(self, symbol: str) -> dict:
        """
        Scans recent raw trades from Redis queue and classifies
        them into block sizes to detect institutional skew.
        """
        # Pull latest 500 tick deltas (volume with direction sign)
        cvd_raw = await self.redis.lrange(f"cvd_ticks:{symbol}", 0, 499)
        if not cvd_raw:
            return {
                "aggressive_buyer_ratio": 0.5,
                "block_buyer_ratio": 0.5,
                "large_block_count": 0,
                "skew_index": 0.0
            }

        deltas = np.array([float(d) for d in cvd_raw])
        abs_volumes = np.abs(deltas)
        
        # Define large trade thresholds based on 90th percentile of volumes
        if len(abs_volumes) < 10:
            return {
                "aggressive_buyer_ratio": 0.5,
                "block_buyer_ratio": 0.5,
                "large_block_count": 0,
                "skew_index": 0.0
            }

        block_threshold = np.percentile(abs_volumes, 90)

        # Separate block sizes (top 10% of trades)
        block_mask = abs_volumes >= block_threshold
        block_deltas = deltas[block_mask]

        buy_blocks = sum(v for v in block_deltas if v > 0)
        sell_blocks = sum(abs(v) for v in block_deltas if v < 0)
        total_blocks = buy_blocks + sell_blocks

        block_buyer_ratio = buy_blocks / (total_blocks + 1e-9) if total_blocks > 0 else 0.5

        # Compute general aggressive buying ratio
        buys = sum(v for v in deltas if v > 0)
        sells = sum(abs(v) for v in deltas if v < 0)
        total_volume = buys + sells
        
        aggressive_buyer_ratio = buys / (total_volume + 1e-9) if total_volume > 0 else 0.5

        skew_index = (aggressive_buyer_ratio - 0.5) * 2.0  # -1.0 to 1.0

        return {
            "aggressive_buyer_ratio": float(aggressive_buyer_ratio),
            "block_buyer_ratio": float(block_buyer_ratio),
            "large_block_count": int(np.sum(block_mask)),
            "skew_index": float(skew_index)
        }
