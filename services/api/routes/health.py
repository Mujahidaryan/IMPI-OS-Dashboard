import logging
from fastapi import APIRouter, Request
from services.macro.staleness_tracker import StalenessTracker

router = APIRouter()
logger = logging.getLogger("routes.health")


@router.get("/health", summary="Full system dependency health check")
async def get_health(request: Request):
    redis = request.app.state.redis
    tracker = StalenessTracker(redis)
    feed_status = await tracker.check_health()

    # Check Redis connectivity
    redis_ok = False
    try:
        await redis.ping()
        redis_ok = True
    except Exception:
        pass

    # Check PostgreSQL connectivity
    pg_ok = False
    try:
        from services.learning.prediction_store import PredictionStore
        store = PredictionStore()
        count = await store.get_prediction_count()
        pg_ok = True
    except Exception:
        pass

    # Overall status
    all_feeds_green = all(v.get("status") == "green" for v in feed_status.values())
    overall = "healthy" if (redis_ok and pg_ok and all_feeds_green) else "degraded"

    return {
        "status": overall,
        "redis": "connected" if redis_ok else "disconnected",
        "postgresql": "connected" if pg_ok else "disconnected",
        "feeds": feed_status,
    }
