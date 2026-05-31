import logging
import numpy as np
import redis.asyncio as aioredis
from typing import List, Tuple

from services.learning.prediction_store import PredictionStore
from services.fusion.calibration import ProbabilityCalibrator

logger = logging.getLogger("CalibrationTracker")


class CalibrationTracker:
    """
    Computes rolling Brier Score and Expected Calibration Error (ECE).
    Triggers Isotonic Regression updates when calibration error exceeds tolerance.
    """

    def __init__(self, db: PredictionStore, calibrator: ProbabilityCalibrator, redis_client: aioredis.Redis):
        self.db = db
        self.calibrator = calibrator
        self.redis = redis_client

    async def calculate_metrics(self) -> Tuple[float, float]:
        """
        Loads all historical outcomes and computes Brier score + ECE.
        Returns: (brier_score, expected_calibration_error).
        """
        probs, outcomes = await self.db.get_historical_data_for_calibration()
        if len(probs) < 10:
            return 0.25, 0.0  # Default neutral values

        probs_arr = np.array(probs, dtype=float)
        outcomes_arr = np.array(outcomes, dtype=float)

        # 1. Brier Score (mean squared error of probability forecasts)
        brier_score = float(np.mean((probs_arr - outcomes_arr) ** 2))

        # 2. Expected Calibration Error (ECE)
        bins = np.linspace(0.0, 1.0, 11)  # 10 buckets
        ece = 0.0
        n_samples = len(probs_arr)

        for i in range(10):
            mask = (probs_arr >= bins[i]) & (probs_arr < bins[i+1])
            bin_size = np.sum(mask)
            if bin_size > 0:
                bin_acc = np.mean(outcomes_arr[mask])
                bin_conf = np.mean(probs_arr[mask])
                ece += (bin_size / n_samples) * abs(bin_conf - bin_acc)

        # Cache metrics in Redis
        await self.redis.set("calibration:brier", f"{brier_score:.4f}")
        await self.redis.set("calibration:ece", f"{ece:.4f}")

        # Retraining trigger if calibration is poor
        if ece > 0.10 and len(probs_arr) >= 100:
            logger.warning("Calibration error ECE=%.3f > 0.10. Retraining Isotonic model...", ece)
            self.calibrator.train(probs, outcomes)

        return brier_score, ece
