import logging
import redis.asyncio as aioredis
from fastapi import APIRouter, Request

router = APIRouter()
logger = logging.getLogger("routes.risk")


def _get_redis(request: Request) -> aioredis.Redis:
    return request.app.state.redis


@router.get("/risk", summary="Get current portfolio risk metrics")
async def get_risk(request: Request):
    redis: aioredis.Redis = _get_redis(request)

    balance = float(await redis.get("risk:balance") or 10000.0)
    peak = float(await redis.get("risk:peak_balance") or balance)
    drawdown_pct = (peak - balance) / peak if peak > 0 else 0.0
    halted_raw = await redis.get("risk:drawdown_halt")
    halted = (halted_raw and halted_raw.decode() == "true")
    consecutive_losses = int(await redis.get("risk:consecutive_losses") or 0)

    brier = await redis.get("calibration:brier")
    ece = await redis.get("calibration:ece")

    # Per-symbol VaR info
    var_info = {}
    for sym in ["XAUUSD_EXNESS", "XAUUSDT", "BTCUSDT"]:
        corr_raw = await redis.get(f"risk:correlation:{sym}")
        var_info[sym] = float(corr_raw) if corr_raw else 0.0

    return {
        "account_balance": balance,
        "peak_balance": peak,
        "drawdown_pct": round(drawdown_pct * 100, 2),
        "trading_halted": halted,
        "consecutive_losses": consecutive_losses,
        "calibration": {
            "brier_score": float(brier.decode()) if brier else None,
            "ece": float(ece.decode()) if ece else None,
        },
        "correlation_exposure": var_info,
    }
