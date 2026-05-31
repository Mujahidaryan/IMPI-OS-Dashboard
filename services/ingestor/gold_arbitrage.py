import asyncio
import logging
import time
import redis.asyncio as aioredis

from services.ingestor.models import Tick, AnomalyEvent

logger = logging.getLogger("GoldArbitrage")


class GoldArbitrageMonitor:
    """
    Compares Exness XAUUSD spot CFD prices with basis-corrected
    Binance XAUUSDT perpetual futures prices to identify cross-exchange divergence.
    """

    def __init__(self, redis_client: aioredis.Redis):
        self.redis = redis_client
        self._running = False
        self._task: asyncio.Task | None = None

    async def start(self):
        self._running = True
        self._task = asyncio.create_task(self._monitor_loop())
        logger.info("Gold Arbitrage Tracker started.")

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Gold Arbitrage Tracker stopped.")

    async def _monitor_loop(self):
        while self._running:
            try:
                await asyncio.sleep(30)  # Check divergence every 30 seconds

                exness_bytes = await self.redis.get("latest_tick:XAUUSD_EXNESS")
                binance_bytes = await self.redis.get("latest_tick:XAUUSDT")

                if not exness_bytes or not binance_bytes:
                    logger.debug("Cannot compute arbitrage. Missing ticks.")
                    continue

                exness_tick = Tick.from_bytes(exness_bytes)
                binance_tick = Tick.from_bytes(binance_bytes)

                exness_price = exness_tick.last
                binance_price = binance_tick.last

                # Calculate basis correction using perpetual funding rate
                funding_raw = await self.redis.get("funding:XAUUSDT")
                funding_rate = float(funding_raw) if funding_raw else 0.0001
                basis_correction = 1.0 + (funding_rate * 8.0)
                binance_spot_equivalent = binance_price / basis_correction

                if exness_price <= 0.0:
                    continue

                raw_divergence = abs(exness_price - binance_spot_equivalent) / exness_price

                # Publish values to Redis cache
                await self.redis.set("gold:arbitrage:divergence", str(raw_divergence), ex=60)
                await self.redis.set("gold:arbitrage:basis", str(basis_correction), ex=60)

                # Divergence threshold checks (>0.3% is an anomaly)
                if raw_divergence > 0.003:
                    severity = min(raw_divergence / 0.01, 1.0)  # max severity at 1% divergence
                    anomaly = AnomalyEvent(
                        symbol="XAUUSD",
                        anomaly_type="cross_exchange_divergence",
                        severity=severity,
                        description=(
                            f"Arbitrage Divergence! Exness: {exness_price:.2f} | "
                            f"Binance equivalent: {binance_spot_equivalent:.2f} (diff: {raw_divergence*100:.3f}%)"
                        ),
                        raw_value=raw_divergence,
                        expected_range=(0.0, 0.003),
                        timestamp_ms=int(time.time() * 1000)
                    )
                    await self.redis.publish("channel:anomalies", anomaly.to_bytes())
                    logger.warning(
                        "Gold cross-exchange divergence detected: %.4f%%",
                        raw_divergence * 100
                    )

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in gold arbitrage check: %s", str(e), exc_info=True)
