"""
Unified logging module for FKS project.

Consolidates logging functionality from:
- src/data/app_logging.py (JSON logging, basicConfig)
- src/worker/fks_logging.py (StreamHandler wrapper)

Usage:
    from core.utils.logging import get_logger, init_logging

    logger = get_logger(__name__)
    logger.info("Trading signal generated", extra={"symbol": "BTCUSDT"})
"""

import json
import logging
import os
from typing import Optional

_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"
_LOGGER_INITIALIZED = False


class JsonFormatter(logging.Formatter):
    """JSON formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        data = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname.lower(),
            "name": record.name,
            "message": record.getMessage(),
        }

        # Add extra fields if provided
        extra = getattr(record, "extra", None)
        if isinstance(extra, dict):
            data.update(extra)

        # Add exception info if present
        if record.exc_info:
            data["exception"] = self.formatException(record.exc_info)

        return json.dumps(data)


def init_logging(force: bool = False, level: str | None = None) -> None:
    """
    Initialize logging configuration.

    Args:
        force: Force re-initialization even if already initialized
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    global _LOGGER_INITIALIZED

    if _LOGGER_INITIALIZED and not force:
        return

    # Determine if JSON logging is enabled
    json_logs = os.getenv("FKS_JSON_LOGS", "0").lower() in ("1", "true", "yes")

    # Determine log level
    if level is None:
        level = os.getenv("FKS_LOG_LEVEL", "INFO").upper()
    log_level = getattr(logging, level, logging.INFO)

    # Create handlers
    handlers = []
    handler = logging.StreamHandler()

    if json_logs:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                "[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )

    handlers.append(handler)

    # Configure logging
    logging.basicConfig(level=log_level, format=_FORMAT, handlers=handlers, force=True)

    _LOGGER_INITIALIZED = True


def get_logger(name: str = "fks") -> logging.Logger:
    """
    Get a logger instance with the specified name.

    Args:
        name: Logger name (typically __name__ of the module)

    Returns:
        Configured logger instance
    """
    if not _LOGGER_INITIALIZED:
        init_logging()

    return logging.getLogger(name)


def log_trade(
    symbol: str, action: str, price: float, quantity: float, **kwargs
) -> None:
    """
    Log a trading action.

    Args:
        symbol: Trading symbol (e.g., "BTCUSDT")
        action: Trading action (e.g., "BUY", "SELL")
        price: Trade price
        quantity: Trade quantity
        **kwargs: Additional trade details
    """
    logger = get_logger("fks.trading")
    logger.info(
        f"{action} {symbol}: {quantity} @ {price}",
        extra={
            "event_type": "trade",
            "symbol": symbol,
            "action": action,
            "price": price,
            "quantity": quantity,
            **kwargs,
        },
    )


def log_signal(symbol: str, signal_type: str, confidence: float, **kwargs) -> None:
    """
    Log a trading signal.

    Args:
        symbol: Trading symbol
        signal_type: Signal type (e.g., "BUY", "SELL", "HOLD")
        confidence: Signal confidence (0-1)
        **kwargs: Additional signal details
    """
    logger = get_logger("fks.signals")
    logger.info(
        f"Signal for {symbol}: {signal_type} (confidence: {confidence:.2%})",
        extra={
            "event_type": "signal",
            "symbol": symbol,
            "signal_type": signal_type,
            "confidence": confidence,
            **kwargs,
        },
    )


__all__ = [
    "get_logger",
    "init_logging",
    "log_trade",
    "log_signal",
    "JsonFormatter",
]
