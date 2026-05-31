"""
Seed script: inserts 100 synthetic predictions + outcomes so that the
isotonic calibration model has data to warm-start on first launch.

Run once after applying 001_initial.sql:
    python tools/db/seed_test.py
"""
import random
import math
import json
import sys
import os

# Allow running from repo root
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import psycopg2
from config.settings import get_settings

random.seed(42)


def generate_synthetic_prediction(asset: str):
    direction = random.choice(["long", "short", "reversal", "breakout"])
    probability = random.uniform(52.0, 90.0)
    regime = random.choice(["trending_up", "trending_down", "ranging", "expansion"])
    ci_half = random.uniform(2.0, 8.0)
    return {
        "asset": asset,
        "direction": direction,
        "probability": probability,
        "ci_lower": max(50.0, probability - ci_half),
        "ci_upper": min(100.0, probability + ci_half),
        "signal_strength": "medium" if probability < 72 else "high",
        "manipulation_probability": random.uniform(0.0, 0.25),
        "regime": regime,
        "expected_move_pct": random.uniform(0.1, 0.8),
        "reliability_rating": random.uniform(0.52, 0.62),
        "strategy_contributions": {
            "trend": random.uniform(0.0, 1.0),
            "mean_reversion": random.uniform(0.0, 1.0),
            "momentum": random.uniform(0.0, 1.0),
            "volatility": random.uniform(0.0, 1.0),
            "order_flow": random.uniform(0.0, 1.0),
            "sentiment": random.uniform(0.0, 1.0),
            "macro_news": random.uniform(0.0, 1.0),
            "intermarket": random.uniform(0.0, 1.0),
        },
        "macro_context": {
            "dxy": 104.0, "us10y": 4.5, "vix": 18.0, "usdt_dominance": 6.5
        },
        "gold_arb_divergence": random.uniform(0.0, 0.003),
        "reasoning": f"Synthetic seed prediction for calibration warm-start.",
    }


def generate_outcome(pred_row):
    """
    Simulates a realistic outcome: higher probability predictions should win more often,
    creating a calibration curve for isotonic regression to learn from.
    """
    prob_norm = pred_row["probability"] / 100.0
    # Probability of being correct ~ the predicted probability (slightly noisy)
    noise = random.uniform(-0.10, 0.10)
    p_correct = max(0.05, min(0.95, prob_norm + noise))
    outcome = 1.0 if random.random() < p_correct else 0.0
    # Simulate PnL: winner gets +1% to +2%, loser gets -0.5% to -1.5%
    if outcome == 1.0:
        pnl_pct = random.uniform(0.01, 0.02)
    else:
        pnl_pct = random.uniform(-0.015, -0.005)
    actual_direction = pred_row["direction"] if outcome == 1.0 else random.choice(["long", "short", "reversal", "breakout"])
    return actual_direction, outcome, pnl_pct


def main():
    settings = get_settings()
    conn = psycopg2.connect(settings.DATABASE_URL)
    cur = conn.cursor()

    assets = ["XAUUSD_EXNESS", "XAUUSDT", "BTCUSDT"]
    insert_pred = """
        INSERT INTO predictions (
            asset, direction, probability, ci_lower, ci_upper,
            signal_strength, manipulation_probability, regime,
            expected_move_pct, reliability_rating, strategy_contributions,
            macro_context, gold_arb_divergence, reasoning
        ) VALUES (
            %(asset)s, %(direction)s, %(probability)s, %(ci_lower)s, %(ci_upper)s,
            %(signal_strength)s, %(manipulation_probability)s, %(regime)s,
            %(expected_move_pct)s, %(reliability_rating)s, %(strategy_contributions)s,
            %(macro_context)s, %(gold_arb_divergence)s, %(reasoning)s
        ) RETURNING id;
    """
    insert_outcome = """
        INSERT INTO actual_outcomes (prediction_id, actual_direction, outcome, pnl_pct)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (prediction_id) DO NOTHING;
    """

    count = 0
    for _ in range(100):
        asset = random.choice(assets)
        pred = generate_synthetic_prediction(asset)

        # Serialize JSONB fields
        pred["strategy_contributions"] = json.dumps(pred["strategy_contributions"])
        pred["macro_context"] = json.dumps(pred["macro_context"])

        cur.execute(insert_pred, pred)
        row = cur.fetchone()
        if row:
            pred_id = row[0]
            actual_dir, outcome, pnl_pct = generate_outcome(pred)
            cur.execute(insert_outcome, (pred_id, actual_dir, outcome, pnl_pct))
            count += 1

    conn.commit()
    cur.close()
    conn.close()
    print(f"Seeded {count} synthetic predictions + outcomes into the database.")


if __name__ == "__main__":
    main()
