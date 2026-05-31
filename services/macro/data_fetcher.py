import logging
import redis.asyncio as aioredis

logger = logging.getLogger("MacroDataFetcher")


class MacroDataFetcher:
    """
    Unified reader class to compile macro data (DXY, US10Y, VIX, USDT dominance,
    MVRV proxy) from Redis cache.
    """

    def __init__(self, redis_client: aioredis.Redis):
        self.redis = redis_client

    async def get_macro_context(self) -> dict:
        """Reads intermarket indicators from Redis and returns as float dict."""
        try:
            dxy = float(await self.redis.get("macro:dxy") or 104.0)
            dxy_prev = float(await self.redis.get("macro:dxy_prev") or dxy)
            
            us10y = float(await self.redis.get("macro:us10y") or 4.5)
            us10y_prev = float(await self.redis.get("macro:us10y_prev") or us10y)
            
            vix = float(await self.redis.get("macro:vix") or 18.0)
            vix_prev = float(await self.redis.get("macro:vix_prev") or vix)
            
            usdt_d = float(await self.redis.get("macro:usdt_dominance") or 6.5)
            usdt_d_prev = float(await self.redis.get("macro:usdt_dominance_prev") or usdt_d)
            
            mvrv = float(await self.redis.get("macro:btc_mvrv_proxy") or 1.5)

            return {
                "dxy": dxy,
                "dxy_prev": dxy_prev,
                "us10y": us10y,
                "us10y_prev": us10y_prev,
                "vix": vix,
                "vix_prev": vix_prev,
                "usdt_dominance": usdt_d,
                "usdt_dominance_prev": usdt_d_prev,
                "btc_mvrv_proxy": mvrv
            }
        except Exception as e:
            logger.error("Failed to compile macro context: %s", str(e))
            return {
                "dxy": 104.0, "dxy_prev": 104.0,
                "us10y": 4.5, "us10y_prev": 4.5,
                "vix": 18.0, "vix_prev": 18.0,
                "usdt_dominance": 6.5, "usdt_dominance_prev": 6.5,
                "btc_mvrv_proxy": 1.5
            }
