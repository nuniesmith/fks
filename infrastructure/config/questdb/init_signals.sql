-- QuestDB Initialization Script for Signals Table
--
-- Creates the signals_crypto table with proper schema, partitioning, and retention policy
-- This script should be executed on QuestDB startup or manually via the HTTP API

-- Drop existing table if recreating (comment out for production)
-- DROP TABLE IF EXISTS signals_crypto;

-- Create signals_crypto table with optimized schema
CREATE TABLE IF NOT EXISTS signals_crypto (
    -- Symbol (e.g., "BTCUSD")
    symbol SYMBOL CAPACITY 256 CACHE,

    -- Exchange (e.g., "binance")
    exchange SYMBOL CAPACITY 64 CACHE,

    -- Timeframe (e.g., "1m", "5m", "15m", "1h", "4h")
    timeframe SYMBOL CAPACITY 32 CACHE,

    -- Signal type (e.g., "ema_golden_cross", "rsi_overbought", "bullish_confluence")
    signal_type SYMBOL CAPACITY 64 CACHE,

    -- Signal direction ("bullish" or "bearish")
    direction SYMBOL CAPACITY 16 CACHE,

    -- Signal strength (1-5)
    strength SHORT,

    -- Current price when signal was generated
    price DOUBLE,

    -- Indicator value that triggered the signal
    trigger_value DOUBLE,

    -- Optional secondary trigger value
    trigger_value_2 DOUBLE,

    -- Timestamp when signal was generated (designated timestamp column)
    timestamp TIMESTAMP,

    -- Additional context/description
    description STRING
) TIMESTAMP(timestamp) PARTITION BY DAY;

-- Create indexes for common query patterns
-- Note: QuestDB automatically indexes SYMBOL columns

-- Add WAL (Write-Ahead Log) for better durability (QuestDB 7.0+)
-- ALTER TABLE signals_crypto SET PARAM maxUncommittedRows = 10000;
-- ALTER TABLE signals_crypto SET PARAM o3MaxLag = 600s;

-- Set retention policy: Keep signals for 90 days
-- Older data will be automatically dropped
-- Note: This requires QuestDB 6.5+ and is executed separately

-- Example: DROP partitions older than 90 days
-- This should be run as a scheduled job (cron, etc.)
--
-- SELECT
--     'ALTER TABLE signals_crypto DROP PARTITION LIST ''' || to_str(timestamp, 'yyyy-MM-dd') || ''';' as drop_command
-- FROM signals_crypto
-- WHERE timestamp < dateadd('d', -90, now())
-- GROUP BY to_str(timestamp, 'yyyy-MM-dd')
-- ORDER BY timestamp;

-- Create a view for recent high-confidence signals (confluence signals)
CREATE VIEW IF NOT EXISTS high_confidence_signals AS
SELECT
    symbol,
    exchange,
    timeframe,
    signal_type,
    direction,
    strength,
    price,
    timestamp,
    description
FROM signals_crypto
WHERE signal_type IN ('bullish_confluence', 'bearish_confluence')
    AND timestamp > dateadd('d', -7, now())
ORDER BY timestamp DESC;

-- Create a view for signal counts per hour (useful for monitoring)
CREATE VIEW IF NOT EXISTS signals_per_hour AS
SELECT
    to_hour(timestamp) as hour_timestamp,
    symbol,
    timeframe,
    signal_type,
    direction,
    count() as signal_count
FROM signals_crypto
WHERE timestamp > dateadd('d', -1, now())
GROUP BY hour_timestamp, symbol, timeframe, signal_type, direction
ORDER BY hour_timestamp DESC;

-- Create a materialized aggregate for signal statistics (requires scheduled refresh)
-- This is a template - QuestDB doesn't support materialized views natively yet
-- Run this query periodically to refresh a separate stats table:
--
-- CREATE TABLE IF NOT EXISTS signals_stats_daily (
--     date DATE,
--     symbol SYMBOL,
--     timeframe SYMBOL,
--     signal_type SYMBOL,
--     total_count LONG,
--     bullish_count LONG,
--     bearish_count LONG,
--     avg_strength DOUBLE,
--     timestamp TIMESTAMP
-- ) TIMESTAMP(timestamp) PARTITION BY MONTH;
--
-- INSERT INTO signals_stats_daily
-- SELECT
--     to_date(timestamp) as date,
--     symbol,
--     timeframe,
--     signal_type,
--     count() as total_count,
--     count_where(direction = 'bullish') as bullish_count,
--     count_where(direction = 'bearish') as bearish_count,
--     avg(strength) as avg_strength,
--     now() as timestamp
-- FROM signals_crypto
-- WHERE to_date(timestamp) = to_date(now())
-- GROUP BY date, symbol, timeframe, signal_type;

-- Performance tuning recommendations:
--
-- 1. SYMBOL columns are automatically indexed and cached
-- 2. Partition by DAY allows efficient time-range queries
-- 3. Use timestamp in WHERE clauses for partition pruning
-- 4. Avoid SELECT * in production queries
-- 5. Use SAMPLE BY for time-series aggregations
-- 6. Monitor table size: SELECT count(), approx_percentile(timestamp, 0.5) FROM signals_crypto;

-- Example queries for common use cases:
--
-- -- Get recent signals for a symbol:
-- SELECT * FROM signals_crypto
-- WHERE symbol = 'BTCUSD'
--   AND timestamp > dateadd('h', -1, now())
-- ORDER BY timestamp DESC;
--
-- -- Count signals by type today:
-- SELECT signal_type, count()
-- FROM signals_crypto
-- WHERE timestamp >= to_date(now())
-- GROUP BY signal_type;
--
-- -- Find confluence signals with high strength:
-- SELECT * FROM signals_crypto
-- WHERE signal_type IN ('bullish_confluence', 'bearish_confluence')
--   AND strength >= 4
--   AND timestamp > dateadd('d', -7, now())
-- ORDER BY timestamp DESC;
--
-- -- Calculate win rate (requires joining with price data):
-- -- See backtest tool for full implementation

-- Maintenance commands:
--
-- -- Vacuum to reclaim space:
-- VACUUM TABLE signals_crypto;
--
-- -- Check table size:
-- SELECT pg_size_pretty(pg_total_relation_size('signals_crypto'));
--
-- -- Show partition list:
-- SELECT * FROM table_partitions('signals_crypto');
--
-- -- Drop old partitions manually (90 days retention):
-- ALTER TABLE signals_crypto DROP PARTITION LIST '2024-10-01';

-- End of initialization script
