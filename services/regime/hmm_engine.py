import asyncio
import logging
import pickle
import numpy as np
import pandas as pd
import redis.asyncio as aioredis
from hmmlearn.hmm import GaussianHMM
from typing import Optional, Tuple, List, Dict

from config.settings import RegimeLabel
from services.features.candle_aggregator import CandleAggregator
from services.features.technical import calculate_tr, wilder_smooth

logger = logging.getLogger("HMMEngine")


class HMMRegimeDetector:
    """
    Online regime classifier fitting a Gaussian Hidden Markov Model (HMM)
    on multi-dimensional returns, realized volatility, and volume indicators.
    Also executes CUSUM structural break calculations.
    """

    def __init__(self, aggregator: CandleAggregator, redis_client: aioredis.Redis):
        self.aggregator = aggregator
        self.redis = redis_client
        self.model: Optional[GaussianHMM] = None
        self._running = False
        self._retrain_tasks: List[asyncio.Task] = []

        # Track number of candles since last training to trigger re-fit
        self._candle_counters: Dict[str, int] = {}

    async def start(self):
        self._running = True
        # Do initial training on startup for each symbol
        for symbol in ["XAUUSD_EXNESS", "XAUUSDT", "BTCUSDT"]:
            self._candle_counters[symbol] = 0
            await self.retrain_model(symbol)

        # Start background listener for new candles to count towards retraining
        self._retrain_tasks.append(asyncio.create_task(self._listen_for_confirmed_candles()))
        logger.info("HMM Regime Detector started.")

    async def stop(self):
        self._running = False
        for t in self._retrain_tasks:
            t.cancel()
            try:
                await t
            except asyncio.CancelledError:
                pass
        logger.info("HMM Regime Detector stopped.")

    async def _listen_for_confirmed_candles(self):
        pubsub = self.redis.pubsub()
        await pubsub.subscribe(
            "channel:candles:confirmed:XAUUSD_EXNESS",
            "channel:candles:confirmed:XAUUSDT",
            "channel:candles:confirmed:BTCUSDT"
        )

        while self._running:
            try:
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if not message:
                    continue

                # We received a confirmed candle. Parse and increment counter
                channel = message["channel"].decode("utf-8")
                symbol = channel.split(":")[-1]

                self._candle_counters[symbol] = self._candle_counters.get(symbol, 0) + 1
                if self._candle_counters[symbol] >= 100:
                    self._candle_counters[symbol] = 0
                    logger.info("100 new candles confirmed for %s. Triggering HMM re-training.", symbol)
                    asyncio.create_task(self.retrain_model(symbol))
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in HMM candle listener: %s", str(e))
                await asyncio.sleep(1)

        await pubsub.unsubscribe()

    async def _build_feature_matrix(self, symbol: str) -> Optional[Tuple[np.ndarray, np.ndarray, np.ndarray]]:
        """Retrieve recent 1h candles and build feature matrix X for HMM fitting."""
        candles = await self.aggregator.get_candles(symbol, "1h", count=500)
        if len(candles) < 100:
            return None

        closes = np.array([c.close for c in candles], dtype=float)
        volumes = np.array([c.volume for c in candles], dtype=float)
        highs = np.array([c.high for c in candles], dtype=float)
        lows = np.array([c.low for c in candles], dtype=float)

        log_returns = np.log(closes[1:] / closes[:-1])
        realized_vol = pd.Series(log_returns).rolling(10).std().values

        vol_ma = pd.Series(volumes).rolling(20).mean().values
        volume_ratio = volumes[1:] / (vol_ma[1:] + 1e-9)

        tr = calculate_tr(highs, lows, closes)
        atrs = wilder_smooth(tr, 14)

        close_ma = pd.Series(closes).rolling(5).mean().values
        abs_momentum = np.abs(closes[1:] - close_ma[1:]) / (atrs[1:] + 1e-9)

        # Align lengths (first 9 elements are NaN in rolling variables)
        X = np.column_stack([
            log_returns[9:],
            realized_vol[9:],
            volume_ratio[9:],
            abs_momentum[9:]
        ])

        # Filter NaN rows
        valid_mask = ~np.isnan(X).any(axis=1)
        X_clean = X[valid_mask]

        return X_clean, log_returns, realized_vol

    async def retrain_model(self, symbol: str):
        """Fits GaussianHMM on the symbol's features and persists parameters to Redis."""
        try:
            res = await self._build_feature_matrix(symbol)
            if res is None:
                logger.warning("Not enough data to train HMM for %s.", symbol)
                return

            X, _, _ = res
            model = GaussianHMM(n_components=3, covariance_type="full", n_iter=200, random_state=42)

            # Wrap training in thread pool to prevent blocking main event loop
            await asyncio.to_thread(model.fit, X)

            # Save parameters to Redis
            params = {
                "transmat": model.transmat_.tolist(),
                "means": model.means_.tolist(),
                "covars": model.covars_.tolist(),
                "symbol": symbol
            }
            await self.redis.set(f"hmm:model:{symbol}", pickle.dumps(model), ex=2592000)  # 30-day TTL
            await self.redis.set(f"hmm:params:{symbol}", json.dumps(params), ex=2592000)
            logger.info("HMM retrained successfully for %s.", symbol)
        except Exception as e:
            logger.error("HMM training failed for %s: %s", symbol, str(e), exc_info=True)

    async def detect_regime(self, symbol: str) -> dict:
        """Decodes the current regime state and runs CUSUM structural break checks."""
        # Retrieve model from Redis
        model_bytes = await self.redis.get(f"hmm:model:{symbol}")
        if not model_bytes:
            # Return fallback regime state
            return {
                "label": RegimeLabel.UNKNOWN,
                "confidence": 1.0,
                "transition_matrix": [[0.33, 0.33, 0.34]] * 3,
                "persistence_probability": 0.33,
                "bars_in_current_regime": 1,
                "structural_break": False
            }

        model = pickle.loads(model_bytes)
        res = await self._build_feature_matrix(symbol)
        if res is None:
            return {
                "label": RegimeLabel.UNKNOWN,
                "confidence": 1.0,
                "transition_matrix": model.transmat_.tolist(),
                "persistence_probability": 0.33,
                "bars_in_current_regime": 1,
                "structural_break": False
            }

        X, log_returns, realized_vol = res

        # Decode state sequence using Viterbi algorithm
        hidden_states = model.predict(X)
        current_state = int(hidden_states[-1])

        # Calculate state probabilities
        posteriors = model.predict_proba(X)
        confidence = float(posteriors[-1][current_state])

        # Structural break check (CUSUM)
        last_vol = realized_vol[-1]
        threshold = 0.5 * last_vol
        cusum_limit = 4.0 * last_vol
        cusum_pos = 0.0
        cusum_neg = 0.0
        for r in log_returns[-50:]:
            cusum_pos = max(0.0, cusum_pos + r - threshold)
            cusum_neg = min(0.0, cusum_neg + r + threshold)
        break_detected = bool(cusum_pos > cusum_limit or abs(cusum_neg) > cusum_limit)

        # Map state number to RegimeLabel dynamically
        # Sort states by volatility first (from covars), then mean log-returns
        # State with highest covariance volume -> expansion or panic
        # State with lowest covariance -> ranging
        cov_traces = [np.trace(model.covars_[i]) for i in range(3)]
        sorted_by_vol = np.argsort(cov_traces)

        low_vol_state = sorted_by_vol[0]
        med_vol_state = sorted_by_vol[1]
        high_vol_state = sorted_by_vol[2]

        means_returns = model.means_[:, 0]

        regime_label = RegimeLabel.UNKNOWN
        if current_state == low_vol_state:
            regime_label = RegimeLabel.RANGING
        elif current_state == med_vol_state:
            if means_returns[med_vol_state] > 0.0001:
                regime_label = RegimeLabel.TRENDING_UP
            elif means_returns[med_vol_state] < -0.0001:
                regime_label = RegimeLabel.TRENDING_DOWN
            else:
                regime_label = RegimeLabel.CONTRACTION
        elif current_state == high_vol_state:
            if means_returns[high_vol_state] < -0.001 or break_detected:
                regime_label = RegimeLabel.PANIC
            else:
                regime_label = RegimeLabel.EXPANSION

        # Count consecutive bars in current regime
        bars_in_regime = 0
        for s in reversed(hidden_states):
            if s == current_state:
                bars_in_regime += 1
            else:
                break

        persistence = float(model.transmat_[current_state][current_state])

        return {
            "label": regime_label,
            "confidence": confidence,
            "transition_matrix": model.transmat_.tolist(),
            "persistence_probability": persistence,
            "bars_in_current_regime": bars_in_regime,
            "structural_break": break_detected
        }
