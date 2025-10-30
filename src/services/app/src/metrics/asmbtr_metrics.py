"""
Prometheus metrics for ASMBTR strategy.

Metrics exported:
- asmbtr_state_transitions_total: Counter for state transitions (by symbol, from_state, to_state)
- asmbtr_prediction_confidence: Gauge for current prediction confidence (by symbol)
- asmbtr_prediction_accuracy: Histogram for prediction accuracy over time
- asmbtr_predictions_total: Counter for total predictions made (by symbol, prediction)
- asmbtr_execution_duration_seconds: Histogram for prediction task execution time

These metrics are exposed on the /metrics endpoint of fks_app (port 8002).
Prometheus scrapes this endpoint every 15 seconds.

Usage in code:
    from metrics.asmbtr_metrics import record_prediction, record_state_transition
    
    record_state_transition(symbol='BTC/USDT', from_state='10101010', to_state='01010101')
    record_prediction(symbol='BTC/USDT', prediction=1, confidence=0.75, actual_outcome=1)
"""

import logging
import time
from contextlib import contextmanager
from typing import Optional

from prometheus_client import Counter, Gauge, Histogram

logger = logging.getLogger(__name__)

# ==============================================================================
# ASMBTR Metrics
# ==============================================================================

# State transitions counter
asmbtr_state_transitions_total = Counter(
    "asmbtr_state_transitions_total",
    "Total number of ASMBTR state transitions",
    ["symbol", "from_state", "to_state"],
)

# Prediction confidence gauge (current value per symbol)
asmbtr_prediction_confidence = Gauge(
    "asmbtr_prediction_confidence",
    "Current ASMBTR prediction confidence score",
    ["symbol"],
)

# Prediction accuracy histogram (tracks correctness over time)
asmbtr_prediction_accuracy = Histogram(
    "asmbtr_prediction_accuracy",
    "ASMBTR prediction accuracy (1.0 = correct, 0.0 = incorrect)",
    ["symbol"],
    buckets=[0.0, 0.25, 0.5, 0.75, 1.0],
)

# Total predictions counter
asmbtr_predictions_total = Counter(
    "asmbtr_predictions_total",
    "Total number of ASMBTR predictions made",
    ["symbol", "prediction"],  # prediction: 'UP', 'DOWN', 'NEUTRAL'
)

# Execution duration histogram
asmbtr_execution_duration_seconds = Histogram(
    "asmbtr_execution_duration_seconds",
    "ASMBTR prediction task execution duration in seconds",
    ["symbol"],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0],
)

# Observation count gauge
asmbtr_observation_count = Gauge(
    "asmbtr_observation_count",
    "Number of observations in ASMBTR prediction table",
    ["symbol", "state"],
)

# ==============================================================================
# Helper Functions
# ==============================================================================


def record_state_transition(symbol: str, from_state: str, to_state: str):
    """
    Record a state transition.

    Args:
        symbol: Trading pair (e.g., 'BTC/USDT')
        from_state: Previous BTR state (e.g., '10101010')
        to_state: New BTR state (e.g., '01010101')
    """
    try:
        asmbtr_state_transitions_total.labels(
            symbol=symbol, from_state=from_state, to_state=to_state
        ).inc()
        logger.debug(f"📊 Recorded state transition: {symbol} {from_state} → {to_state}")
    except Exception as e:
        logger.error(f"❌ Failed to record state transition: {e}")


def update_confidence_score(symbol: str, confidence: float):
    """
    Update current confidence score.

    Args:
        symbol: Trading pair
        confidence: Prediction confidence (0.0-1.0)
    """
    try:
        asmbtr_prediction_confidence.labels(symbol=symbol).set(confidence)
        logger.debug(f"📊 Updated confidence: {symbol} = {confidence:.2%}")
    except Exception as e:
        logger.error(f"❌ Failed to update confidence: {e}")


def record_prediction(
    symbol: str, prediction: int, confidence: float, actual_outcome: Optional[int] = None
):
    """
    Record a prediction and optionally its accuracy.

    Args:
        symbol: Trading pair
        prediction: Predicted direction (1=UP, -1=DOWN, 0=NEUTRAL)
        confidence: Prediction confidence (0.0-1.0)
        actual_outcome: Actual market direction (1=UP, -1=DOWN, 0=NEUTRAL) for accuracy tracking
    """
    try:
        # Map numeric prediction to label
        prediction_label = {1: "UP", -1: "DOWN", 0: "NEUTRAL"}.get(prediction, "UNKNOWN")

        # Increment prediction counter
        asmbtr_predictions_total.labels(symbol=symbol, prediction=prediction_label).inc()

        # Update confidence
        update_confidence_score(symbol, confidence)

        # Record accuracy if actual outcome provided
        if actual_outcome is not None:
            accuracy = 1.0 if prediction == actual_outcome else 0.0
            asmbtr_prediction_accuracy.labels(symbol=symbol).observe(accuracy)
            logger.debug(
                f"📊 Recorded prediction: {symbol} {prediction_label} "
                f"(confidence={confidence:.2%}, accuracy={accuracy:.0%})"
            )
        else:
            logger.debug(
                f"📊 Recorded prediction: {symbol} {prediction_label} (confidence={confidence:.2%})"
            )

    except Exception as e:
        logger.error(f"❌ Failed to record prediction: {e}")


def update_observation_count(symbol: str, state: str, count: int):
    """
    Update observation count for a specific state.

    Args:
        symbol: Trading pair
        state: BTR state
        count: Number of observations
    """
    try:
        asmbtr_observation_count.labels(symbol=symbol, state=state).set(count)
    except Exception as e:
        logger.error(f"❌ Failed to update observation count: {e}")


@contextmanager
def track_execution_time(symbol: str):
    """
    Context manager to track ASMBTR prediction execution time.

    Usage:
        with track_execution_time('BTC/USDT'):
            # Run prediction
            pass
    """
    start_time = time.time()
    try:
        yield
    finally:
        duration = time.time() - start_time
        try:
            asmbtr_execution_duration_seconds.labels(symbol=symbol).observe(duration)
            logger.debug(f"⏱️ ASMBTR execution: {symbol} took {duration:.2f}s")
        except Exception as e:
            logger.error(f"❌ Failed to record execution time: {e}")


# ==============================================================================
# Metrics Aggregation Class
# ==============================================================================


class ASMBTRMetrics:
    """
    Centralized metrics manager for ASMBTR strategy.

    This class provides a clean interface for recording all ASMBTR metrics.
    """

    @staticmethod
    def record_state_transition(symbol: str, from_state: str, to_state: str):
        """Record state transition."""
        record_state_transition(symbol, from_state, to_state)

    @staticmethod
    def update_confidence(symbol: str, confidence: float):
        """Update confidence score."""
        update_confidence_score(symbol, confidence)

    @staticmethod
    def record_prediction(
        symbol: str, prediction: int, confidence: float, actual_outcome: Optional[int] = None
    ):
        """Record prediction with optional accuracy."""
        record_prediction(symbol, prediction, confidence, actual_outcome)

    @staticmethod
    def update_observations(symbol: str, state: str, count: int):
        """Update observation count."""
        update_observation_count(symbol, state, count)

    @staticmethod
    @contextmanager
    def track_execution(symbol: str):
        """Track execution time."""
        with track_execution_time(symbol):
            yield

    @staticmethod
    def get_all_metrics():
        """
        Get summary of all ASMBTR metrics.

        Returns:
            Dict with metric names and current values
        """
        return {
            "state_transitions_total": asmbtr_state_transitions_total,
            "prediction_confidence": asmbtr_prediction_confidence,
            "prediction_accuracy": asmbtr_prediction_accuracy,
            "predictions_total": asmbtr_predictions_total,
            "execution_duration_seconds": asmbtr_execution_duration_seconds,
            "observation_count": asmbtr_observation_count,
        }
