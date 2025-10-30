-- Migration: 004_quality_metrics.sql
-- Description: Add quality_metrics hypertable for storing data quality monitoring results
-- Phase: 5.6 Task 3 - Pipeline Integration
-- Date: 2025-10-30

-- Create quality_metrics table for storing quality check results over time
CREATE TABLE IF NOT EXISTS quality_metrics (
    time TIMESTAMPTZ NOT NULL,
    symbol TEXT NOT NULL,
    
    -- Overall quality metrics
    overall_score DOUBLE PRECISION NOT NULL,
    status TEXT NOT NULL, -- excellent, good, fair, poor
    
    -- Component scores
    outlier_score DOUBLE PRECISION,
    freshness_score DOUBLE PRECISION,
    completeness_score DOUBLE PRECISION,
    
    -- Detailed metrics
    outlier_count INTEGER DEFAULT 0,
    outlier_severity TEXT, -- low, medium, high
    freshness_age_seconds DOUBLE PRECISION,
    completeness_percentage DOUBLE PRECISION,
    
    -- Issue tracking
    issues JSONB, -- Array of issue objects: [{type, severity, message}]
    issue_count INTEGER DEFAULT 0,
    
    -- Metadata
    check_duration_ms DOUBLE PRECISION, -- Duration of quality check in milliseconds
    collector_version TEXT DEFAULT 'v1.0',
    
    CONSTRAINT quality_metrics_score_range CHECK (overall_score >= 0 AND overall_score <= 100),
    CONSTRAINT quality_metrics_component_range CHECK (
        (outlier_score IS NULL OR (outlier_score >= 0 AND outlier_score <= 100)) AND
        (freshness_score IS NULL OR (freshness_score >= 0 AND freshness_score <= 100)) AND
        (completeness_score IS NULL OR (completeness_score >= 0 AND completeness_score <= 100))
    )
);

-- Create hypertable with 1-day chunks
SELECT create_hypertable(
    'quality_metrics',
    'time',
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists => TRUE
);

-- Create indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_quality_metrics_symbol_time 
    ON quality_metrics (symbol, time DESC);

CREATE INDEX IF NOT EXISTS idx_quality_metrics_status 
    ON quality_metrics (status, time DESC);

CREATE INDEX IF NOT EXISTS idx_quality_metrics_score 
    ON quality_metrics (overall_score, time DESC);

-- Index for issue filtering
CREATE INDEX IF NOT EXISTS idx_quality_metrics_issue_count 
    ON quality_metrics (issue_count, time DESC) 
    WHERE issue_count > 0;

-- Add compression policy (compress data older than 7 days)
-- Note: Columnstore compression requires TimescaleDB 2.11+
-- For now, use standard compression
SELECT add_compression_policy('quality_metrics', INTERVAL '7 days');

-- Retention policy: keep data for 90 days (configurable)
SELECT add_retention_policy(
    'quality_metrics',
    INTERVAL '90 days',
    if_not_exists => TRUE
);

-- Create continuous aggregate for hourly quality statistics
CREATE MATERIALIZED VIEW IF NOT EXISTS quality_metrics_hourly
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 hour', time) AS bucket,
    symbol,
    status,
    AVG(overall_score) AS avg_score,
    MIN(overall_score) AS min_score,
    MAX(overall_score) AS max_score,
    AVG(outlier_score) AS avg_outlier_score,
    AVG(freshness_score) AS avg_freshness_score,
    AVG(completeness_score) AS avg_completeness_score,
    SUM(issue_count) AS total_issues,
    COUNT(*) AS check_count,
    AVG(check_duration_ms) AS avg_duration_ms
FROM quality_metrics
GROUP BY bucket, symbol, status;

-- Add refresh policy (refresh hourly aggregate every 30 minutes)
-- Fixed: Use 2-hour window instead of 30 minutes to meet minimum bucket requirement
SELECT add_continuous_aggregate_policy('quality_metrics_hourly',
    start_offset => INTERVAL '2 hours',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '30 minutes'
);

-- Create daily aggregate for long-term trends
CREATE MATERIALIZED VIEW IF NOT EXISTS quality_metrics_daily
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 day', time) AS bucket,
    symbol,
    AVG(overall_score) AS avg_score,
    MIN(overall_score) AS min_score,
    MAX(overall_score) AS max_score,
    STDDEV(overall_score) AS stddev_score,
    SUM(issue_count) AS total_issues,
    COUNT(*) AS check_count,
    AVG(check_duration_ms) AS avg_duration_ms,
    -- Calculate percentage of time in each status
    SUM(CASE WHEN status = 'excellent' THEN 1 ELSE 0 END)::FLOAT / COUNT(*) * 100 AS pct_excellent,
    SUM(CASE WHEN status = 'good' THEN 1 ELSE 0 END)::FLOAT / COUNT(*) * 100 AS pct_good,
    SUM(CASE WHEN status = 'fair' THEN 1 ELSE 0 END)::FLOAT / COUNT(*) * 100 AS pct_fair,
    SUM(CASE WHEN status = 'poor' THEN 1 ELSE 0 END)::FLOAT / COUNT(*) * 100 AS pct_poor
FROM quality_metrics
GROUP BY bucket, symbol;

-- Refresh policy: update daily aggregate once per day
SELECT add_continuous_aggregate_policy(
    'quality_metrics_daily',
    start_offset => INTERVAL '3 days',
    end_offset => INTERVAL '1 day',
    schedule_interval => INTERVAL '1 day',
    if_not_exists => TRUE
);

-- Grant permissions
GRANT SELECT, INSERT ON quality_metrics TO fks_user;
GRANT SELECT ON quality_metrics_hourly TO fks_user;
GRANT SELECT ON quality_metrics_daily TO fks_user;

-- Add comments for documentation
COMMENT ON TABLE quality_metrics IS 'TimescaleDB hypertable for storing data quality metrics over time. Used by quality_collector.py for historical quality tracking.';
COMMENT ON COLUMN quality_metrics.time IS 'Timestamp when quality check was performed';
COMMENT ON COLUMN quality_metrics.symbol IS 'Trading pair symbol (e.g., BTCUSDT)';
COMMENT ON COLUMN quality_metrics.overall_score IS 'Composite quality score (0-100)';
COMMENT ON COLUMN quality_metrics.status IS 'Quality status: excellent (90-100), good (70-90), fair (50-70), poor (0-50)';
COMMENT ON COLUMN quality_metrics.issues IS 'JSON array of detected issues with type, severity, and message';
COMMENT ON COLUMN quality_metrics.check_duration_ms IS 'Duration of quality check in milliseconds';

COMMENT ON VIEW quality_metrics_hourly IS 'Hourly aggregated quality metrics for performance and trend analysis';
COMMENT ON VIEW quality_metrics_daily IS 'Daily aggregated quality metrics for long-term trend analysis';
