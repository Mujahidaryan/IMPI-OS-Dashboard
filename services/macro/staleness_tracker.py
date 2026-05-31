import time
import logging
import redis.asyncio as aioredis

from services.ingestor.models import Tick

logger = logging.getLogger("StalenessTracker")


class StalenessTracker:
    """
    Monitors data pipeline latencies and registers freshness statuses (green/yellow/red)
    across ticks, candle feeds, and intermarket updates.
    """

    def __init__(self, redis_client: aioredis.Redis):
        self.redis = redis_client

    async def check_health(self) -> dict:
        """
        Scans timestamps of all ingested feeds.
        Returns a dict of feed names mapped to status ("green", "yellow", "red") and delay.
        """
        now_ms = int(time.time() * 1000)
        status = {}

        # 1. Tick feeds checks
        tick_symbols = ["XAUUSD_EXNESS", "XAUUSDT", "BTCUSDT"]
        for sym in tick_symbols:
            key = f"latest_tick:{sym}"
            tick_bytes = await self.redis.get(key)
            if tick_bytes:
                tick = Tick.from_bytes(tick_bytes)
                delay_sec = (now_ms - tick.timestamp_ms) / 1000.0
                
                if delay_sec < 5.0:
                    state = "green"
                elif delay_sec < 15.0:
                    state = "yellow"
                else:
                    state = "red"
                
                status[f"tick:{sym}"] = {"status": state, "latency_sec": float(delay_sec)}
            else:
                status[f"tick:{sym}"] = {"status": "red", "latency_sec": 9999.0}

        # 2. Macro feeds checks (DXY and US10Y)
        macro_keys = ["macro:dxy", "macro:us10y", "macro:vix"]
        for key in macro_keys:
            val = await self.redis.get(key)
            ts_raw = await self.redis.get(f"{key}:ts")
            
            if val and ts_raw:
                ts = float(ts_raw)
                delay_sec = time.time() - ts
                
                if delay_sec < 3600.0:  # 1 hour
                    state = "green"
                elif delay_sec < 7200.0:  # 2 hours
                    state = "yellow"
                else:
                    state = "red"
                
                status[key] = {"status": state, "latency_sec": float(delay_sec)}
            else:
                status[key] = {"status": "red", "latency_sec": 99999.0}

        return status
