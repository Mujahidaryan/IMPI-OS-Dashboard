import asyncio
import logging
import time
from typing import Dict, List, Optional
import redis.asyncio as aioredis
import MetaTrader5 as mt5

from config.settings import get_settings
from services.ingestor.models import Tick, AnomalyEvent

logger = logging.getLogger("ExnessMT5")

# Map timeframe strings to MT5 constants
TF_MAP = {
    "1m": mt5.TIMEFRAME_M1,
    "5m": mt5.TIMEFRAME_M5,
    "15m": mt5.TIMEFRAME_M15,
    "1h": mt5.TIMEFRAME_H1,
    "4h": mt5.TIMEFRAME_H4,
}


class ExnessMT5Client:
    """
    Client for Exness MetaTrader 5 terminal API. Runs on a Windows host.
    Performs symbol detection, tick polling, historical candle fetching,
    spread spike monitoring, and failsafe price decay handling.
    """

    def __init__(self, redis_client: aioredis.Redis):
        self.redis = redis_client
        self.settings = get_settings()
        self._running: bool = False
        self._loop_task: asyncio.Task | None = None
        self.gold_symbol: Optional[str] = None
        
        # Normal spread in pips for XAUUSD (usually ~15 to 25 pips on Exness)
        self.NORMAL_SPREAD_PIPS = 25.0
        self.point_size = 0.01  # default fallback

        # Failsafe price variables
        self.last_known_tick: Optional[Tick] = None
        self.disconnect_time: Optional[float] = None

    async def start(self):
        self._running = True
        success = await asyncio.to_thread(self._initialize_mt5)
        if not success:
            logger.error("Failed to initialize MT5 terminal on start.")
            # Set disconnect time to trigger failsafe
            self.disconnect_time = time.time()
        
        self._loop_task = asyncio.create_task(self._tick_stream_loop())
        logger.info("Exness MT5 Client started.")

    async def stop(self):
        self._running = False
        if self._loop_task:
            self._loop_task.cancel()
            try:
                await self._loop_task
            except asyncio.CancelledError:
                pass
        await asyncio.to_thread(mt5.shutdown)
        logger.info("Exness MT5 Client stopped.")

    def _initialize_mt5(self) -> bool:
        """Initialise connection to the MT5 terminal process."""
        try:
            init_ok = mt5.initialize(
                path=self.settings.MT5_TERMINAL_PATH,
                login=int(self.settings.MT5_LOGIN),
                password=self.settings.MT5_PASSWORD,
                server=self.settings.MT5_SERVER,
                timeout=30000,
            )
            if not init_ok:
                err = mt5.last_error()
                logger.error("MT5 initialization failed. Error: %s", str(err))
                return False

            # Detect Gold Symbol name
            self.gold_symbol = None
            for name in ["XAUUSD", "XAUUSDm", "GOLD", "XAUUSD."]:
                info = mt5.symbol_info(name)
                if info is not None:
                    # Make sure symbol is visible/selected in Market Watch
                    mt5.symbol_select(name, True)
                    if info.visible:
                        self.gold_symbol = name
                        self.point_size = info.point
                        logger.info(
                            "Detected Gold Symbol: %s (point size: %f)",
                            name, self.point_size
                        )
                        break

            if not self.gold_symbol:
                logger.error("Could not locate any valid Gold symbol in MT5 Market Watch.")
                return False

            return True
        except Exception as e:
            logger.error("Exception during MT5 initialization: %s", str(e))
            return False

    async def _tick_stream_loop(self):
        last_tick_time = 0
        while self._running:
            try:
                if not self.gold_symbol or not await asyncio.to_thread(mt5.terminal_info):
                    logger.warning("MT5 disconnected or uninitialized. Reconnecting...")
                    success = await asyncio.to_thread(self._initialize_mt5)
                    if not success:
                        if self.disconnect_time is None:
                            self.disconnect_time = time.time()
                        
                        # Apply price decay failsafe if we have a last known price
                        if self.last_known_tick:
                            await self._apply_decay_failsafe()
                            
                        # Emit MT5 disconnect AnomalyEvent
                        anomaly = AnomalyEvent(
                            symbol="XAUUSD_EXNESS",
                            anomaly_type="mt5_disconnected",
                            severity=0.9,
                            description="MetaTrader 5 terminal connection lost",
                            raw_value=1.0,
                            expected_range=(0.0, 0.0),
                            timestamp_ms=int(time.time() * 1000)
                        )
                        await self.redis.publish("channel:anomalies", anomaly.to_bytes())
                        await asyncio.sleep(5.0)
                        continue

                # We are connected, reset disconnect time if we were offline
                self.disconnect_time = None

                tick = await asyncio.to_thread(mt5.symbol_info_tick, self.gold_symbol)
                if tick is not None and tick.time_msc != last_tick_time:
                    last_tick_time = tick.time_msc
                    
                    canonical_tick = Tick(
                        symbol="XAUUSD_EXNESS",
                        exchange="exness",
                        bid=tick.bid,
                        ask=tick.ask,
                        last=tick.last if tick.last > 0 else (tick.bid + tick.ask) / 2.0,
                        volume=tick.volume_real if tick.volume_real > 0 else float(tick.volume),
                        timestamp_ms=tick.time_msc,
                    )
                    
                    self.last_known_tick = canonical_tick
                    
                    # Store tick and publish to Redis
                    await self.redis.set("latest_tick:XAUUSD_EXNESS", canonical_tick.to_bytes())
                    await self.redis.publish("channel:ticks:XAUUSD_EXNESS", canonical_tick.to_bytes())

                    # Monitor Spread Spike
                    spread_points = tick.ask - tick.bid
                    spread_pips = spread_points / (self.point_size * 10)  # pip is 10 points
                    await self.redis.set("exness:spread:XAUUSD", str(spread_pips), ex=60)
                    
                    if spread_pips > self.NORMAL_SPREAD_PIPS * 3:
                        severity = min(spread_pips / self.NORMAL_SPREAD_PIPS / 10.0, 1.0)
                        anomaly = AnomalyEvent(
                            symbol="XAUUSD_EXNESS",
                            anomaly_type="spread_spike",
                            severity=severity,
                            description=f"Spread spike: {spread_pips:.1f} pips (threshold: {self.NORMAL_SPREAD_PIPS * 3:.1f})",
                            raw_value=spread_pips,
                            expected_range=(0.0, self.NORMAL_SPREAD_PIPS * 3.0),
                            timestamp_ms=tick.time_msc
                        )
                        await self.redis.publish("channel:anomalies", anomaly.to_bytes())

                await asyncio.sleep(0.25)  # Poll every 250ms
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in MT5 tick stream loop: %s", str(e), exc_info=True)
                await asyncio.sleep(1.0)

    async def _apply_decay_failsafe(self):
        """Applies price decay failsafe to the latest tick if MT5 is disconnected."""
        if not self.last_known_tick or not self.disconnect_time:
            return
        
        seconds_elapsed = time.time() - self.disconnect_time
        # Fall back to last known price * (1 - 0.0001) ** seconds_elapsed
        decay_factor = (1.0 - 0.0001) ** seconds_elapsed
        
        decayed_tick = Tick(
            symbol="XAUUSD_EXNESS",
            exchange="exness",
            bid=self.last_known_tick.bid * decay_factor,
            ask=self.last_known_tick.ask * decay_factor,
            last=self.last_known_tick.last * decay_factor,
            volume=0.0,
            timestamp_ms=int(time.time() * 1000)
        )
        
        await self.redis.set("latest_tick:XAUUSD_EXNESS", decayed_tick.to_bytes())
        await self.redis.publish("channel:ticks:XAUUSD_EXNESS", decayed_tick.to_bytes())

    async def fetch_candles(self, timeframe: str, count: int = 500) -> List[dict]:
        """Fetch historical candle rates from MT5 terminal for warmup/gap fill."""
        if not self.gold_symbol:
            logger.error("MT5 Gold symbol not set. Cannot fetch candles.")
            return []

        tf_mt5 = TF_MAP.get(timeframe)
        if tf_mt5 is None:
            logger.error("Unsupported timeframe requested: %s", timeframe)
            return []

        def _fetch():
            rates = mt5.copy_rates_from_pos(self.gold_symbol, tf_mt5, 0, count)
            if rates is None:
                err = mt5.last_error()
                logger.error("MT5 copy_rates_from_pos failed: %s", str(err))
                return []
            return [
                {
                    "time": int(r["time"]) * 1000,  # convert seconds to ms
                    "open": float(r["open"]),
                    "high": float(r["high"]),
                    "low": float(r["low"]),
                    "close": float(r["close"]),
                    "volume": float(r["tick_volume"]),
                }
                for r in rates
            ]

        try:
            return await asyncio.to_thread(_fetch)
        except Exception as e:
            logger.error("Error fetching rates from MT5: %s", str(e))
            return []
