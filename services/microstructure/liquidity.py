import logging
import redis.asyncio as aioredis
from typing import Dict, Tuple

from services.ingestor.models import Tick

logger = logging.getLogger("LiquidityMonitor")


class LiquidityMonitor:
    """
    Monitors bid/ask spread widths, book thickness at various levels,
    and identifies microstructural liquidity voids or spread blowouts.
    """

    def __init__(self, redis_client: aioredis.Redis):
        self.redis = redis_client

    async def check_liquidity_quality(self, symbol: str) -> Tuple[float, float]:
        """
        Computes spread quality and detects liquidity voids.
        Returns a tuple: (spread_ratio_zscore, book_depth_deficit).
        Both values normalized, higher values represent worse liquidity conditions.
        """
        tick_bytes = await self.redis.get(f"latest_tick:{symbol}")
        if not tick_bytes:
            return 0.0, 0.0

        tick = Tick.from_bytes(tick_bytes)
        bid, ask = tick.bid, tick.ask
        mid = tick.mid

        if mid <= 0:
            return 0.0, 0.0

        spread_pct = (ask - bid) / mid

        # Rolling tracking of spreads in Redis to compute rolling mean/std
        spread_history_key = f"liquidity:spread_history:{symbol}"
        await self.redis.lpush(spread_history_key, str(spread_pct))
        await self.redis.ltrim(spread_history_key, 0, 99)  # last 100 observations

        spreads_raw = await self.redis.lrange(spread_history_key, 0, -1)
        spreads = [float(s) for s in spreads_raw]

        mean_spread = sum(spreads) / len(spreads)
        var_spread = sum((s - mean_spread) ** 2 for s in spreads) / len(spreads)
        std_spread = var_spread ** 0.5

        # Z-score of the spread
        spread_ratio_zscore = (spread_pct - mean_spread) / (std_spread + 1e-9)
        spread_ratio_zscore = max(0.0, float(spread_ratio_zscore))

        # Check Order Book imbalance and depth gaps to quantify Liquidity Void
        ob_imbalance_raw = await self.redis.get(f"ob_imbalance:{symbol}")
        ob_imbalance = abs(float(ob_imbalance_raw)) if ob_imbalance_raw else 0.0

        # High order book imbalance combined with widened spreads indicates a void
        book_depth_deficit = min(1.0, ob_imbalance * (spread_pct / (mean_spread + 1e-9)))

        return spread_ratio_zscore, book_depth_deficit
