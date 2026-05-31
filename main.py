import asyncio
import json
import logging
import sys
import time
from typing import Dict, Any, List
import uvicorn
import redis.asyncio as aioredis

from config.settings import get_settings, RegimeLabel
from services.ingestor.clock_sync import ClockSynchronizer
from services.ingestor.binance_ws import BinanceWebSocketClient
from services.ingestor.exness_mt5 import ExnessMT5Client
from services.ingestor.gold_arbitrage import GoldArbitrageMonitor
from services.features.candle_aggregator import CandleAggregator
from services.features.feature_engine import FeatureEngine
from services.regime.hmm_engine import HMMRegimeDetector
from services.microstructure.manipulation import ManipulationDetector
from services.microstructure.liquidity import LiquidityMonitor
from services.microstructure.order_flow import MicrostructureOrderFlow
from services.macro.data_fetcher import MacroDataFetcher
from services.macro.asset_context import AssetMacroContextBuilder
from services.fusion.calibration import ProbabilityCalibrator
from services.fusion.bayesian_engine import BayesianFusionEngine
from services.learning.prediction_store import PredictionStore
from services.learning.weight_updater import StrategyWeightUpdater
from services.learning.calibration_tracker import CalibrationTracker
from services.api.ws_broadcaster import broadcaster

# Strategies imports
from services.ingestor.models import Tick
from services.strategies.trend import TrendStrategy
from services.strategies.mean_reversion import MeanReversionStrategy
from services.strategies.momentum import MomentumStrategy
from services.strategies.volatility import VolatilityStrategy
from services.strategies.order_flow import OrderFlowStrategy
from services.strategies.sentiment import SentimentStrategy
from services.strategies.macro_news import MacroNewsStrategy
from services.strategies.intermarket import IntermarketStrategy

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("IPMI_OS_Main")


class IPMIOSSystem:
    def __init__(self):
        self.settings = get_settings()
        self.redis: aioredis.Redis | None = None
        self.clock_sync: ClockSynchronizer | None = None

        # Clients & Ingestors
        self.binance_ws: BinanceWebSocketClient | None = None
        self.exness_mt5: ExnessMT5Client | None = None
        self.gold_arb: GoldArbitrageMonitor | None = None

        # Pipelines & Processors
        self.candle_aggregator: CandleAggregator | None = None
        self.feature_engine: FeatureEngine | None = None
        self.hmm_detector: HMMRegimeDetector | None = None
        self.manipulation_detector: ManipulationDetector | None = None

        # Context Builders & Monitors
        self.macro_fetcher: MacroDataFetcher | None = None
        self.liquidity_monitor: LiquidityMonitor | None = None
        self.micro_order_flow: MicrostructureOrderFlow | None = None
        self.context_builder: AssetMacroContextBuilder | None = None

        # Fusion & Calibration
        self.calibrator: ProbabilityCalibrator | None = None
        self.fusion_engine: BayesianFusionEngine | None = None

        # Database & Learning
        self.db: PredictionStore | None = None
        self.weight_updater: StrategyWeightUpdater | None = None
        self.calibration_tracker: CalibrationTracker | None = None

        # Strategies
        self.strategies: Dict[str, Any] = {}

        self._running = False
        self._tasks: List[asyncio.Task] = []

    async def start(self):
        self._running = True
        logger.info("Initializing IPMI-OS 2.0 system...")

        # 1. Initialize Redis
        self.redis = aioredis.from_url(self.settings.REDIS_URL, decode_responses=False)

        # 2. Clock Synchronization
        self.clock_sync = ClockSynchronizer()
        await self.clock_sync.sync()

        # 3. Initialize Ingestors
        self.exness_mt5 = ExnessMT5Client(self.redis)
        self.binance_ws = BinanceWebSocketClient(self.clock_sync, self.redis)
        self.gold_arb = GoldArbitrageMonitor(self.redis)

        # Start Ingestors
        await self.exness_mt5.start()
        await self.binance_ws.start()
        await self.gold_arb.start()

        # 4. Initialize Pipelines
        self.candle_aggregator = CandleAggregator(self.redis, mt5_client=self.exness_mt5)
        await self.candle_aggregator.start()

        self.feature_engine = FeatureEngine(self.candle_aggregator)
        self.hmm_detector = HMMRegimeDetector(self.candle_aggregator, self.redis)
        await self.hmm_detector.start()

        self.manipulation_detector = ManipulationDetector(self.candle_aggregator, self.redis)
        self.liquidity_monitor = LiquidityMonitor(self.redis)
        self.micro_order_flow = MicrostructureOrderFlow(self.redis)

        self.macro_fetcher = MacroDataFetcher(self.redis)
        self.context_builder = AssetMacroContextBuilder(
            self.macro_fetcher,
            self.liquidity_monitor,
            self.micro_order_flow
        )

        # 5. Initialize Fusion & Learning
        self.calibrator = ProbabilityCalibrator()
        self.db = PredictionStore()

        # Warm start calibration data
        probs, outcomes = await self.db.get_historical_data_for_calibration()
        self.calibrator.train(probs, outcomes)

        self.fusion_engine = BayesianFusionEngine(self.redis, self.calibrator)
        self.weight_updater = StrategyWeightUpdater(self.db, self.redis)
        await self.weight_updater.initialize()

        self.calibration_tracker = CalibrationTracker(self.db, self.calibrator, self.redis)
        await self.calibration_tracker.calculate_metrics()

        # 6. Initialize Strategies
        self.strategies = {
            "trend": TrendStrategy(),
            "mean_reversion": MeanReversionStrategy(),
            "momentum": MomentumStrategy(self.candle_aggregator),
            "volatility": VolatilityStrategy(),
            "order_flow": OrderFlowStrategy(self.candle_aggregator, self.redis),
            "sentiment": SentimentStrategy(self.redis),
            "macro_news": MacroNewsStrategy(),
            "intermarket": IntermarketStrategy(self.redis),
        }

        # Start strategies that run background polling/news feeds
        await self.strategies["sentiment"].start()
        await self.strategies["macro_news"].start()
        await self.strategies["intermarket"].start()

        # 7. Start Main Processing Listeners & Workers
        self._tasks.append(asyncio.create_task(self._listen_confirmed_candles()))
        self._tasks.append(asyncio.create_task(self._outcome_resolution_loop()))

        # 8. Start Uvicorn API Server
        config = uvicorn.Config(
            "services.api.server:app",
            host="0.0.0.0",
            port=self.settings.API_PORT,
            log_level="warning"
        )
        server = uvicorn.Server(config)
        self._tasks.append(asyncio.create_task(server.serve()))

        logger.info("IPMI-OS 2.0 System fully started and operational.")

    async def stop(self):
        self._running = False
        logger.info("Stopping IPMI-OS 2.0 system...")

        # Cancel main tasks
        for task in self._tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        # Stop strategies
        if "sentiment" in self.strategies:
         await self.strategies["sentiment"].stop()
        await self.strategies["macro_news"].stop()
        await self.strategies["intermarket"].stop()

        # Stop HMM regime detector & Candle aggregator
        await self.hmm_detector.stop()
        await self.candle_aggregator.stop()

        # Stop ingestors
        await self.exness_mt5.stop()
        await self.binance_ws.stop()
        await self.gold_arb.stop()

        # Close Redis
        if self.redis:
            await self.redis.close()

        logger.info("IPMI-OS 2.0 system cleanly stopped.")

    async def _listen_confirmed_candles(self):
        """Listens to confirmed candle closures to execute Bayesian signal fusion."""
        pubsub = self.redis.pubsub()
        await pubsub.subscribe(
            "channel:candles:confirmed:XAUUSD_EXNESS",
            "channel:candles:confirmed:XAUUSDT",
            "channel:candles:confirmed:BTCUSDT"
        )
        logger.info("Listening for confirmed closed candles...")

        while self._running:
            try:
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if not message:
                    continue

                channel = message["channel"].decode("utf-8")
                symbol = channel.split(":")[-1]

                # Check features and run prediction
                # Timeframe defaults to '1m' since that's the primary stream kline interval
                await self._execute_prediction_flow(symbol, "1m")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in confirmed candle listener: %s", str(e), exc_info=True)
                await asyncio.sleep(1)

        await pubsub.unsubscribe()

    async def _execute_prediction_flow(self, symbol: str, timeframe: str):
        """Builds features, queries HMM regime & microstructure context, and runs Bayesian Fusion."""
        try:
            logger.info("New candle closed for %s. Triggering signal fusion...", symbol)

            # 1. Feature Engineering
            features = await self.feature_engine.build_feature_vector(symbol, timeframe)
            if not features:
                logger.debug("Failed to build feature vector for %s (warmup in progress).", symbol)
                return

            # 2. HMM Regime Decoding
            regime_info = await self.hmm_detector.detect_regime(symbol)
            regime_label = regime_info["label"]

            # Broadcast updated regime
            await broadcaster.broadcast_regime(symbol, regime_info)

            # 3. Microstructure Manipulation probability
            manipulation_prob = await self.manipulation_detector.calculate_manipulation_score(symbol, timeframe)

            # 4. Macro and Micro Context compiles
            macro_ctx = await self.context_builder.get_context_for_asset(symbol)

            # 5. Execute all strategies to generate signals
            strategy_signals = []
            strategy_directions = {}
            for name, strategy in self.strategies.items():
                try:
                    sig = await strategy.generate_signal(symbol, features)
                    strategy_signals.append(sig)

                    # Store predicted directions for outcome monitoring
                    # Determine dominant direction
                    logits = [sig.bull_logit, sig.bear_logit, sig.reversal_logit, sig.breakout_logit]
                    dirs = ["long", "short", "reversal", "breakout"]
                    strategy_directions[name] = {"direction": dirs[logits.index(max(logits))]}
                except Exception as e:
                    logger.error("Strategy %s generate_signal failed: %s", name, str(e))

            # 6. Bayesian Signal Fusion
            prediction = await self.fusion_engine.fuse_signals(
                symbol=symbol,
                signals=strategy_signals,
                regime_label=regime_label,
                features=features,
                manipulation_prob=manipulation_prob,
                macro_context=macro_ctx
            )

            # 7. Save prediction output to Neon PostgreSQL
            pred_id = await self.db.save_prediction(prediction)
            if pred_id:
                # Cache prediction details in Redis to verify outcomes
                await self.redis.set(f"prediction_entry:{pred_id}", str(features.close), ex=3600)
                await self.redis.set(f"prediction_strats:{pred_id}", json.dumps(strategy_directions), ex=3600)
                logger.info("Saved prediction ID %d for %s in database.", pred_id, symbol)

            # 8. Cache latest PredictionOutput in Redis
            prediction_dict = prediction.to_dict()
            prediction_dict["timestamp"] = int(time.time() * 1000)
            await self.redis.set(f"latest_signal:{symbol}", prediction.to_bytes())

            # 9. Broadcast to Connected Websocket clients
            await broadcaster.broadcast_prediction(prediction_dict)

        except Exception as e:
            logger.error("Error in prediction flow for %s: %s", symbol, str(e), exc_info=True)

    async def _outcome_resolution_loop(self):
        """Periodically queries pending predictions and evaluates their accuracy using real prices."""
        logger.info("Outcome resolution background loop started.")
        while self._running:
            try:
                await asyncio.sleep(10)  # Check outcomes every 10 seconds

                # Fetch unresolved predictions from database
                # Resolve predictions older than 1 minute
                conn = self.db._get_connection()
                cur = conn.cursor()
                try:
                    query = """
                        SELECT id, asset, direction, timestamp
                        FROM predictions
                        WHERE id NOT IN (SELECT prediction_id FROM actual_outcomes)
                          AND timestamp < NOW() - INTERVAL '1 minute'
                        ORDER BY timestamp ASC
                        LIMIT 50;
                    """
                    cur.execute(query)
                    pending = cur.fetchall()
                except Exception as e:
                    logger.error("Failed to query pending outcomes: %s", str(e))
                    pending = []
                finally:
                    cur.close()
                    conn.close()

                for r in pending:
                    pred_id = int(r["id"])
                    symbol = r["asset"]
                    predicted_dir = r["direction"]

                    # Fetch exit price (latest price from Redis tick cache)
                    tick_bytes = await self.redis.get(f"latest_tick:{symbol}")
                    if not tick_bytes:
                        continue

                    tick = Tick.from_bytes(tick_bytes)
                    exit_price = tick.last

                    # Fetch entry price from Redis cache
                    entry_raw = await self.redis.get(f"prediction_entry:{pred_id}")
                    if not entry_raw:
                        # Fallback: cannot calculate price outcome without entry price
                        continue

                    entry_price = float(entry_raw)

                    if entry_price <= 0.0:
                        continue

                    price_diff_pct = (exit_price - entry_price) / entry_price

                    # Determine actual direction
                    # Reversal and breakout outcomes depend on volatility movement
                    actual_dir = "flat"
                    if price_diff_pct > 0.0001:
                        actual_dir = "long"
                    elif price_diff_pct < -0.0001:
                        actual_dir = "short"

                    # Calculate outcome accuracy (binary classification score)
                    outcome = 0.0
                    if predicted_dir == "long" and actual_dir == "long":
                        outcome = 1.0
                    elif predicted_dir == "short" and actual_dir == "short":
                        outcome = 1.0
                    elif predicted_dir in ["reversal", "breakout"]:
                        # For volatility directions, outcome is based on absolute movement threshold
                        if abs(price_diff_pct) > 0.001:
                            outcome = 1.0

                    # Save outcome to database
                    await self.db.save_outcome(pred_id, actual_dir, outcome)
                    logger.info(
                        "Resolved prediction %d (%s) outcome. Predicted: %s, Actual: %s, Price change: %.3f%%. Score: %.1f",
                        pred_id, symbol, predicted_dir, actual_dir, price_diff_pct * 100.0, outcome
                    )

                    # Update strategy weights
                    strats_raw = await self.redis.get(f"prediction_strats:{pred_id}")
                    if strats_raw:
                        strategy_signals = json.loads(strats_raw)
                        await self.weight_updater.observe_outcome(pred_id, actual_dir, strategy_signals)

                    # Calculate updated calibration metrics
                    await self.calibration_tracker.calculate_metrics()

                    # Clean up Redis caches
                    await self.redis.delete(f"prediction_entry:{pred_id}")
                    await self.redis.delete(f"prediction_strats:{pred_id}")

            except Exception as e:
                logger.error("Error in outcome resolution loop: %s", str(e), exc_info=True)


async def main():
    system = IPMIOSSystem()
    try:
        await system.start()
        # Keep running until cancelled
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        await system.stop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("System interrupted by user.")
