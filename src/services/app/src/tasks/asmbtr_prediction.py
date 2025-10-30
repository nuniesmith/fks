"""
ASMBTR prediction task for Celery Beat.

This task:
1. Fetches latest market ticks from fks_data or CCXT
2. Updates StateEncoder for active symbols
3. Generates predictions via PredictionTable
4. Stores results in Redis cache

Execution: Every 60 seconds via Celery Beat
"""

import json
import logging
import os
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

import redis
from celery import shared_task

logger = logging.getLogger(__name__)

# Import ASMBTR components
try:
    from ..strategies.asmbtr.encoder import StateEncoder
    from ..strategies.asmbtr.predictor import PredictionTable
    from ..strategies.asmbtr.strategy import ASMBTRStrategy
except ImportError:
    logger.error("Failed to import ASMBTR modules. Ensure strategies package exists.")
    raise


class ASMBTRPredictionService:
    """Service for running ASMBTR predictions."""

    def __init__(
        self,
        redis_url: Optional[str] = None,
        depth: int = 8,
        confidence_threshold: Decimal = Decimal("0.60"),
        decay_rate: Decimal = Decimal("0.95"),
        min_observations: int = 10,
    ):
        """
        Initialize ASMBTR prediction service.

        Args:
            redis_url: Redis connection URL (defaults to env REDIS_URL)
            depth: BTR encoding depth (2-64)
            confidence_threshold: Minimum confidence for predictions (0.5-1.0)
            decay_rate: Observation decay rate (0.9-1.0)
            min_observations: Minimum observations required for predictions
        """
        self.redis_url = redis_url or os.getenv(
            "REDIS_URL", "redis://:@redis:6379/1"
        )
        self.redis_client = redis.from_url(self.redis_url, decode_responses=True)

        # ASMBTR configuration
        self.depth = depth
        self.confidence_threshold = confidence_threshold
        self.decay_rate = decay_rate
        self.min_observations = min_observations

        # State management (symbol → StateEncoder)
        self.encoders: Dict[str, StateEncoder] = {}
        self.prediction_tables: Dict[str, PredictionTable] = {}

        logger.info(
            f"🔮 ASMBTR Prediction Service initialized "
            f"(depth={depth}, threshold={confidence_threshold}, decay={decay_rate})"
        )

    def _get_or_create_encoder(self, symbol: str) -> StateEncoder:
        """Get or create StateEncoder for symbol."""
        if symbol not in self.encoders:
            # Use StateEncoder per symbol; StateEncoder expects depth only
            self.encoders[symbol] = StateEncoder(depth=self.depth)
            logger.info(f"📊 Created StateEncoder for {symbol}")
        return self.encoders[symbol]

    def _get_or_create_predictor(self, symbol: str) -> PredictionTable:
        """Get or create PredictionTable for symbol."""
        if symbol not in self.prediction_tables:
            # PredictionTable expects depth and decay_rate
            self.prediction_tables[symbol] = PredictionTable(
                depth=self.depth, decay_rate=float(self.decay_rate)
            )
            logger.info(f"🎯 Created PredictionTable for {symbol}")
        return self.prediction_tables[symbol]

    def fetch_latest_ticks(
        self, symbol: str, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Fetch latest market ticks from CCXT.

        In production, this would call fks_data service via HTTP.
        For now, using CCXT directly as fallback.

        Args:
            symbol: Trading pair (e.g., 'BTC/USDT')
            limit: Number of recent ticks to fetch

        Returns:
            List of tick dicts with 'timestamp', 'last', 'volume' keys
        """
        try:
            import ccxt

            exchange = ccxt.binance({"enableRateLimit": True})

            # Fetch recent OHLCV candles
            ohlcv = exchange.fetch_ohlcv(symbol, timeframe="1m", limit=limit)

            # Convert to tick format (ASMBTR expects 'last' price)
            ticks = [
                {
                    "timestamp": datetime.fromtimestamp(
                        candle[0] / 1000, tz=timezone.utc
                    ),
                    "last": Decimal(str(candle[4])),  # Close price
                    "volume": Decimal(str(candle[5])),
                }
                for candle in ohlcv
            ]

            logger.info(f"📈 Fetched {len(ticks)} ticks for {symbol}")
            return ticks

        except Exception as e:
            logger.error(f"❌ Failed to fetch ticks for {symbol}: {e}")
            return []

    def update_state(self, symbol: str, ticks: List[Dict[str, Any]]):
        """
        Update StateEncoder with new ticks.

        Args:
            symbol: Trading pair
            ticks: List of tick dicts

        Returns:
            Current BTR state string (e.g., '10110011') or None if no movements
        """
        if not ticks:
            return None

        encoder = self._get_or_create_encoder(symbol)
        prev_state = encoder.get_current_state()
        prev_state_seq = prev_state.sequence if prev_state else None

        # Process ticks via encoder.process_tick
        for tick in ticks:
            # Ensure tick includes 'last' price key
            # process_tick expects a dict with price under 'last'
            try:
                encoder.process_tick(tick, price_key='last')
            except Exception:
                # Ignore individual tick processing errors
                continue

        # Get current state object
        state = encoder.get_current_state()
        if state:
            # Record state transition if changed
            if prev_state_seq and prev_state_seq != state.sequence:
                from ..metrics.asmbtr_metrics import record_state_transition
                record_state_transition(symbol, prev_state_seq, state.sequence)

            logger.info(f"🔄 {symbol} state: {state.sequence}")
            return state
        return None

    def generate_prediction(
        self, symbol: str, state
    ) -> Optional[Dict[str, Any]]:
        """
        Generate prediction for current state.

        Args:
            symbol: Trading pair
            state: BTR state object (has .sequence)

        Returns:
            Prediction dict with 'prediction', 'confidence', 'up_prob', 'down_prob'
        """
        predictor = self._get_or_create_predictor(symbol)

        # `state` should be a BTRState object
        try:
            prediction = predictor.predict(state, min_observations=self.min_observations)
        except Exception as e:
            logger.error(f"❌ Prediction error for {symbol}: {e}")
            return None

        if not prediction:
            return None

        result = {
            "symbol": symbol,
            "state": getattr(state, "sequence", str(state)),
            "prediction": getattr(prediction, "prediction", None),
            "confidence": float(getattr(prediction, "confidence", 0.0)),
            "up_prob": float(getattr(prediction, "up_probability", 0.0)),
            "down_prob": float(getattr(prediction, "down_probability", 0.0)),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # Record metrics
        try:
            from ..metrics.asmbtr_metrics import record_prediction

            record_prediction(
                symbol=symbol,
                prediction=result["prediction"],
                confidence=result["confidence"],
            )
        except Exception:
            logger.debug("⚠️ Failed to record prediction metric")

        # Check if confidence meets threshold
        try:
            if result["confidence"] >= float(self.confidence_threshold):
                logger.info(
                    f"✅ {symbol} prediction: {result['prediction']} "
                    f"(confidence: {result['confidence']:.2%})"
                )
            else:
                logger.debug(
                    f"⚠️ {symbol} low confidence: {result['confidence']:.2%} "
                    f"(threshold: {float(self.confidence_threshold):.2%})"
                )
        except Exception:
            logger.debug("⚠️ Error evaluating confidence threshold")

        return result

    def store_prediction(self, symbol: str, prediction: Dict[str, Any]):
        """
        Store prediction in Redis.

        Key: asmbtr:predictions:{symbol}
        Value: JSON prediction dict
        TTL: 120 seconds (2x prediction interval)
        """
        key = f"asmbtr:predictions:{symbol}"
        try:
            self.redis_client.setex(
                key, 120, json.dumps(prediction, default=str)  # 2-minute TTL
            )
            logger.debug(f"💾 Stored prediction for {symbol} in Redis")
        except Exception as e:
            logger.error(f"❌ Failed to store prediction in Redis: {e}")

    def run_prediction_cycle(self, symbols: List[str]):
        """
        Run complete prediction cycle for all symbols.

        Args:
            symbols: List of trading pairs to predict
        """
        logger.info(f"🔮 Starting ASMBTR prediction cycle for {len(symbols)} symbols")

        for symbol in symbols:
            # Track execution time per symbol
            from ..metrics.asmbtr_metrics import track_execution_time
            
            with track_execution_time(symbol):
                try:
                    # 1. Fetch latest ticks
                    ticks = self.fetch_latest_ticks(symbol, limit=100)
                    if not ticks:
                        logger.warning(f"⚠️ No ticks fetched for {symbol}, skipping")
                        continue

                    # 2. Update state
                    state = self.update_state(symbol, ticks)
                    if not state:
                        logger.debug(f"⚠️ No state generated for {symbol}, skipping")
                        continue

                    # 3. Generate prediction
                    prediction = self.generate_prediction(symbol, state)
                    if not prediction:
                        logger.debug(f"⚠️ No prediction for {symbol}, skipping")
                        continue

                    # 4. Store in Redis
                    self.store_prediction(symbol, prediction)

                except Exception as e:
                    logger.error(f"❌ Error predicting {symbol}: {e}", exc_info=True)

        logger.info("✅ ASMBTR prediction cycle complete")


@shared_task(name="asmbtr.predict", bind=True, max_retries=3)
def predict_asmbtr_task(self, symbols: Optional[List[str]] = None):
    """
    Celery task for ASMBTR predictions.

    Args:
        symbols: List of trading pairs to predict (defaults to BTCUSDT, ETHUSDT)

    Returns:
        Dict with execution status
    """
    if symbols is None:
        symbols = ["BTC/USDT", "ETH/USDT"]

    logger.info(f"🚀 ASMBTR prediction task started for {symbols}")

    try:
        service = ASMBTRPredictionService()
        service.run_prediction_cycle(symbols)

        return {
            "status": "success",
            "symbols": symbols,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as exc:
        logger.error(f"❌ ASMBTR prediction task failed: {exc}", exc_info=True)
        # Retry with exponential backoff
        raise self.retry(exc=exc, countdown=60 * (2**self.request.retries))
