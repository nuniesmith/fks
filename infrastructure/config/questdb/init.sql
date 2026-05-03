-- ============================================================================
-- QuestDB Initialization Script
-- ============================================================================
-- This script creates the necessary tables for the Janus Data Factory service.
-- Tables are optimized for time-series data with appropriate partitioning and
-- Write-Ahead Log (WAL) enabled for durability.
-- ============================================================================

-- ----------------------------------------------------------------------------
-- Crypto Trades Table
-- Stores real-time trade ticks from cryptocurrency exchanges
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS trades_crypto (
    ts TIMESTAMP,
    symbol SYMBOL CAPACITY 256 CACHE,
    exchange SYMBOL CAPACITY 16 CACHE,
    side SYMBOL CAPACITY 2 CACHE,
    price DOUBLE,
    amount DOUBLE,
    trade_id STRING,
    latency_ms LONG
) TIMESTAMP(ts) PARTITION BY DAY WAL;

-- Index on symbol for faster filtering
-- Note: QuestDB doesn't support secondary indices in the traditional sense,
-- but SYMBOL type provides implicit indexing

-- ----------------------------------------------------------------------------
-- Candles Table
-- Stores OHLCV candle data for backfilling and historical analysis
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS candles_crypto (
    ts TIMESTAMP,
    symbol SYMBOL CAPACITY 256 CACHE,
    exchange SYMBOL CAPACITY 16 CACHE,
    interval SYMBOL CAPACITY 8 CACHE,
    open DOUBLE,
    high DOUBLE,
    low DOUBLE,
    close DOUBLE,
    volume DOUBLE
) TIMESTAMP(ts) PARTITION BY DAY WAL;

-- ----------------------------------------------------------------------------
-- Market Metrics Table
-- Stores market-wide metrics like Fear & Greed Index, volatility, ETF flows
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS market_metrics (
    ts TIMESTAMP,
    metric_type SYMBOL CAPACITY 32 CACHE,
    asset SYMBOL CAPACITY 32 CACHE,
    source SYMBOL CAPACITY 32 CACHE,
    value DOUBLE,
    meta STRING
) TIMESTAMP(ts) PARTITION BY MONTH WAL;

-- ----------------------------------------------------------------------------
-- System Health Table
-- Stores health check data for monitoring service components
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS system_health (
    ts TIMESTAMP,
    component SYMBOL CAPACITY 64 CACHE,
    status SYMBOL CAPACITY 8 CACHE,
    message STRING
) TIMESTAMP(ts) PARTITION BY DAY WAL;

-- ----------------------------------------------------------------------------
-- UMAP Coordinates Table (Future Use)
-- Stores 2D/3D projection coordinates for market state visualization
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS umap_coordinates (
    ts TIMESTAMP,
    symbol SYMBOL CAPACITY 256 CACHE,
    model_id SYMBOL CAPACITY 64 CACHE,
    x DOUBLE,
    y DOUBLE,
    z DOUBLE,
    color STRING
) TIMESTAMP(ts) PARTITION BY DAY WAL;

-- ============================================================================
-- End of Initialization Script
-- ============================================================================
