-- ============================================================
-- IPMI-OS 2.0 - Initial PostgreSQL Schema for Neon
-- ============================================================

-- Predictions table: stores every generated signal fusion output
CREATE TABLE IF NOT EXISTS predictions (
    id                       BIGSERIAL PRIMARY KEY,
    asset                    VARCHAR(32)      NOT NULL,
    direction                VARCHAR(16)      NOT NULL,
    probability              DOUBLE PRECISION NOT NULL,
    ci_lower                 DOUBLE PRECISION NOT NULL,
    ci_upper                 DOUBLE PRECISION NOT NULL,
    signal_strength          VARCHAR(16)      NOT NULL,
    manipulation_probability DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    regime                   VARCHAR(32)      NOT NULL,
    expected_move_pct        DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    reliability_rating       DOUBLE PRECISION NOT NULL DEFAULT 0.5,
    strategy_contributions   JSONB            NOT NULL DEFAULT '{}',
    macro_context            JSONB            NOT NULL DEFAULT '{}',
    gold_arb_divergence      DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    reasoning                TEXT             NOT NULL DEFAULT '',
    timestamp                TIMESTAMPTZ      NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_predictions_asset     ON predictions (asset);
CREATE INDEX IF NOT EXISTS idx_predictions_timestamp ON predictions (timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_predictions_direction ON predictions (direction);

-- Actual outcomes table: records trade results for calibration feedback
CREATE TABLE IF NOT EXISTS actual_outcomes (
    id               BIGSERIAL PRIMARY KEY,
    prediction_id    BIGINT           NOT NULL REFERENCES predictions(id) ON DELETE CASCADE,
    actual_direction VARCHAR(16)      NOT NULL,
    outcome          DOUBLE PRECISION NOT NULL,
    pnl_pct          DOUBLE PRECISION,
    recorded_at      TIMESTAMPTZ      NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_outcome_prediction UNIQUE (prediction_id)
);

CREATE INDEX IF NOT EXISTS idx_outcomes_prediction_id ON actual_outcomes (prediction_id);
CREATE INDEX IF NOT EXISTS idx_outcomes_recorded_at   ON actual_outcomes (recorded_at DESC);

-- Strategy weights table: tracks adaptive strategy reliability history
CREATE TABLE IF NOT EXISTS strategy_weights (
    id          BIGSERIAL PRIMARY KEY,
    strategy    VARCHAR(32)      NOT NULL,
    weight      DOUBLE PRECISION NOT NULL,
    recorded_at TIMESTAMPTZ      NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_strategy_weights_strategy    ON strategy_weights (strategy);
CREATE INDEX IF NOT EXISTS idx_strategy_weights_recorded_at ON strategy_weights (recorded_at DESC);

-- Anomalies table: logs all detected microstructure and feed anomalies
CREATE TABLE IF NOT EXISTS anomaly_log (
    id             BIGSERIAL PRIMARY KEY,
    symbol         VARCHAR(32)      NOT NULL,
    anomaly_type   VARCHAR(64)      NOT NULL,
    severity       DOUBLE PRECISION NOT NULL,
    description    TEXT             NOT NULL,
    raw_value      DOUBLE PRECISION NOT NULL,
    expected_min   DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    expected_max   DOUBLE PRECISION NOT NULL DEFAULT 1.0,
    timestamp_ms   BIGINT           NOT NULL,
    logged_at      TIMESTAMPTZ      NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_anomaly_log_symbol    ON anomaly_log (symbol);
CREATE INDEX IF NOT EXISTS idx_anomaly_log_type      ON anomaly_log (anomaly_type);
CREATE INDEX IF NOT EXISTS idx_anomaly_log_logged_at ON anomaly_log (logged_at DESC);
