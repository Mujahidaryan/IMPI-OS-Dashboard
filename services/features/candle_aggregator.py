import asyncio
import json
import logging
from collections import defaultdict
from typing import Dict, List, Optional
import httpx
import redis.asyncio as aioredis

from services.ingestor.models import Tick, Candle
from services.ingestor.exness_mt5 import ExnessMT5Client

logger = logging.getLogger("CandleAggregator")


class CandleAggregator:
    """
    Subscribes to raw tick streams and aggregates them into OHLCV candles
    across multiple timeframes (1m, 5m, 15m, 1h, 4h).
    Maintains a rolling ring buffer of candles in Redis/Memory for indicator analysis.
    """

    def __init__(self, redis_client: aioredis.Redis, mt5_client: Optional[ExnessMT5Client] = None):
        self.redis = redis_client
        self.mt5_client = mt5_client
        self._running = False
        self._tasks: List[asyncio.Task] = []
        
        # Local ring buffers: self.candles[symbol][timeframe] = list[Candle]
        self.candles: Dict[str, Dict[str, List[Candle]]] = defaultdict(lambda: defaultdict(list))
        self.max_candles = 1000

    async def start(self):
        self._running = True
        
        # Warmup history
        await self._warmup_history()
        
        # Start message listeners
        self._tasks.append(asyncio.create_task(self._listen_ticks()))
        self._tasks.append(asyncio.create_task(self._listen_binance_candles()))
        logger.info("Candle Aggregator service started.")

    async def stop(self):
        self._running = False
        for t in self._tasks:
            t.cancel()
            try:
                await t
            except asyncio.CancelledError:
                pass
        logger.info("Candle Aggregator service stopped.")

    async def _warmup_history(self):
        """Warm up historical candles for all assets and timeframes."""
        timeframes = ["1m", "5m", "15m", "1h", "4h"]
        symbols = ["XAUUSD_EXNESS", "XAUUSDT", "BTCUSDT"]

        for symbol in symbols:
            for tf in timeframes:
                history = []
                if symbol == "XAUUSD_EXNESS" and self.mt5_client:
                    history = await self.mt5_client.fetch_candles(tf, count=500)
                elif symbol in ["XAUUSDT", "BTCUSDT"]:
                    history = await self._fetch_binance_history(symbol, tf, count=500)

                for c_dict in history:
                    candle = Candle(
                        symbol=symbol,
                        timeframe=tf,
                        time_ms=c_dict["time"],
                        open=c_dict["open"],
                        high=c_dict["high"],
                        low=c_dict["low"],
                        close=c_dict["close"],
                        volume=c_dict["volume"],
                        confirmed=True
                    )
                    self.candles[symbol][tf].append(candle)
                
                # Sort candles to ensure correct order
                self.candles[symbol][tf].sort(key=lambda x: x.time_ms)
                logger.info(
                    "Warmed up %d historical candles for %s on %s",
                    len(self.candles[symbol][tf]), symbol, tf
                )

    async def _fetch_binance_history(self, symbol: str, timeframe: str, count: int = 500) -> List[dict]:
        """Fetch historical klines from Binance Futures REST API."""
        tf_map = {"1m": "1m", "5m": "5m", "15m": "15m", "1h": "1h", "4h": "4h"}
        url = "https://fapi.binance.com/fapi/v1/klines"
        params = {
            "symbol": symbol,
            "interval": tf_map[timeframe],
            "limit": count
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, params=params)
            if response.status_code == 200:
                klines = response.json()
                return [
                    {
                        "time": int(k[0]),
                        "open": float(k[1]),
                        "high": float(k[2]),
                        "low": float(k[3]),
                        "close": float(k[4]),
                        "volume": float(k[5]),
                    }
                    for k in klines
                ]
            else:
                logger.error(
                    "Binance REST history call failed for %s %s: status %d",
                    symbol, timeframe, response.status_code
                )
        except Exception as e:
            logger.error("Exception fetching Binance history for %s: %s", symbol, str(e))
        return []

    async def get_candles(self, symbol: str, timeframe: str, count: int = 200) -> List[Candle]:
        """Retrieve recent candles for technical indicator calculation."""
        buffer = self.candles[symbol][timeframe]
        return buffer[-count:]

    async def _listen_ticks(self):
        """Listen to ticks from MT5 (XAUUSD_EXNESS) and aggregate them manually."""
        pubsub = self.redis.pubsub()
        await pubsub.subscribe("channel:ticks:XAUUSD_EXNESS")

        while self._running:
            try:
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if not message:
                    continue

                tick = Tick.from_bytes(message["data"])
                await self._process_tick("XAUUSD_EXNESS", tick)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in MT5 tick aggregator loop: %s", str(e), exc_info=True)
                await asyncio.sleep(1)

        await pubsub.unsubscribe("channel:ticks:XAUUSD_EXNESS")

    async def _listen_binance_candles(self):
        """Listen to confirmed candles directly from the Binance WebSocket client."""
        pubsub = self.redis.pubsub()
        await pubsub.subscribe("channel:candles:XAUUSDT", "channel:candles:BTCUSDT")

        while self._running:
            try:
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if not message:
                    continue

                data = json.loads(message["data"])
                candle = Candle.from_dict(data)

                # Append to our local ring buffer
                symbol = candle.symbol
                tf = candle.timeframe
                
                # Check if we should update or append
                buffer = self.candles[symbol][tf]
                if buffer and buffer[-1].time_ms == candle.time_ms:
                    buffer[-1] = candle  # Update current open bar
                else:
                    buffer.append(candle)  # Add new bar
                    if len(buffer) > self.max_candles:
                        buffer.pop(0)

                # If confirmed, propagate to sub-timeframes if needed, and publish
                if candle.confirmed:
                    await self._propagate_binance_candle(candle)
                    await self.redis.publish(f"channel:candles:confirmed:{symbol}", candle.to_bytes())

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in Binance candle listener: %s", str(e), exc_info=True)
                await asyncio.sleep(1)

        await pubsub.unsubscribe("channel:candles:XAUUSDT", "channel:candles:BTCUSDT")

    async def _process_tick(self, symbol: str, tick: Tick):
        """Aggregate tick data into multiple timeframes for Exness."""
        t_ms = tick.timestamp_ms
        price = tick.last
        vol = tick.volume

        timeframe_seconds = {
            "1m": 60,
            "5m": 300,
            "15m": 900,
            "1h": 3600,
            "4h": 14400,
        }

        for tf, secs in timeframe_seconds.items():
            candle_start = (t_ms // (secs * 1000)) * (secs * 1000)
            buffer = self.candles[symbol][tf]

            # If the last candle matches this starting time, we update it
            if buffer and buffer[-1].time_ms == candle_start:
                c = buffer[-1]
                c.high = max(c.high, price)
                c.low = min(c.low, price)
                c.close = price
                c.volume += vol
                c.confirmed = False
            else:
                # Close the previous candle
                if buffer:
                    buffer[-1].confirmed = True
                    await self.redis.publish(f"channel:candles:confirmed:{symbol}", buffer[-1].to_bytes())

                # Create a new candle
                c = Candle(
                    symbol=symbol,
                    timeframe=tf,
                    time_ms=candle_start,
                    open=price,
                    high=price,
                    low=price,
                    close=price,
                    volume=vol,
                    confirmed=False
                )
                buffer.append(c)
                if len(buffer) > self.max_candles:
                    buffer.pop(0)

            # Publish the temporary candle update (not confirmed) for real-time indicator updates
            await self.redis.publish(f"channel:candles:update:{symbol}", c.to_bytes())

    async def _propagate_binance_candle(self, kline: Candle):
        """Handles higher timeframe calculations for Binance candles from 1m stream."""
        if kline.timeframe != "1m":
            return  # Only propagate from 1m closes

        symbol = kline.symbol
        timeframe_minutes = {
            "5m": 5,
            "15m": 15,
            "1h": 60,
            "4h": 240,
        }

        for tf, mins in timeframe_minutes.items():
            secs = mins * 60
            candle_start = (kline.time_ms // (secs * 1000)) * (secs * 1000)
            buffer = self.candles[symbol][tf]

            # Collect 1m candles within the current period
            one_m_candles = [
                c for c in self.candles[symbol]["1m"]
                if c.time_ms >= candle_start and c.time_ms < candle_start + (secs * 1000)
            ]

            if not one_m_candles:
                continue

            open_p = one_m_candles[0].open
            high_p = max(c.high for c in one_m_candles)
            low_p = min(c.low for c in one_m_candles)
            close_p = one_m_candles[-1].close
            volume_sum = sum(c.volume for c in one_m_candles)
            is_confirmed = (len(one_m_candles) == mins)

            new_candle = Candle(
                symbol=symbol,
                timeframe=tf,
                time_ms=candle_start,
                open=open_p,
                high=high_p,
                low=low_p,
                close=close_p,
                volume=volume_sum,
                confirmed=is_confirmed
            )

            if buffer and buffer[-1].time_ms == candle_start:
                buffer[-1] = new_candle
            else:
                buffer.append(new_candle)
                if len(buffer) > self.max_candles:
                    buffer.pop(0)

            if is_confirmed:
                await self.redis.publish(f"channel:candles:confirmed:{symbol}", new_candle.to_bytes())
            else:
                await self.redis.publish(f"channel:candles:update:{symbol}", new_candle.to_bytes())
