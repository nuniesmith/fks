#!/usr/bin/env python3
"""
QuestDB Prometheus Exporter
Exposes internal QuestDB metrics for Prometheus scraping.

Endpoints:
  GET /metrics  — Prometheus text format
  GET /health   — liveness probe (used by Docker HEALTHCHECK)
"""

from __future__ import annotations

import logging
import os
import signal
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import requests
from prometheus_client import CONTENT_TYPE_LATEST, REGISTRY, generate_latest
from prometheus_client.core import GaugeMetricFamily

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(name)s  %(levelname)s  %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("questdb-exporter")

# ---------------------------------------------------------------------------
# Configuration (all overridable via environment variables)
# ---------------------------------------------------------------------------
QUESTDB_HOST: str = os.getenv("QUESTDB_HOST", "localhost")
QUESTDB_PORT: str = os.getenv("QUESTDB_PORT", "9000")
EXPORTER_PORT: int = int(os.getenv("EXPORTER_PORT", "9122"))
SCRAPE_INTERVAL: int = int(os.getenv("SCRAPE_INTERVAL", "30"))
REQUEST_TIMEOUT: int = int(os.getenv("REQUEST_TIMEOUT", "10"))

QUESTDB_BASE_URL: str = f"http://{QUESTDB_HOST}:{QUESTDB_PORT}"

# Tables to monitor — override via comma-separated env var if needed
MONITORED_TABLES: list[str] = [
    t.strip()
    for t in os.getenv(
        "MONITORED_TABLES",
        "trades_crypto,candles_crypto,market_metrics,system_health",
    ).split(",")
    if t.strip()
]

# ---------------------------------------------------------------------------
# Graceful shutdown
# ---------------------------------------------------------------------------
_shutdown = threading.Event()


def _handle_signal(sig: int, _frame) -> None:  # noqa: ANN001
    logger.info("Signal %s received — shutting down", sig)
    _shutdown.set()


signal.signal(signal.SIGINT, _handle_signal)
signal.signal(signal.SIGTERM, _handle_signal)


# ---------------------------------------------------------------------------
# QuestDB collector
# ---------------------------------------------------------------------------
class QuestDBCollector:
    """Prometheus custom collector that queries QuestDB's REST API."""

    def __init__(self) -> None:
        self._base_url = QUESTDB_BASE_URL
        self._session = requests.Session()
        self._session.headers.update({"Accept": "application/json"})

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _query(self, sql: str) -> dict | None:
        """Run *sql* against QuestDB's /exec endpoint and return parsed JSON."""
        try:
            resp = self._session.get(
                f"{self._base_url}/exec",
                params={"query": sql},
                timeout=REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.Timeout:
            logger.warning("Query timed out: %.120s", sql)
        except requests.exceptions.ConnectionError as exc:
            logger.error("Cannot reach QuestDB at %s: %s", self._base_url, exc)
        except Exception as exc:  # noqa: BLE001
            logger.error("Query failed (%.120s): %s", sql, exc)
        return None

    @staticmethod
    def _rows(result: dict | None) -> list:
        """Safely extract the dataset list from a QuestDB response."""
        if result and "dataset" in result:
            return result["dataset"]
        return []

    # ------------------------------------------------------------------
    # Prometheus collector protocol
    # ------------------------------------------------------------------

    def collect(self):  # noqa: ANN201
        """Yield all metric families — called by Prometheus on every scrape."""
        yield from self._table_metrics()
        yield from self._partition_metrics()
        yield from self._wal_metrics()
        yield from self._storage_metrics()

    # ------------------------------------------------------------------
    # Table-level metrics
    # ------------------------------------------------------------------

    def _table_metrics(self):
        sql = f"""
            SELECT
                name            AS table_name,
                maxUncommittedRows,
                o3MaxLag,
                walEnabled
            FROM tables()
            WHERE name IN ({", ".join(f"'{t}'" for t in MONITORED_TABLES)})
        """
        rows = self._rows(self._query(sql))
        if not rows:
            return

        row_count_mf = GaugeMetricFamily(
            "questdb_table_rows",
            "Total number of rows in the table",
            labels=["table"],
        )
        size_mf = GaugeMetricFamily(
            "questdb_table_size_bytes",
            "On-disk size of the table in bytes",
            labels=["table"],
        )
        wal_mf = GaugeMetricFamily(
            "questdb_table_wal_enabled",
            "1 if WAL is enabled for this table, 0 otherwise",
            labels=["table"],
        )
        o3_mf = GaugeMetricFamily(
            "questdb_table_o3_max_lag_micros",
            "O3 maximum out-of-order lag in microseconds",
            labels=["table"],
        )
        uncommitted_mf = GaugeMetricFamily(
            "questdb_table_max_uncommitted_rows",
            "Maximum uncommitted rows before an automatic commit is triggered",
            labels=["table"],
        )

        for table_name, max_uncommitted, o3_max_lag, wal_enabled in rows:
            # Row count — separate query per table
            count_rows = self._rows(self._query(f"SELECT count() FROM '{table_name}'"))
            if count_rows:
                row_count_mf.add_metric([table_name], count_rows[0][0] or 0)

            # Partition-sum size
            size_rows = self._rows(self._query(f"SELECT sum(size) FROM table_partitions('{table_name}')"))
            if size_rows:
                size_mf.add_metric([table_name], size_rows[0][0] or 0)

            wal_mf.add_metric([table_name], 1 if wal_enabled else 0)
            o3_mf.add_metric([table_name], o3_max_lag or 0)
            uncommitted_mf.add_metric([table_name], max_uncommitted or 0)

        yield row_count_mf
        yield size_mf
        yield wal_mf
        yield o3_mf
        yield uncommitted_mf

    # ------------------------------------------------------------------
    # Partition-level metrics
    # ------------------------------------------------------------------

    def _partition_metrics(self):
        partition_tables = [t for t in MONITORED_TABLES if t in {"trades_crypto", "candles_crypto"}]

        for table in partition_tables:
            sql = f"""
                SELECT
                    name     AS partition,
                    size     AS size_bytes,
                    numRows  AS row_count
                FROM table_partitions('{table}')
                ORDER BY name DESC
                LIMIT 30
            """
            rows = self._rows(self._query(sql))
            if not rows:
                continue

            size_mf = GaugeMetricFamily(
                "questdb_partition_size_bytes",
                "On-disk size of a single partition in bytes",
                labels=["table", "partition"],
            )
            rows_mf = GaugeMetricFamily(
                "questdb_partition_rows",
                "Number of rows in a single partition",
                labels=["table", "partition"],
            )

            for partition_name, size_bytes, num_rows in rows:
                size_mf.add_metric([table, partition_name], size_bytes or 0)
                rows_mf.add_metric([table, partition_name], num_rows or 0)

            yield size_mf
            yield rows_mf

    # ------------------------------------------------------------------
    # WAL metrics
    # ------------------------------------------------------------------

    def _wal_metrics(self):
        sql = """
            SELECT
                name            AS table_name,
                sequencerTxn
            FROM tables()
            WHERE walEnabled = true
        """
        rows = self._rows(self._query(sql))
        if not rows:
            return

        txn_mf = GaugeMetricFamily(
            "questdb_wal_sequencer_txn",
            "Latest WAL sequencer transaction number",
            labels=["table"],
        )
        lag_mf = GaugeMetricFamily(
            "questdb_wal_lag_transactions",
            "Number of WAL transactions not yet applied to the table",
            labels=["table"],
        )

        for table_name, sequencer_txn in rows:
            txn_mf.add_metric([table_name], sequencer_txn or 0)

            # WAL writer status — applied_txn available in wal_tables()
            wal_rows = self._rows(self._query(f"SELECT writerTxn FROM wal_tables() WHERE tableName = '{table_name}'"))
            if wal_rows and wal_rows[0][0] is not None:
                lag = max(0, (sequencer_txn or 0) - wal_rows[0][0])
            else:
                lag = 0
            lag_mf.add_metric([table_name], lag)

        yield txn_mf
        yield lag_mf

    # ------------------------------------------------------------------
    # Storage metrics
    # ------------------------------------------------------------------

    def _storage_metrics(self):
        union_parts = "\n        UNION ALL\n        ".join(
            f"SELECT sum(size) AS size FROM table_partitions('{t}')"
            for t in MONITORED_TABLES
            if t != "system_health"  # skip tiny meta table from storage sum
        )
        sql = f"SELECT sum(size) FROM ({union_parts})"

        rows = self._rows(self._query(sql))
        if rows:
            total_mf = GaugeMetricFamily(
                "questdb_total_size_bytes",
                "Combined on-disk size of all monitored tables in bytes",
            )
            total_mf.add_metric([], rows[0][0] or 0)
            yield total_mf


# ---------------------------------------------------------------------------
# HTTP server — serves /metrics and /health on a single port
# ---------------------------------------------------------------------------
class MetricsHandler(BaseHTTPRequestHandler):
    """Minimal HTTP handler: /metrics → Prometheus exposition, /health → 200 OK."""

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            self._respond(200, "text/plain", b"ok\n")
        elif self.path in ("/metrics", "/metrics/"):
            output = generate_latest(REGISTRY)
            self._respond(200, CONTENT_TYPE_LATEST, output)
        else:
            self._respond(404, "text/plain", b"Not Found\n")

    def _respond(self, code: int, content_type: str, body: bytes) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args) -> None:  # noqa: ANN002, ANN003
        # Route nginx-style access log through our logger so it's structured
        logger.debug("HTTP %s", fmt % args)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main() -> None:
    logger.info("QuestDB Exporter starting on :%d", EXPORTER_PORT)
    logger.info("Connecting to QuestDB at %s", QUESTDB_BASE_URL)
    logger.info("Monitoring tables: %s", ", ".join(MONITORED_TABLES))

    # Register the collector once
    REGISTRY.register(QuestDBCollector())

    server = HTTPServer(("0.0.0.0", EXPORTER_PORT), MetricsHandler)
    server.timeout = 1  # allows the loop below to check _shutdown regularly

    logger.info("Listening — GET :%d/metrics  GET :%d/health", EXPORTER_PORT, EXPORTER_PORT)

    while not _shutdown.is_set():
        server.handle_request()

    logger.info("Shutdown complete")


if __name__ == "__main__":
    main()
