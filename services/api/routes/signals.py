import json
import logging
from typing import Optional
import redis.asyncio as aioredis
from fastapi import APIRouter, HTTPException, Request

router = APIRouter()
logger = logging.getLogger("routes.signals")

VALID_SYMBOLS = {"XAUUSD_EXNESS", "XAUUSDT", "BTCUSDT"}


def _get_redis(request: Request) -> aioredis.Redis:
    return request.app.state.redis


@router.get("/signals", summary="Get latest signals for all 3 assets")
async def get_all_signals(request: Request):
    """Returns the latest Bayesian fusion PredictionOutput for all 3 assets."""
    redis: aioredis.Redis = _get_redis(request)
    results = []

    for symbol in ["XAUUSD_EXNESS", "XAUUSDT", "BTCUSDT"]:
        raw = await redis.get(f"latest_signal:{symbol}")
        if raw:
            results.append(json.loads(raw))
        else:
            results.append({"asset": symbol, "status": "warming_up"})

    return {"signals": results, "count": len(results)}


@router.get("/signals/{symbol}", summary="Get latest signal for a specific asset")
async def get_signal_by_symbol(symbol: str, request: Request):
    """Returns the latest PredictionOutput for the specified asset."""
    symbol = symbol.upper()
    if symbol not in VALID_SYMBOLS:
        raise HTTPException(status_code=404, detail=f"Symbol '{symbol}' not found. Valid: {list(VALID_SYMBOLS)}")

    redis: aioredis.Redis = _get_redis(request)
    raw = await redis.get(f"latest_signal:{symbol}")
    if not raw:
        return {"asset": symbol, "status": "warming_up"}

    return json.loads(raw)
