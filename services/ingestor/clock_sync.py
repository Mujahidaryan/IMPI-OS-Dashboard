import asyncio
import logging
import time
import httpx

logger = logging.getLogger("ClockSync")


class ClockSynchronizer:
    """
    Synchronises the local system clock with Binance server time
    to calculate precise network latency and normalise event timestamps.
    """

    def __init__(self):
        self.offset_ms: int = 0
        self._running: bool = False
        self._sync_task: asyncio.Task | None = None

    async def start(self):
        self._running = True
        # Do initial sync
        await self.sync()
        self._sync_task = asyncio.create_task(self._sync_loop())

    async def stop(self):
        self._running = False
        if self._sync_task:
            self._sync_task.cancel()
            try:
                await self._sync_task
            except asyncio.CancelledError:
                pass

    async def sync(self) -> int:
        """Fetch Binance server time and compute offset: local_time - server_time."""
        url = "https://fapi.binance.com/fapi/v1/time"
        try:
            t_before = int(time.time() * 1000)
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(url)
            t_after = int(time.time() * 1000)

            if response.status_code == 200:
                server_time = int(response.json()["serverTime"])
                # Estimate latency as half of round trip time (RTT)
                rtt = t_after - t_before
                estimated_server_time = server_time + (rtt // 2)
                self.offset_ms = t_after - estimated_server_time
                logger.info(
                    "Clock synchronised. RTT: %d ms, Time Offset: %d ms",
                    rtt, self.offset_ms
                )
                return self.offset_ms
            else:
                logger.warning(
                    "Failed to sync clock. Binance returned status %d",
                    response.status_code
                )
        except Exception as e:
            logger.error("Error during clock sync: %s", str(e))
        return self.offset_ms

    def correct(self, local_timestamp_ms: int) -> int:
        """Adjust a local timestamp by the sync offset to yield Binance-aligned time."""
        return local_timestamp_ms - self.offset_ms

    async def _sync_loop(self):
        """Periodically sync clock every 30 minutes."""
        while self._running:
            try:
                await asyncio.sleep(1800)  # 30 minutes
                await self.sync()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in clock sync loop: %s", str(e))
                await asyncio.sleep(60)
