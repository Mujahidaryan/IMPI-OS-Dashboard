import asyncio
import json
import logging
from typing import Set
from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger("WSBroadcaster")


class WebSocketBroadcaster:
    """
    Manages all connected WebSocket dashboard clients and broadcasts
    prediction outputs, tick updates, and anomaly events in real time.
    """

    def __init__(self):
        self._connections: Set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        async with self._lock:
            self._connections.add(websocket)
        logger.info("Dashboard client connected. Total: %d", len(self._connections))

    async def disconnect(self, websocket: WebSocket):
        async with self._lock:
            self._connections.discard(websocket)
        logger.info("Dashboard client disconnected. Total: %d", len(self._connections))

    async def broadcast(self, message: dict):
        """Broadcasts a JSON message to all connected dashboard clients."""
        if not self._connections:
            return

        payload = json.dumps(message)
        dead_connections: Set[WebSocket] = set()

        async with self._lock:
            connections_snapshot = set(self._connections)

        for ws in connections_snapshot:
            try:
                await ws.send_text(payload)
            except WebSocketDisconnect:
                dead_connections.add(ws)
            except Exception as e:
                logger.warning("Failed to send to WebSocket client: %s", str(e))
                dead_connections.add(ws)

        if dead_connections:
            async with self._lock:
                self._connections -= dead_connections
            logger.info("Removed %d dead connections. Total: %d", len(dead_connections), len(self._connections))

    async def broadcast_prediction(self, prediction_dict: dict):
        await self.broadcast({"type": "prediction", "data": prediction_dict})

    async def broadcast_tick(self, tick_dict: dict):
        await self.broadcast({"type": "tick", "data": tick_dict})

    async def broadcast_anomaly(self, anomaly_dict: dict):
        await self.broadcast({"type": "anomaly", "data": anomaly_dict})

    async def broadcast_regime(self, symbol: str, regime_dict: dict):
        await self.broadcast({"type": "regime", "symbol": symbol, "data": regime_dict})

    async def broadcast_health(self, health_dict: dict):
        await self.broadcast({"type": "health", "data": health_dict})


# Shared broadcaster instance
broadcaster = WebSocketBroadcaster()
