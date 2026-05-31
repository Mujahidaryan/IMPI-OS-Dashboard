import math
import logging
import numpy as np
import redis.asyncio as aioredis
from typing import List, Dict, Tuple

from config.settings import RegimeLabel
from services.strategies.base import StrategySignal
from services.features.feature_engine import FeatureVector
from services.fusion.output_schema import PredictionOutput
from services.fusion.calibration import ProbabilityCalibrator

logger = logging.getLogger("BayesianFusion")

REGIME_PRIORS = {
    "trending_up":   [0.50, 0.20, 0.15, 0.15],
    "trending_down": [0.20, 0.50, 0.15, 0.15],
    "ranging":       [0.20, 0.20, 0.40, 0.20],
    "expansion":     [0.25, 0.25, 0.15, 0.35],
    "contraction":   [0.25, 0.25, 0.35, 0.15],
    "panic":         [0.10, 0.50, 0.25, 0.15],
    "unknown":       [0.25, 0.25, 0.25, 0.25],
}


class BayesianFusionEngine:
    """
    Core signal fusion engine combining strategy logits and regime priors
    in log space, performing numerical softmax, calibration mapping,
    and output schema packaging.
    """

    def __init__(self, redis_client: aioredis.Redis, calibrator: ProbabilityCalibrator):
        self.redis = redis_client
        self.calibrator = calibrator

    async def fuse_signals(
        self,
        symbol: str,
        signals: List[StrategySignal],
        regime_label: RegimeLabel,
        features: FeatureVector,
        manipulation_prob: float,
        macro_context: dict
    ) -> PredictionOutput:
        """
        Fuses incoming strategy signals with HMM priors and produces a PredictionOutput.
        """
        # Step 1 — Regime-adjusted prior
        prior_probs = REGIME_PRIORS.get(regime_label.value, REGIME_PRIORS["unknown"])
        log_L = [math.log(p + 1e-9) for p in prior_probs]

        # Step 2 — Weighted log-likelihood accumulation
        strategy_weights = {}
        contributions = []
        
        for sig in signals:
            # Query weight from Redis or default to base reliability
            weight_raw = await self.redis.get(f"strategy_weight:{sig.name}")
            w = float(weight_raw) if weight_raw else sig.base_reliability
            strategy_weights[sig.name] = w

            # Accumulate in log space
            log_L[0] += w * np.clip(sig.bull_logit, -5.0, 5.0)
            log_L[1] += w * np.clip(sig.bear_logit, -5.0, 5.0)
            log_L[2] += w * np.clip(sig.reversal_logit, -5.0, 5.0)
            log_L[3] += w * np.clip(sig.breakout_logit, -5.0, 5.0)

            # Store contribution score as weight * (sum of active logits)
            contrib_score = w * (abs(sig.bull_logit) + abs(sig.bear_logit) + abs(sig.reversal_logit) + abs(sig.breakout_logit))
            contributions.append((sig.name, float(contrib_score)))

        # Step 3 — Numerically stable softmax
        log_L_arr = np.array(log_L, dtype=float)
        log_L_arr -= log_L_arr.max()
        exp_L = np.exp(log_L_arr)
        posteriors = exp_L / exp_L.sum()

        # Step 4 — Cold-start calibration guard
        n_preds_raw = await self.redis.get("prediction_count")
        n_predictions = int(n_preds_raw) if n_preds_raw else 0
        
        if n_predictions < 100:
            shrinkage = max(0.0, 1.0 - n_predictions / 100.0)
            posteriors = posteriors * (1.0 - shrinkage) + 0.25 * shrinkage
        else:
            posteriors = self.calibrator.calibrate(posteriors)

        # Step 5 — Gold dual-feed adjustment
        gold_div = 0.0
        if symbol in ["XAUUSD_EXNESS", "XAUUSDT"]:
            gold_div_raw = await self.redis.get("gold:arbitrage:divergence")
            gold_div = float(gold_div_raw) if gold_div_raw else 0.0
            uncertainty_boost = min(gold_div * 15.0, 0.3)
            posteriors = posteriors * (1.0 - uncertainty_boost) + 0.25 * uncertainty_boost

        # Step 6 — Uncertainty quantification
        entropy = -np.sum(posteriors * np.log(posteriors + 1e-9))
        max_entropy = math.log(4.0)
        norm_entropy = float(entropy / max_entropy)

        dominant_idx = int(np.argmax(posteriors))
        dominant_prob = float(posteriors[dominant_idx])
        direction_map = {0: "long", 1: "short", 2: "reversal", 3: "breakout"}
        direction = direction_map[dominant_idx]

        # Apply microstructure manipulation penalty to probability
        confidence_multiplier = 1.00
        if manipulation_prob > 0.70:
            confidence_multiplier = 0.40
        elif manipulation_prob > 0.40:
            confidence_multiplier = 0.70
        dominant_prob *= confidence_multiplier

        # 90% Wilson score confidence interval
        n_eff = len(signals) * 10
        z = 1.645
        margin = z * math.sqrt(max(0.0, dominant_prob * (1.0 - dominant_prob) / n_eff))
        ci_lower = max(0.0, dominant_prob - margin)
        ci_upper = min(1.0, dominant_prob + margin)

        # Step 7 — Signal quality gate
        probability_pct = dominant_prob * 100.0
        if probability_pct < 55.0:
            signal_strength = "insufficient"
        elif probability_pct < 65.0:
            signal_strength = "low"
        elif probability_pct < 72.0:
            signal_strength = "medium"
        elif probability_pct < 80.0:
            signal_strength = "high"
        else:
            signal_strength = "very_high"

        # Step 8 — Expected move estimation
        atr_pct = (features.atr_14 / (features.close + 1e-9)) * 100.0
        multiplier_map = {"insufficient": 0.0, "low": 0.5, "medium": 0.8, "high": 1.0, "very_high": 1.3}
        expected_move_pct = atr_pct * multiplier_map[signal_strength]

        # Step 9 — Build reasoning string
        top_drivers = sorted(contributions, key=lambda x: x[1], reverse=True)[:3]
        drivers_str = ", ".join(f"{name} ({score:.2f})" for name, score in top_drivers)
        
        reasoning = (
            f"{direction.upper()} signal at {probability_pct:.1f}% confidence. "
            f"Regime: {regime_label.value}. "
            f"Top drivers: {drivers_str}. "
            f"Uncertainty (Entropy): {norm_entropy:.2f}."
        )
        if symbol.startswith("XAU"):
            reasoning += f" Gold arb divergence: {gold_div*100:.3f}%."

        # Average strategy weight for reliability rating
        reliability_rating = float(np.mean(list(strategy_weights.values())))

        return PredictionOutput(
            asset=symbol,
            direction=direction,
            probability=probability_pct,
            ci_lower=ci_lower * 100.0,
            ci_upper=ci_upper * 100.0,
            signal_strength=signal_strength,
            manipulation_probability=manipulation_prob,
            regime=regime_label.value,
            volatility_state=features.vol_ratio,  # Proxy for vol state
            expected_move_pct=float(expected_move_pct),
            reliability_rating=reliability_rating,
            strategy_contributions=dict(contributions),
            macro_context=macro_context,
            gold_arb_divergence=gold_div,
            reasoning=reasoning
        )
