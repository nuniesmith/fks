-- 06_chain.sql — On-chain monitoring tables
-- Tables for whale transaction tracking, exchange flow monitoring,
-- wallet watchlists, and the convenience feed view.
-- Must run against ruby_db (the data/engine database).
-- Run: psql -U fks_user -d ruby_db -f 06_chain.sql

\set ruby_db `echo "${RUBY_DB:-ruby_db}"`

\connect :ruby_db

CREATE TABLE IF NOT EXISTS chain_transactions (
    id               BIGSERIAL PRIMARY KEY,
    chain            TEXT NOT NULL,          -- BTC | ETH | SOL
    tx_hash          TEXT NOT NULL UNIQUE,   -- dedup key
    tx_type          TEXT NOT NULL,
    amount_native    DOUBLE PRECISION,
    amount_usd       DOUBLE PRECISION,
    from_address     TEXT,
    to_address       TEXT,
    from_label       TEXT,
    to_label         TEXT,
    token            TEXT,
    tx_timestamp     TIMESTAMPTZ NOT NULL,
    block_height     BIGINT,
    tier             TEXT,                   -- mega | large | medium | small
    sentiment        TEXT,                   -- bullish | bearish | neutral
    source           TEXT,                   -- whale_alert | etherscan | solscan
    correlation_score REAL DEFAULT 0,
    raw_json         JSONB,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chain_tx_chain     ON chain_transactions (chain, tx_timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_chain_tx_tier      ON chain_transactions (tier, tx_timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_chain_tx_sentiment ON chain_transactions (sentiment, tx_timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_chain_tx_usd       ON chain_transactions (amount_usd DESC, tx_timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_chain_tx_labels    ON chain_transactions USING GIN (to_tsvector('english', coalesce(from_label,'') || ' ' || coalesce(to_label,'')));

CREATE TABLE IF NOT EXISTS chain_exchange_flows (
    id             BIGSERIAL PRIMARY KEY,
    chain          TEXT NOT NULL,
    exchange       TEXT NOT NULL,
    inflow_native  DOUBLE PRECISION,
    outflow_native DOUBLE PRECISION,
    inflow_usd     DOUBLE PRECISION,
    outflow_usd    DOUBLE PRECISION,
    net_native     DOUBLE PRECISION,         -- positive = outflow dominant (bullish)
    sentiment      TEXT,
    period_hours   INT DEFAULT 24,
    as_of          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chain_flows_chain ON chain_exchange_flows (chain, as_of DESC);

CREATE TABLE IF NOT EXISTS chain_watchlist (
    address      TEXT NOT NULL,
    chain        TEXT NOT NULL,
    label        TEXT,
    min_usd      DOUBLE PRECISION DEFAULT 0,
    alert_on_any BOOLEAN DEFAULT TRUE,
    enabled      BOOLEAN DEFAULT TRUE,
    added_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (address, chain)
);

-- Convenience view for the terminal feed
CREATE OR REPLACE VIEW chain_whale_feed AS
SELECT
    id, chain, tx_hash, tx_type,
    amount_native, amount_usd, token,
    from_label, to_label,
    from_address, to_address,
    tier, sentiment, correlation_score,
    tx_timestamp,
    EXTRACT(EPOCH FROM (NOW() - tx_timestamp))::INT AS age_seconds
FROM chain_transactions
WHERE tx_timestamp > NOW() - INTERVAL '24 hours'
ORDER BY tx_timestamp DESC;
