import logging
from typing import List
import numpy as np
from sklearn.isotonic import IsotonicRegression

logger = logging.getLogger("Calibrator")


class ProbabilityCalibrator:
    """
    Fits and applies isotonic regression calibration on raw Bayesian posteriors
    to map them to empirical win rates.
    """

    def __init__(self):
        # We need a model for each dimension or a unified model mapping dominant probability to win/loss
        self._model = IsotonicRegression(out_of_bounds="clip")
        self._fitted = False

    def train(self, historical_probs: List[float], historical_outcomes: List[float]):
        """
        Trains the isotonic regression calibration curve.
        historical_probs should be normalized in [0, 1].
        historical_outcomes should be binary indicators in {0.0, 1.0}.
        """
        if len(historical_probs) < 20:
            logger.debug("Insufficient training samples to fit calibrator. Need at least 20.")
            return

        try:
            x = np.array(historical_probs, dtype=float)
            y = np.array(historical_outcomes, dtype=float)
            
            # Isotonic regression requires sorted inputs or it sorts them internally
            self._model.fit(x, y)
            self._fitted = True
            logger.info("Isotonic calibration model trained successfully on %d samples.", len(x))
        except Exception as e:
            logger.error("Failed to fit Isotonic regression model: %s", str(e))
            self._fitted = False

    def calibrate(self, posteriors: np.ndarray) -> np.ndarray:
        """
        Transforms uncalibrated Bayesian posteriors into calibrated probability space.
        posteriors is expected to be a 4-dimensional vector sum=1.0.
        """
        if not self._fitted:
            # Cold-start path: return original posteriors
            return posteriors

        try:
            # We calibrate each element individually or scale the dominant element
            # Standard practice is to calibrate the probability values directly
            calibrated = np.zeros_like(posteriors)
            for i in range(len(posteriors)):
                calibrated[i] = float(self._model.transform([posteriors[i]])[0])
            
            # Re-normalise to sum to 1.0
            denom = np.sum(calibrated)
            if denom > 0:
                return calibrated / denom
            return posteriors
        except Exception as e:
            logger.error("Failed to calibrate probabilities: %s. Returning raw.", str(e))
            return posteriors

    def update_model(self, model: IsotonicRegression):
        """Allows direct model injection from the learning loop updates."""
        self._model = model
        self._fitted = True
