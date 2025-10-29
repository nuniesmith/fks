"""
Custom Prometheus metrics for FKS trading platform.
Tracks RAG latency, task success rates, and trading intelligence metrics.
"""

from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry
from django_prometheus.exports import ExportToDjangoView

# Create custom registry for FKS metrics
fks_registry = CollectorRegistry()

# RAG Intelligence Metrics
rag_query_duration = Histogram(
    'fks_rag_query_duration_seconds',
    'Time spent processing RAG queries',
    ['query_type', 'symbol'],
    registry=fks_registry
)

rag_query_count = Counter(
    'fks_rag_query_total',
    'Total number of RAG queries processed',
    ['query_type', 'status'],
    registry=fks_registry
)

rag_confidence_score = Histogram(
    'fks_rag_confidence_score',
    'Confidence scores from RAG recommendations',
    ['action_type'],
    registry=fks_registry
)

rag_sources_used = Histogram(
    'fks_rag_sources_used',
    'Number of historical sources used in RAG responses',
    ['query_type'],
    registry=fks_registry
)

# Trading Task Metrics
celery_task_duration = Histogram(
    'fks_celery_task_duration_seconds',
    'Time spent executing Celery tasks',
    ['task_name', 'status'],
    registry=fks_registry
)

celery_task_count = Counter(
    'fks_celery_task_total',
    'Total number of Celery tasks executed',
    ['task_name', 'status'],
    registry=fks_registry
)

# Trading Intelligence Metrics
trading_signal_generated = Counter(
    'fks_trading_signal_generated_total',
    'Total number of trading signals generated',
    ['signal_type', 'confidence_level'],
    registry=fks_registry
)

backtest_completed = Counter(
    'fks_backtest_completed_total',
    'Total number of backtests completed',
    ['strategy_name', 'symbol', 'status'],
    registry=fks_registry
)

portfolio_optimization_run = Counter(
    'fks_portfolio_optimization_run_total',
    'Total number of portfolio optimizations run',
    ['optimization_type', 'status'],
    registry=fks_registry
)

# Data Ingestion Metrics
documents_ingested = Counter(
    'fks_documents_ingested_total',
    'Total number of documents ingested into RAG',
    ['doc_type', 'status'],
    registry=fks_registry
)

chunks_ingested = Counter(
    'fks_chunks_ingested_total',
    'Total number of document chunks created',
    ['doc_type'],
    registry=fks_registry
)

# Market Data Metrics
market_data_fetched = Counter(
    'fks_market_data_fetched_total',
    'Total market data fetch operations',
    ['exchange', 'symbol', 'status'],
    registry=fks_registry
)

ohlcv_records_stored = Counter(
    'fks_ohlcv_records_stored_total',
    'Total OHLCV records stored in database',
    ['symbol', 'timeframe'],
    registry=fks_registry
)

# User Activity Metrics
api_requests_total = Counter(
    'fks_api_requests_total',
    'Total API requests by endpoint',
    ['endpoint', 'method', 'status_code'],
    registry=fks_registry
)

user_sessions_active = Gauge(
    'fks_user_sessions_active',
    'Number of currently active user sessions',
    registry=fks_registry
)

# Error Metrics
application_errors = Counter(
    'fks_application_errors_total',
    'Total application errors by type',
    ['error_type', 'component'],
    registry=fks_registry
)

# Performance Metrics
database_query_duration = Histogram(
    'fks_database_query_duration_seconds',
    'Time spent on database queries',
    ['query_type', 'table'],
    registry=fks_registry
)

cache_hit_ratio = Gauge(
    'fks_cache_hit_ratio',
    'Cache hit ratio (0.0 to 1.0)',
    ['cache_type'],
    registry=fks_registry
)


class FKSMetrics:
    """Helper class for recording FKS-specific metrics"""

    @staticmethod
    def record_rag_query(query_type: str, symbol: str, duration: float, status: str = 'success'):
        """Record RAG query metrics"""
        rag_query_duration.labels(query_type=query_type, symbol=symbol).observe(duration)
        rag_query_count.labels(query_type=query_type, status=status).inc()

    @staticmethod
    def record_rag_confidence(action_type: str, confidence: float):
        """Record RAG confidence scores"""
        rag_confidence_score.labels(action_type=action_type).observe(confidence)

    @staticmethod
    def record_rag_sources(query_type: str, sources_count: int):
        """Record number of sources used in RAG responses"""
        rag_sources_used.labels(query_type=query_type).observe(sources_count)

    @staticmethod
    def record_celery_task(task_name: str, duration: float, status: str = 'success'):
        """Record Celery task metrics"""
        celery_task_duration.labels(task_name=task_name, status=status).observe(duration)
        celery_task_count.labels(task_name=task_name, status=status).inc()

    @staticmethod
    def record_trading_signal(signal_type: str, confidence_level: str):
        """Record trading signal generation"""
        trading_signal_generated.labels(signal_type=signal_type, confidence_level=confidence_level).inc()

    @staticmethod
    def record_backtest(strategy_name: str, symbol: str, status: str = 'success'):
        """Record backtest completion"""
        backtest_completed.labels(strategy_name=strategy_name, symbol=symbol, status=status).inc()

    @staticmethod
    def record_portfolio_optimization(optimization_type: str, status: str = 'success'):
        """Record portfolio optimization runs"""
        portfolio_optimization_run.labels(optimization_type=optimization_type, status=status).inc()

    @staticmethod
    def record_document_ingestion(doc_type: str, status: str = 'success'):
        """Record document ingestion"""
        documents_ingested.labels(doc_type=doc_type, status=status).inc()

    @staticmethod
    def record_chunks_ingested(doc_type: str, count: int):
        """Record chunk ingestion"""
        chunks_ingested.labels(doc_type=doc_type).inc(count)

    @staticmethod
    def record_market_data_fetch(exchange: str, symbol: str, status: str = 'success'):
        """Record market data fetch operations"""
        market_data_fetched.labels(exchange=exchange, symbol=symbol, status=status).inc()

    @staticmethod
    def record_ohlcv_storage(symbol: str, timeframe: str, count: int):
        """Record OHLCV data storage"""
        ohlcv_records_stored.labels(symbol=symbol, timeframe=timeframe).inc(count)

    @staticmethod
    def record_api_request(endpoint: str, method: str, status_code: int):
        """Record API request metrics"""
        api_requests_total.labels(endpoint=endpoint, method=method, status_code=status_code).inc()

    @staticmethod
    def record_application_error(error_type: str, component: str):
        """Record application errors"""
        application_errors.labels(error_type=error_type, component=component).inc()

    @staticmethod
    def record_database_query(query_type: str, table: str, duration: float):
        """Record database query performance"""
        database_query_duration.labels(query_type=query_type, table=table).observe(duration)


# Export metrics to Django view
fks_metrics_view = ExportToDjangoView(fks_registry)