from dataclasses import dataclass, asdict
from typing import Dict, Tuple
import orjson


@dataclass(slots=True)
class PredictionOutput:
    """
    Canonical output schema for Bayesian signal fusion results.
    """

    asset: str
    direction: str              # "long" | "short" | "reversal" | "breakout"
    probability: float          # 0 - 100
    ci_lower: float             # 90% Confidence Interval lower bound
    ci_upper: float             # 90% Confidence Interval upper bound
    signal_strength: str        # "insufficient" | "low" | "medium" | "high" | "very_high"
    manipulation_probability: float  # 0.0 – 1.0
    regime: str
    volatility_state: str       # "low" | "normal" | "high"
    expected_move_pct: float
    reliability_rating: float   # Mean strategy reliability weight
    strategy_contributions: Dict[str, float]
    macro_context: Dict[str, float]
    gold_arb_divergence: float  # 0.0 for BTC, real value for gold pairs
    reasoning: str

    def to_dict(self) -> dict:
        return asdict(self)

    def to_bytes(self) -> bytes:
        return orjson.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: dict) -> "PredictionOutput":
        return cls(
            asset=data["asset"],
            direction=data["direction"],
            probability=float(data["probability"]),
            ci_lower=float(data["ci_lower"]),
            ci_upper=float(data["ci_upper"]),
            signal_strength=data["signal_strength"],
            manipulation_probability=float(data["manipulation_probability"]),
            regime=data["regime"],
            volatility_state=data["volatility_state"],
            expected_move_pct=float(data["expected_move_pct"]),
            reliability_rating=float(data["reliability_rating"]),
            strategy_contributions={k: float(v) for k, v in data["strategy_contributions"].items()},
            macro_context={k: float(v) for k, v in data["macro_context"].items()},
            gold_arb_divergence=float(data["gold_arb_divergence"]),
            reasoning=data["reasoning"]
        )

    @classmethod
    def from_bytes(cls, raw: bytes) -> "PredictionOutput":
        return cls.from_dict(orjson.loads(raw))
