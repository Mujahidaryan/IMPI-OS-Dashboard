import logging
import redis.asyncio as aioredis
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from config.settings import get_settings
from services.api.ws_broadcaster import broadcaster
from services.api.routes import signals, risk, health, history

logger = logging.getLogger("APIServer")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize Redis connection
    settings = get_settings()
    logger.info("Connecting to Redis at %s", settings.REDIS_URL)
    app.state.redis = aioredis.from_url(
        settings.REDIS_URL,
        decode_responses=False  # Keep raw bytes for consistency with other files
    )
    yield
    # Shutdown: Close Redis connection
    logger.info("Closing Redis connection...")
    await app.state.redis.close()


def create_app() -> FastAPI:
    settings = get_settings()
    
    app = FastAPI(
        title="IPMI-OS 2.0 API Server",
        description="Probabilistic Market Intelligence OS Real-Time Backend",
        version="2.0.0",
        lifespan=lifespan
    )

    # CORS configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Allow all dashboard connections, change to specific URL in production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register Routers
    app.include_router(signals.router, prefix="/api", tags=["Signals"])
    app.include_router(risk.router, prefix="/api", tags=["Risk"])
    app.include_router(health.router, prefix="/api", tags=["Health"])
    app.include_router(history.router, prefix="/api", tags=["History"])

    # Root route for server identification
    @app.get("/")
    async def index():
        return {
            "name": "IPMI-OS Backend",
            "status": "online",
            "version": "2.0.0"
        }

    # WebSocket Real-Time Endpoint
    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        await broadcaster.connect(websocket)
        try:
            while True:
                # Keep-alive loop, wait for client disconnects or messages
                await websocket.receive_text()
        except WebSocketDisconnect:
            await broadcaster.disconnect(websocket)
        except Exception as e:
            logger.warning("WebSocket connection exception: %s", str(e))
            await broadcaster.disconnect(websocket)

    return app


app = create_app()
