"""
data_factory — Automated data pipeline for FKS Trading System.

Provides: gap scanning, chunked backfill, cache warming, store
reconciliation, news ingestion, and Prometheus health metrics.

All workers are managed by the DataFactoryCoordinator which runs
as a [program:factory] process under supervisord inside fks_ruby.
"""

from __future__ import annotations
