import logging
import numpy as np
from fastapi import APIRouter, Request, Query
from services.learning.prediction_store import PredictionStore

router = APIRouter()
logger = logging.getLogger("routes.history")


@router.get("/history", summary="Get historical predictions and outcome metrics")
async def get_history(
    request: Request,
    limit: int = Query(default=100, ge=1, le=1000)
):
    """
    Returns recent predictions joined with their outcomes, along with
    cached rolling Brier score and ECE calibration metrics.
    """
    redis = request.app.state.redis
    store = PredictionStore()

    predictions = await store.get_recent_predictions(limit=limit)

    brier_bytes = await redis.get("calibration:brier")
    ece_bytes = await redis.get("calibration:ece")

    brier_score = float(brier_bytes.decode()) if brier_bytes else None
    ece = float(ece_bytes.decode()) if ece_bytes else None

    return {
        "predictions": predictions,
        "metrics": {
            "brier_score": brier_score,
            "ece": ece,
            "count": len(predictions)
        }
    }


@router.get("/history/calibration", summary="Get data points for reliability/calibration curve")
async def get_calibration_data(request: Request):
    """
    Buckets historical predictions into 10 probability bins (0-10%, 10-20%, etc.)
    and returns the mean predicted probability vs the actual outcome frequency.
    """
    store = PredictionStore()
    probs, outcomes = await store.get_historical_data_for_calibration()

    if not probs:
        return {"curve": [], "total_samples": 0}

    probs_arr = np.array(probs, dtype=float)
    outcomes_arr = np.array(outcomes, dtype=float)

    bins = np.linspace(0.0, 1.0, 11)  # 10 bins
    curve = []
    n_samples = len(probs_arr)

    for i in range(10):
        mask = (probs_arr >= bins[i]) & (probs_arr < bins[i+1])
        bin_count = int(np.sum(mask))
        
        if bin_count > 0:
            mean_pred = float(np.mean(probs_arr[mask]))
            actual_freq = float(np.mean(outcomes_arr[mask]))
        else:
            mean_pred = float((bins[i] + bins[i+1]) / 2.0)
            actual_freq = 0.0

        curve.append({
            "bin": i + 1,
            "range": f"{int(bins[i]*100)}-{int(bins[i+1]*100)}%",
            "count": bin_count,
            "mean_predicted": round(mean_pred, 4),
            "actual_frequency": round(actual_freq, 4)
        })

    return {
        "curve": curve,
        "total_samples": n_samples
    }
