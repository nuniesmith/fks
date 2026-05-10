-- 07_memories.sql — Janus Execution Memories
-- Persistent store for closed-trade outcomes consumed by the Janus ML
-- feedback loop (FLOW-C + AI-C).  Every simulated and live trade that
-- closes is written here so the model can learn from historical execution
-- quality, regime fit, and signal accuracy over time.
--
-- Ring-buffer companion: Redis list  fks:memories:new  (LPUSH + LTRIM 500)
-- provides a low-latency feed for real-time inference without DB round-trips.
--
-- Must run against ruby_db (the data/engine database).
-- Run order: after 06_chain.sql
-- Run:  psql -U fks_user -d ruby_db -f 07_memories.sql

\set ruby_db `echo "${RUBY_DB:-ruby_db}"`

\connect :ruby_db

-- ---------------------------------------------------------------------------
-- Extension guard — gen_random_uuid() requires pgcrypto (PG < 13) or is
-- built-in from PG 13+.  The DO block installs it only when needed.
-- ---------------------------------------------------------------------------
DO $$
BEGIN
    IF current_setting('server_version_num')::int < 130000 THEN
        CREATE EXTENSION IF NOT EXISTS pgcrypto;
    END IF;
END;
$$;

-- ---------------------------------------------------------------------------
-- Core table
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS janus_memories (
    -- Primary key — UUID so records can be created across replicas without
    -- collisions and referenced by the ML feature store without integer leakage.
    memory_id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Signal lineage — links this outcome back to the originating Janus signal
    -- and the trading session it belongs to.
    signal_id               TEXT,
    session_id              TEXT,

    -- Instrument & strategy classification
    symbol                  TEXT                NOT NULL,
    strategy                TEXT                NOT NULL DEFAULT 'unknown',
    regime                  TEXT,                           -- e.g. 'trending', 'ranging', 'volatile'

    -- Signal metadata at the time of entry (snapshot for replay accuracy)
    signal_confidence       DOUBLE PRECISION,              -- 0.0–1.0
    signal_strength         DOUBLE PRECISION,              -- normalised strength score
    signal_direction        TEXT,                          -- 'LONG' | 'SHORT' | 'NEUTRAL'

    -- Trade outcome
    result                  TEXT CHECK (result IN ('win', 'loss', 'breakeven', 'partial')),
    entry_price             DOUBLE PRECISION,
    exit_price              DOUBLE PRECISION,
    pnl                     DOUBLE PRECISION,              -- realised P&L in account currency
    pnl_percent             DOUBLE PRECISION,              -- pnl / (entry_price × qty) × 100

    -- Excursion analytics (populated by live fills; NULL for simulation)
    max_favorable_excursion DOUBLE PRECISION,              -- MFE — best price during hold
    max_adverse_excursion   DOUBLE PRECISION,              -- MAE — worst price during hold

    -- Timing
    duration_ms             BIGINT,                        -- hold time in milliseconds
    exit_reason             TEXT,                          -- 'sl', 'tp', 'manual', 'timeout', …

    -- Execution quality (populated for live fills via broker slippage report)
    slippage_entry_bps      DOUBLE PRECISION,              -- basis points slippage on entry
    slippage_exit_bps       DOUBLE PRECISION,              -- basis points slippage on exit

    -- Timestamps
    opened_at               TIMESTAMPTZ,                   -- position entry time
    closed_at               TIMESTAMPTZ DEFAULT NOW(),     -- position exit time
    created_at              TIMESTAMPTZ DEFAULT NOW(),     -- row insertion time

    -- Arbitrary JSON bag for strategy-specific fields, indicator snapshots,
    -- model version tags, A/B test labels, etc.
    metadata                JSONB
);

-- ---------------------------------------------------------------------------
-- Indexes
-- ---------------------------------------------------------------------------

-- Lookups by instrument (most common query axis for the ML feature builder)
CREATE INDEX IF NOT EXISTS idx_jm_symbol
    ON janus_memories (symbol);

-- Lookups by strategy (used by the strategy evaluator to compute win-rate
-- per strategy and feed that signal into position-sizing)
CREATE INDEX IF NOT EXISTS idx_jm_strategy
    ON janus_memories (strategy);

-- Lookups by result (enables fast win/loss ratio queries without a full scan)
CREATE INDEX IF NOT EXISTS idx_jm_result
    ON janus_memories (result);

-- Time-series scans (dashboard charts, rolling P&L windows, recent-N queries)
CREATE INDEX IF NOT EXISTS idx_jm_created_at
    ON janus_memories (created_at DESC);

-- Session grouping — partial index keeps it lean; most rows have no session_id
CREATE INDEX IF NOT EXISTS idx_jm_session
    ON janus_memories (session_id)
    WHERE session_id IS NOT NULL;

-- Composite index for the most frequent ML query pattern:
--   SELECT … WHERE symbol = $1 AND strategy = $2 ORDER BY created_at DESC
CREATE INDEX IF NOT EXISTS idx_jm_symbol_strategy_time
    ON janus_memories (symbol, strategy, created_at DESC);

-- Signal lineage lookup — find all outcomes for a given originating signal
CREATE INDEX IF NOT EXISTS idx_jm_signal_id
    ON janus_memories (signal_id)
    WHERE signal_id IS NOT NULL;
