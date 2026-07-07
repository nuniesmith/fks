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
-- Stores OHLCV candle data for backfilling and historical analysis.
--
-- ⚠️  This DDL is the CANONICAL schema for candles_crypto, but note QuestDB has
--     no Postgres-style initdb hook — it does not execute this file on startup
--     (init.sql is only baked into conf/ for reference). In practice the table
--     is auto-created over ILP (port 9009) by the janus candle sink the first
--     time a closed kline is written, so the shape below mirrors what ILP
--     actually creates on the live deploy (verified via SHOW COLUMNS):
--       - designated column is `timestamp` (µs TIMESTAMP), appended last by ILP
--         — NOT `ts`; the previous `ts` DDL never applied;
--       - symbol/exchange/interval are SYMBOL (ILP default CAPACITY 256 CACHE);
--       - columns match the fks-web reader (src/web/src/hooks.server.ts):
--         timestamp, open, high, low, close, volume, symbol, exchange, interval.
--     Because ILP creates the table first, `IF NOT EXISTS` here is a no-op on an
--     existing volume; the DEDUP clause below only self-applies on a genuinely
--     fresh QuestDB volume. For an ALREADY-RUNNING table apply the idempotent
--     migration in migrations/001_candles_crypto_dedup.sql (ALTER … DEDUP …).
--
-- DEDUP ENABLE UPSERT KEYS(...) makes duplicate candles impossible at the
-- storage layer: re-ingesting a row with the same
-- (timestamp, symbol, exchange, interval) upserts the existing row instead of
-- appending a duplicate. Requires a WAL table; the designated timestamp MUST be
-- one of the keys.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS candles_crypto (
    symbol SYMBOL CAPACITY 256 CACHE,
    exchange SYMBOL CAPACITY 256 CACHE,
    interval SYMBOL CAPACITY 256 CACHE,
    open DOUBLE,
    high DOUBLE,
    low DOUBLE,
    close DOUBLE,
    volume DOUBLE,
    timestamp TIMESTAMP
) TIMESTAMP(timestamp) PARTITION BY DAY WAL
  DEDUP UPSERT KEYS(timestamp, symbol, exchange, interval);

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
