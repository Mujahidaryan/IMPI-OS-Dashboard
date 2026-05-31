import json
import logging
import asyncio
import psycopg2
from psycopg2.extras import RealDictCursor
from typing import List, Dict, Any, Optional, Tuple

from config.settings import get_settings
from services.fusion.output_schema import PredictionOutput

logger = logging.getLogger("PredictionStore")


class PredictionStore:
    """
    Saves predictions, outcomes, and strategy weights to the Neon PostgreSQL database
    using psycopg2 database connectors executed inside thread pools to prevent blocking.
    """

    def __init__(self):
        self.settings = get_settings()

    def _get_connection(self):
        return psycopg2.connect(self.settings.DATABASE_URL, cursor_factory=RealDictCursor)

    async def save_prediction(self, pred: PredictionOutput) -> Optional[int]:
        """Saves a prediction to the database and returns the generated prediction ID."""
        def _execute():
            conn = self._get_connection()
            cur = conn.cursor()
            try:
                query = """
                    INSERT INTO predictions (
                        asset, direction, probability, ci_lower, ci_upper, 
                        signal_strength, manipulation_probability, regime, 
                        expected_move_pct, reliability_rating, strategy_contributions, 
                        macro_context, gold_arb_divergence, reasoning
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id;
                """
                cur.execute(query, (
                    pred.asset,
                    pred.direction,
                    pred.probability,
                    pred.ci_lower,
                    pred.ci_upper,
                    pred.signal_strength,
                    pred.manipulation_probability,
                    pred.regime,
                    pred.expected_move_pct,
                    pred.reliability_rating,
                    json.dumps(pred.strategy_contributions),
                    json.dumps(pred.macro_context),
                    pred.gold_arb_divergence,
                    pred.reasoning
                ))
                row = cur.fetchone()
                conn.commit()
                return int(row["id"]) if row else None
            except Exception as e:
                logger.error("Database save_prediction failed: %s", str(e))
                conn.rollback()
                return None
            finally:
                cur.close()
                conn.close()

        try:
            return await asyncio.to_thread(_execute)
        except Exception as e:
            logger.error("Async execution of save_prediction failed: %s", str(e))
            return None

    async def save_outcome(self, prediction_id: int, actual_direction: str, outcome: float):
        """Saves actual trade outcome relative to prediction."""
        def _execute():
            conn = self._get_connection()
            cur = conn.cursor()
            try:
                query = """
                    INSERT INTO actual_outcomes (prediction_id, actual_direction, outcome)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (prediction_id) DO UPDATE 
                    SET actual_direction = EXCLUDED.actual_direction, outcome = EXCLUDED.outcome;
                """
                cur.execute(query, (prediction_id, actual_direction, outcome))
                conn.commit()
            except Exception as e:
                logger.error("Database save_outcome failed: %s", str(e))
                conn.rollback()
            finally:
                cur.close()
                conn.close()

        try:
            await asyncio.to_thread(_execute)
        except Exception as e:
            logger.error("Async execution of save_outcome failed: %s", str(e))

    async def get_prediction_count(self) -> int:
        """Counts total predictions generated in predictions table."""
        def _execute():
            conn = self._get_connection()
            cur = conn.cursor()
            try:
                cur.execute("SELECT COUNT(*) as count FROM predictions;")
                row = cur.fetchone()
                return int(row["count"]) if row else 0
            except Exception as e:
                logger.error("Database get_prediction_count failed: %s", str(e))
                return 0
            finally:
                cur.close()
                conn.close()

        try:
            return await asyncio.to_thread(_execute)
        except Exception as e:
            logger.error("Async execution of get_prediction_count failed: %s", str(e))
            return 0

    async def get_historical_data_for_calibration(self) -> Tuple[List[float], List[float]]:
        """Retrieves historical prediction probabilities and actual outcomes for calibrator retraining."""
        def _execute():
            conn = self._get_connection()
            cur = conn.cursor()
            try:
                query = """
                    SELECT p.probability / 100.0 as prob, o.outcome
                    FROM predictions p
                    JOIN actual_outcomes o ON p.id = o.prediction_id
                    ORDER BY p.timestamp ASC;
                """
                cur.execute(query)
                rows = cur.fetchall()
                probs = [float(r["prob"]) for r in rows]
                outcomes = [float(r["outcome"]) for r in rows]
                return probs, outcomes
            except Exception as e:
                logger.error("Database get_historical_data_for_calibration failed: %s", str(e))
                return [], []
            finally:
                cur.close()
                conn.close()

        try:
            return await asyncio.to_thread(_execute)
        except Exception as e:
            logger.error("Async execution of get_historical_data_for_calibration failed: %s", str(e))
            return [], []

    async def save_strategy_weights(self, weights: Dict[str, float]):
        """Persists strategy weights to the strategy_weights table."""
        def _execute():
            conn = self._get_connection()
            cur = conn.cursor()
            try:
                for strategy, weight in weights.items():
                    cur.execute(
                        "INSERT INTO strategy_weights (strategy, weight) VALUES (%s, %s)",
                        (strategy, weight)
                    )
                conn.commit()
            except Exception as e:
                logger.error("Database save_strategy_weights failed: %s", str(e))
                conn.rollback()
            finally:
                cur.close()
                conn.close()

        try:
            await asyncio.to_thread(_execute)
        except Exception as e:
            logger.error("Async execution of save_strategy_weights failed: %s", str(e))

    async def get_latest_strategy_weights(self) -> Dict[str, float]:
        """Retrieves the latest weight for each strategy."""
        def _execute():
            conn = self._get_connection()
            cur = conn.cursor()
            try:
                query = """
                    SELECT DISTINCT ON (strategy) strategy, weight
                    FROM strategy_weights
                    ORDER BY strategy, recorded_at DESC;
                """
                cur.execute(query)
                rows = cur.fetchall()
                return {r["strategy"]: float(r["weight"]) for r in rows}
            except Exception as e:
                logger.error("Database get_latest_strategy_weights failed: %s", str(e))
                return {}
            finally:
                cur.close()
                conn.close()

        try:
            return await asyncio.to_thread(_execute)
        except Exception as e:
            logger.error("Async execution of get_latest_strategy_weights failed: %s", str(e))
            return {}

    async def get_recent_predictions(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Retrieves recent predictions joined with their outcome if available."""
        def _execute():
            conn = self._get_connection()
            cur = conn.cursor()
            try:
                query = """
                    SELECT p.*, o.actual_direction, o.outcome, o.pnl_pct, o.recorded_at as outcome_recorded_at
                    FROM predictions p
                    LEFT JOIN actual_outcomes o ON p.id = o.prediction_id
                    ORDER BY p.timestamp DESC
                    LIMIT %s;
                """
                cur.execute(query, (limit,))
                rows = cur.fetchall()
                results = []
                for r in rows:
                    item = dict(r)
                    if item.get("timestamp"):
                        item["timestamp"] = item["timestamp"].isoformat()
                    if item.get("outcome_recorded_at"):
                        item["outcome_recorded_at"] = item["outcome_recorded_at"].isoformat()
                    results.append(item)
                return results
            except Exception as e:
                logger.error("Database get_recent_predictions failed: %s", str(e))
                return []
            finally:
                cur.close()
                conn.close()

        try:
            return await asyncio.to_thread(_execute)
        except Exception as e:
            logger.error("Async execution of get_recent_predictions failed: %s", str(e))
            return []
