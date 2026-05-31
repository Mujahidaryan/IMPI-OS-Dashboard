import asyncio
import logging
import time
import httpx
import redis.asyncio as aioredis

from services.strategies.base import BaseStrategy, StrategySignal
from services.features.feature_engine import FeatureVector
from config.settings import get_settings

logger = logging.getLogger("IntermarketStrategy")


class IntermarketStrategy(BaseStrategy):
    """
    Inter-market correlations tracking DXY (Dollar Index), US 10Y Yield,
    VIX (Volatility Index), USDT Dominance, and BTC MVRV Proxy.
    """

    def __init__(self, redis_client: aioredis.Redis):
        super().__init__("intermarket")
        self.redis = redis_client
        self.settings = get_settings()
        self._running = False
        self._poll_task: asyncio.Task | None = None

    async def start(self):
        self._running = True
        self._poll_task = asyncio.create_task(self._poll_loop())
        logger.info("Intermarket Strategy background polling started.")

    async def stop(self):
        self._running = False
        if self._poll_task:
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass
        logger.info("Intermarket Strategy background polling stopped.")

    async def _poll_loop(self):
        """Poll intermarket macro data every 15 minutes."""
        while self._running:
            try:
                logger.info("Polling intermarket macro data...")
                async with httpx.AsyncClient(timeout=15.0) as client:
                    await self._fetch_dxy(client)
                    await self._fetch_us10y(client)
                    await self._fetch_vix(client)
                    await self._fetch_coingecko_metrics(client)
            except Exception as e:
                logger.error("Error in intermarket poll loop: %s", str(e))
            
            await asyncio.sleep(900)  # 15 minutes

    async def _fetch_dxy(self, client: httpx.AsyncClient):
        # 1. Primary - Yahoo Finance
        try:
            url = "https://query1.finance.yahoo.com/v8/finance/chart/%5EDXY"
            resp = await client.get(url, params={"interval": "1h", "range": "2d"}, headers={"User-Agent": "Mozilla/5.0"})
            if resp.status_code == 200:
                data = resp.json()
                close_prices = data["chart"]["result"][0]["indicators"]["quote"][0]["close"]
                # Filter out None values
                close_prices = [p for p in close_prices if p is not None]
                if close_prices:
                    dxy = float(close_prices[-1])
                    await self._set_macro_with_prev("macro:dxy", dxy)
                    return
        except Exception as e:
            logger.warning("DXY Yahoo fetch failed: %s. Attempting secondary...", str(e))

        # 2. Secondary - Alpha Vantage
        if self.settings.ALPHA_VANTAGE_KEY:
            try:
                url = "https://www.alphavantage.co/query"
                resp = await client.get(url, params={
                    "function": "FX_DAILY",
                    "from_symbol": "USD",
                    "to_symbol": "EUR",
                    "apikey": self.settings.ALPHA_VANTAGE_KEY
                })
                if resp.status_code == 200:
                    time_series = resp.json().get("Time Series FX (Daily)", {})
                    if time_series:
                        latest_date = sorted(time_series.keys())[-1]
                        eur_usd = float(time_series[latest_date]["4. close"])
                        dxy_proxy = (1.0 / eur_usd) * 100.0
                        await self._set_macro_with_prev("macro:dxy", dxy_proxy)
                        return
            except Exception as e:
                logger.error("DXY Alpha Vantage fetch failed: %s", str(e))

        # 3. Fallback with decay
        try:
            last_dxy_raw = await self.redis.get("macro:dxy")
            last_ts_raw = await self.redis.get("macro:dxy:ts")
            
            last_dxy = float(last_dxy_raw) if last_dxy_raw else 104.0
            last_ts = float(last_ts_raw) if last_ts_raw else time.time()
            
            minutes_stale = (time.time() - last_ts) / 60.0
            decayed_dxy = last_dxy * (0.9999 ** minutes_stale)
            
            await self.redis.set("macro:dxy", str(decayed_dxy))
            await self.redis.set("macro:dxy:ts", str(time.time()))
            logger.warning("Using decayed DXY: %.2f (stale by %.1f minutes)", decayed_dxy, minutes_stale)
        except Exception as e:
            logger.error("DXY decay fallback failed: %s", str(e))

    async def _fetch_us10y(self, client: httpx.AsyncClient):
        try:
            url = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=GS10"
            resp = await client.get(url)
            if resp.status_code == 200:
                lines = resp.text.strip().split("\n")
                if lines:
                    last_line = lines[-1]
                    date_str, yield_str = last_line.split(",")
                    # Fred occasionally reports "." for missing days (holidays)
                    if yield_str.strip() == "." and len(lines) > 1:
                        last_line = lines[-2]
                        date_str, yield_str = last_line.split(",")
                    
                    us10y = float(yield_str)
                    await self._set_macro_with_prev("macro:us10y", us10y)
        except Exception as e:
            logger.error("US10Y Fred fetch failed: %s", str(e))

    async def _fetch_vix(self, client: httpx.AsyncClient):
        try:
            url = "https://query1.finance.yahoo.com/v8/finance/chart/%5EVIX"
            resp = await client.get(url, params={"interval": "1d", "range": "5d"}, headers={"User-Agent": "Mozilla/5.0"})
            if resp.status_code == 200:
                data = resp.json()
                close_prices = data["chart"]["result"][0]["indicators"]["quote"][0]["close"]
                close_prices = [p for p in close_prices if p is not None]
                if close_prices:
                    vix = float(close_prices[-1])
                    await self._set_macro_with_prev("macro:vix", vix)
        except Exception as e:
            logger.error("VIX Yahoo fetch failed: %s", str(e))

    async def _fetch_coingecko_metrics(self, client: httpx.AsyncClient):
        # 1. On-Chain Metrics (MVRV Proxy)
        try:
            url = "https://api.coingecko.com/api/v3/coins/bitcoin"
            params = {
                "localization": "false",
                "tickers": "false",
                "market_data": "true",
                "community_data": "false"
            }
            resp = await client.get(url, params=params, headers={"Accept": "application/json"})
            if resp.status_code == 200:
                data = resp.json().get("market_data", {})
                market_cap = float(data.get("market_cap", {}).get("usd", 0))
                vol_24h = float(data.get("total_volume", {}).get("usd", 0))
                mvrv_proxy = market_cap / (vol_24h * 365.0 + 1e-9)
                await self.redis.set("macro:btc_mvrv_proxy", str(mvrv_proxy), ex=900)
        except Exception as e:
            logger.error("CoinGecko BTC fetch failed: %s", str(e))

        # 2. USDT Dominance
        try:
            url = "https://api.coingecko.com/api/v3/global"
            resp = await client.get(url)
            if resp.status_code == 200:
                usdt_dom = float(resp.json()["data"]["market_cap_percentage"]["usdt"])
                await self._set_macro_with_prev("macro:usdt_dominance", usdt_dom)
        except Exception as e:
            logger.error("CoinGecko Global USDT dominance fetch failed: %s", str(e))

    async def _set_macro_with_prev(self, key: str, current_value: float):
        prev = await self.redis.get(key)
        if prev:
            await self.redis.set(f"{key}_prev", prev)
        else:
            await self.redis.set(f"{key}_prev", str(current_value))
        await self.redis.set(key, str(current_value))
        await self.redis.set(f"{key}:ts", str(time.time()))

    async def generate_signal(self, symbol: str, features: FeatureVector) -> StrategySignal:
        dxy = float(await self.redis.get("macro:dxy") or 104.0)
        us10y = float(await self.redis.get("macro:us10y") or 4.5)
        vix = float(await self.redis.get("macro:vix") or 18.0)
        usdt_d = float(await self.redis.get("macro:usdt_dominance") or 6.5)

        dxy_prev = float(await self.redis.get("macro:dxy_prev") or dxy)
        us10y_prev = float(await self.redis.get("macro:us10y_prev") or us10y)
        vix_prev = float(await self.redis.get("macro:vix_prev") or vix)

        if symbol.startswith("XAU"):
            gold_bull_score = 0.0
            if dxy < dxy_prev:
                gold_bull_score += 0.25
            if us10y < us10y_prev:
                gold_bull_score += 0.25
            if vix > vix_prev:
                gold_bull_score += 0.25
            if usdt_d > 6.8:
                gold_bull_score += 0.25

            bull_logit = gold_bull_score
            bear_logit = 1.0 - gold_bull_score
        else:
            mvrv = float(await self.redis.get("macro:btc_mvrv_proxy") or 1.5)
            btc_bull_score = 0.0
            if mvrv < 1.0:
                btc_bull_score += 0.35
            if usdt_d < 6.0:
                btc_bull_score += 0.25
            if vix < vix_prev:
                btc_bull_score += 0.20
            if dxy < dxy_prev:
                btc_bull_score += 0.20

            bull_logit = btc_bull_score
            bear_logit = 1.0 - btc_bull_score

        return StrategySignal(
            name=self.name,
            bull_logit=float(bull_logit),
            bear_logit=float(bear_logit),
            reversal_logit=0.1,
            breakout_logit=0.1,
            base_reliability=0.53
        )
