"""
Logging configuration for Futures.

Provides a simple stdlib-based logging setup suitable for lightweight
deployments (e.g. Raspberry Pi).  Call ``setup_logging()`` once at
process startup — every subsequent ``get_logger()`` call will return
a standard ``logging.Logger``.

Usage::

    from utils.logging_config import setup_logging, get_logger

    setup_logging(level="INFO")
    logger = get_logger("engine")

    logger.info("engine started, account_size=%d, interval=%s", 150_000, "5m")

Ring buffer
-----------
A singleton ``_RingBufferHandler`` is always installed alongside the
stderr handler.  The web dashboard reads from it for the live log tail
without touching any files.  Access it via ``get_ring_buffer()``.

Daily log files
---------------
Set the ``LOG_DIR`` environment variable (e.g. ``LOG_DIR=/app/logs``)
to also write logs to ``{LOG_DIR}/YYYY-MM-DD.log`` files that rotate
at UTC midnight and are kept for 30 days.  The web dashboard's
historical log view reads these files directly.
"""

import collections
import logging
import logging.handlers
import os
import sys
import threading
from pathlib import Path
from typing import Any

_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"

# ---------------------------------------------------------------------------
# In-memory ring buffer — feeds the web dashboard's live log view
# ---------------------------------------------------------------------------


class _RingBufferHandler(logging.Handler):
    """Thread-safe in-memory ring buffer that retains the last *capacity* log
    records.  Installed as a singleton alongside the stderr handler so the
    web dashboard can tail logs without reading any files.

    Each stored entry is a plain dict::

        {
            "ts": float,  # record.created (Unix timestamp)
            "level": str,  # "INFO" | "WARNING" | "ERROR" | "DEBUG" | …
            "name": str,  # logger name  e.g. "__main__" or "web"
            "msg": str,  # fully formatted log line
        }
    """

    _singleton: "_RingBufferHandler | None" = None
    _lock: threading.Lock = threading.Lock()

    def __init__(self, capacity: int = 2000) -> None:
        super().__init__()
        self._buf: collections.deque[dict] = collections.deque(maxlen=capacity)
        self._buf_lock = threading.Lock()

    # ── logging.Handler interface ─────────────────────────────────────────────

    def emit(self, record: logging.LogRecord) -> None:
        try:
            entry = {
                "ts": record.created,
                "level": record.levelname,
                "name": record.name,
                "msg": self.format(record),
            }
            with self._buf_lock:
                self._buf.append(entry)
        except Exception:
            self.handleError(record)

    # ── Query helpers ─────────────────────────────────────────────────────────

    def get_since(
        self,
        since_ts: float = 0.0,
        level: str = "",
        name: str = "",
    ) -> list[dict]:
        """Return entries newer than *since_ts*, optionally filtered.

        Parameters
        ----------
        since_ts:
            Unix timestamp; only entries with ``ts > since_ts`` are returned.
            Pass ``0.0`` to get everything in the buffer.
        level:
            Case-insensitive level filter e.g. ``"WARNING"``.  Empty = all.
        name:
            Substring match on the logger name e.g. ``"btc"``.  Empty = all.
        """
        with self._buf_lock:
            entries = list(self._buf)

        result = [e for e in entries if e["ts"] > since_ts]

        if level:
            upper = level.upper()
            result = [e for e in result if e["level"] == upper]

        if name:
            lower = name.lower()
            result = [e for e in result if lower in e["name"].lower()]

        return result

    def get_all(self, level: str = "", name: str = "") -> list[dict]:
        """Return all buffered entries, optionally filtered."""
        return self.get_since(since_ts=0.0, level=level, name=name)

    def clear(self) -> None:
        with self._buf_lock:
            self._buf.clear()

    # ── Singleton factory ─────────────────────────────────────────────────────

    @classmethod
    def install(cls, capacity: int = 2000) -> "_RingBufferHandler":
        """Return the singleton, creating it on first call."""
        with cls._lock:
            if cls._singleton is None:
                cls._singleton = cls(capacity)
            return cls._singleton

    @classmethod
    def get_instance(cls) -> "_RingBufferHandler | None":
        """Return the singleton if already installed, else ``None``."""
        return cls._singleton


def get_ring_buffer() -> "_RingBufferHandler | None":
    """Return the installed ``_RingBufferHandler`` singleton.

    Returns ``None`` if ``setup_logging()`` has not been called yet.
    """
    return _RingBufferHandler.get_instance()


# ---------------------------------------------------------------------------
# setup_logging
# ---------------------------------------------------------------------------


def setup_logging(
    *,
    level: str | None = None,
    service: str = "futures",
) -> None:
    """Configure stdlib ``logging`` for the whole process.

    Always installs:
    - A ``StreamHandler`` writing to stderr.
    - A ``_RingBufferHandler`` singleton for the web dashboard live view.

    Optionally installs (when ``LOG_DIR`` env var is set):
    - A ``TimedRotatingFileHandler`` that writes ``{LOG_DIR}/YYYY-MM-DD.log``
      files rotating at UTC midnight, keeping 30 days of history.

    Parameters
    ----------
    level:
        Root log level.  Falls back to the ``LOG_LEVEL`` env var, then
        ``"INFO"``.
    service:
        Accepted for backward compatibility but unused.
    """
    if level is None:
        level = os.getenv("LOG_LEVEL", "INFO").upper()

    numeric_level = getattr(logging, level, logging.INFO)
    formatter = logging.Formatter(_LOG_FORMAT)

    # ── stderr handler ────────────────────────────────────────────────────────
    stream_handler = logging.StreamHandler(sys.stderr)
    stream_handler.setFormatter(formatter)

    # ── ring buffer handler ───────────────────────────────────────────────────
    ring = _RingBufferHandler.install(capacity=2000)
    ring.setFormatter(formatter)

    # ── rebuild root logger handlers ──────────────────────────────────────────
    root_logger = logging.getLogger()
    # Keep any non-StreamHandler, non-ring handlers (e.g. from trainer_server)
    _keep = [
        h
        for h in root_logger.handlers
        if not isinstance(h, (logging.StreamHandler, _RingBufferHandler))
    ]
    root_logger.handlers.clear()
    for h in _keep:
        root_logger.addHandler(h)
    root_logger.addHandler(stream_handler)
    root_logger.addHandler(ring)
    root_logger.setLevel(numeric_level)

    # ── optional daily rotating file handler ──────────────────────────────────
    log_dir_env = os.getenv("LOG_DIR", "").strip()
    if log_dir_env:
        log_dir = Path(log_dir_env)
        log_dir.mkdir(parents=True, exist_ok=True)

        fh = logging.handlers.TimedRotatingFileHandler(
            filename=log_dir / "futures.log",
            when="midnight",
            utc=True,
            backupCount=30,
            encoding="utf-8",
        )
        fh.setFormatter(formatter)

        # Rename rotated files from "futures.log.YYYY-MM-DD" → "YYYY-MM-DD.log"
        _log_dir_ref = log_dir  # capture for closure

        def _namer(default_name: str) -> str:
            # default_name looks like "/app/logs/futures.log.2024-01-15"
            p = Path(default_name)
            suffix = p.suffix.lstrip(".")  # "2024-01-15"
            if len(suffix) == 10 and suffix[4] == "-":
                return str(_log_dir_ref / f"{suffix}.log")
            return default_name

        fh.namer = _namer
        root_logger.addHandler(fh)

    # ── silence noisy third-party loggers ─────────────────────────────────────
    for noisy in (
        "uvicorn.access",
        "httpx",
        "httpcore",
        "websockets",
        "urllib3",
        "sqlalchemy.engine",
        "hmmlearn",
        "matplotlib",
    ):
        logging.getLogger(noisy).setLevel(logging.WARNING)


# ---------------------------------------------------------------------------
# get_logger
# ---------------------------------------------------------------------------


def get_logger(name: str | None = None, **initial_binds: Any) -> logging.Logger:
    """Return a stdlib logger.

    Parameters
    ----------
    name:
        Logger name.  When ``None``, returns the root logger.
    **initial_binds:
        Accepted for backward compatibility with the previous
        structlog-based interface but silently ignored.

    Examples
    --------
    >>> logger = get_logger("engine")
    >>> logger.info("refresh complete, bars=%d", 500)
    """
    return logging.getLogger(name)
