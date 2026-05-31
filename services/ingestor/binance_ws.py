import asyncio
import json
import logging
import random
import time
from typing import Dict
import websockets
import redis.asyncio as aioredis

from config.settings import get_settings
from services.ingestor.models import Tick
from services.ingestor.clock_sync import ClockSynchronizer

logger = logging.getLogger("BinanceWS")


class BinanceWebSocketClient:
    """
    Asynchronously streams market data from Binance Futures WebSockets,
    normalises it into canonical models, and caches metrics in Redis.
    """

    def __init__(self, clock_sync: ClockSynchronizer, redis_client: aioredis.Redis):
        self.clock_sync = clock_sync
        self.redis = redis_client
        self.settings = get_settings()
        self._running = False
        self._task: asyncio.Task | None = None
        self._last_agg_trade_ids: Dict[str, int] = {}
        
        # In-memory store to merge bookTicker (bid/ask) and aggTrade (last price) into Tick
        self._tick_cache: Dict[str, dict] = {
            "XAUUSDT": {"bid": 0.0, "ask": 0.0, "last": 0.0, "volume": 0.0},
            "BTCUSDT": {"bid": 0.0, "ask": 0.0, "last": 0.0, "volume": 0.0},
        }

    async def start(self):
        self._running = True
        self._task = asyncio.create_task(self._connect_loop())
        logger.info("Binance WS Ingestor task started.")

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Binance WS Ingestor task stopped.")

    async def _connect_loop(self):
        base_delay = 1.0
        max_delay = 60.0
        multiplier = 2.0
        delay = base_delay

        streams = [
            "xauusdt@aggTrade",
            "xauusdt@bookTicker",
            "xauusdt@depth5@100ms",
            "xauusdt@kline_1m",
            "xauusdt@markPrice@1s",
            "btcusdt@aggTrade",
            "btcusdt@bookTicker",
            "btcusdt@depth5@100ms",
            "btcusdt@kline_1m",
            "btcusdt@markPrice@1s",
        ]
        url = f"wss://fstream.binance.com/stream?streams={'/'.join(streams)}"

        while self._running:
            try:
                logger.info("Connecting to Binance WebSocket: %s", url)
                async with websockets.connect(url) as ws:
                    delay = base_delay  # Reset delay on successful connection
                    logger.info("Connected to Binance WebSocket.")
                    while self._running:
                        message = await ws.recv()
                        await self._handle_message(message)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Binance WS Connection error: %s", str(e))
                if not self._running:
                    break
                # Apply exponential backoff with jitter
                jitter = random.uniform(-0.2, 0.2) * delay
                sleep_time = min(delay + jitter, max_delay)
                logger.info("Reconnecting in %.2f seconds...", sleep_time)
                await asyncio.sleep(max_sleep_time := max(0.1, sleep_time))
                delay = min(delay * multiplier, max_delay)

    async def _handle_message(self, message: str):
        try:
            payload = json.loads(message)
            stream_name = payload.get("stream")
            data = payload.get("data")
            if not stream_name or not data:
                return

            symbol = data.get("s")
            if not symbol:
                return
            symbol = symbol.upper()

            event_type = data.get("e")

            # 1. Mark Price and Funding Rate
            if event_type == "markPriceUpdate":
                funding_rate = float(data.get("r", 0.0))
                await self.redis.set(f"funding:{symbol}", str(funding_rate), ex=120)

            # 2. Top of Book Tickers
            elif "bookTicker" in stream_name:
                bid_price = float(data.get("b", 0.0))
                ask_price = float(data.get("a", 0.0))
                
                cache = self._tick_cache.get(symbol)
                if cache:
                    cache["bid"] = bid_price
                    cache["ask"] = ask_price
                    await self._publish_tick(symbol, data.get("E", int(time.time() * 1000)))

            # 3. Aggregated Trades (Volume & Trade matching)
            elif event_type == "aggTrade":
                price = float(data.get("p", 0.0))
                volume = float(data.get("q", 0.0))
                buyer_maker = bool(data.get("m", False))
                trade_id = int(data.get("a", 0))
                event_time = int(data.get("T", int(time.time() * 1000)))

                # Sequence gap checking
                last_id = self._last_agg_trade_ids.get(symbol)
                if last_id is not None and trade_id > last_id + 1:
                    logger.warning(
                        "Sequence gap detected for %s. Missing trade IDs: %d to %d",
                        symbol, last_id + 1, trade_id - 1
                    )
                self._last_agg_trade_ids[symbol] = trade_id

                # Calculate delta for CVD
                delta = -volume if buyer_maker else volume
                await self.redis.lpush(f"cvd_ticks:{symbol}", str(delta))
                await self.redis.ltrim(f"cvd_ticks:{symbol}", 0, 999)

                cache = self._tick_cache.get(symbol)
                if cache:
                    cache["last"] = price
                    cache["volume"] = volume
                    await self._publish_tick(symbol, event_time)

            # 4. Order Book Imbalance (depth5@100ms)
            elif "depth5" in stream_name:
                bids = data.get("b", [])
                asks = data.get("a", [])
                bid_volume = sum(float(qty) for _, qty in bids)
                ask_volume = sum(float(qty) for _, qty in asks)
                
                denom = bid_volume + ask_volume
                ob_imbalance = (bid_volume - ask_volume) / denom if denom > 0 else 0.0
                await self.redis.set(f"ob_imbalance:{symbol}", str(ob_imbalance), ex=5)

            # 5. Kline/Candle streaming
            elif event_type == "kline":
                kline = data.get("k", {})
                candle_data = {
                    "symbol": symbol,
                    "timeframe": kline.get("i"),
                    "time_ms": self.clock_sync.correct(int(kline.get("t", 0))),
                    "open": float(kline.get("o", 0.0)),
                    "high": float(kline.get("h", 0.0)),
                    "low": float(kline.get("l", 0.0)),
                    "close": float(kline.get("c", 0.0)),
                    "volume": float(kline.get("v", 0.0)),
                    "confirmed": bool(kline.get("x", False)),
                }
                # Publish to channel for candle aggregator / strategies
                await self.redis.publish(f"channel:candles:{symbol}", json.dumps(candle_data))

        except Exception as e:
            logger.error("Error processing Binance WS message: %s", str(e), exc_info=True)

    async def _publish_tick(self, symbol: str, raw_timestamp_ms: int):
        cache = self._tick_cache[symbol]
        if cache["bid"] == 0.0 or cache["last"] == 0.0:
            return  # Wait until we have both bid/ask and last trade price

        corrected_time = self.clock_sync.correct(raw_timestamp_ms)
        tick = Tick(
            symbol=symbol,
            exchange="binance",
            bid=cache["bid"],
            ask=cache["ask"],
            last=cache["last"],
            volume=cache["volume"],
            timestamp_ms=corrected_time,
        )
        # Save to hot cache in Redis
        await self.redis.set(f"latest_tick:{symbol}", tick.to_bytes())
        # Publish tick event to channel
        await self.redis.publish(f"channel:ticks:{symbol}", tick.to_bytes())
