-- =============================================================================
-- migration: backup-support tables
-- Adds tables the backup service expects to exist.
-- Must run against ruby_db (the data/engine database).
-- =============================================================================

\set ruby_db `echo "${RUBY_DB:-ruby_db}"`
\set fks_user    `echo "${POSTGRES_USER:-fks_user}"`

\connect :ruby_db

-- Enabled assets (what the system actively tracks / trades)
CREATE TABLE IF NOT EXISTS enabled_assets (
    symbol          TEXT PRIMARY KEY,
    display_name    TEXT,
    exchange        TEXT NOT NULL DEFAULT 'kraken',  -- kraken | rithmic | binance
    asset_type      TEXT NOT NULL DEFAULT 'crypto',  -- crypto | futures | equity
    enabled         BOOLEAN NOT NULL DEFAULT TRUE,
    kraken_auto     BOOLEAN NOT NULL DEFAULT TRUE,
    min_confidence  FLOAT NOT NULL DEFAULT 0.65,
    max_position_pct FLOAT NOT NULL DEFAULT 0.05,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Per-asset, per-session indicator presets
CREATE TABLE IF NOT EXISTS indicator_presets (
    id          SERIAL PRIMARY KEY,
    name        TEXT NOT NULL,
    symbol      TEXT,                 -- NULL = global default
    indicators  JSONB NOT NULL,       -- {ema:{span:20,color:"..."}, rsi:{period:14}, ...}
    is_default  BOOLEAN NOT NULL DEFAULT FALSE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (name, symbol)
);

-- Strategy configs (execution gate rules, signal filters)
CREATE TABLE IF NOT EXISTS strategy_configs (
    id              SERIAL PRIMARY KEY,
    name            TEXT NOT NULL UNIQUE,
    config          JSONB NOT NULL,
    active          BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Alert configs (price, signal, system alerts)
CREATE TABLE IF NOT EXISTS alert_configs (
    id          SERIAL PRIMARY KEY,
    type        TEXT NOT NULL,        -- price | signal | system | circuit_breaker
    symbol      TEXT,
    condition   JSONB NOT NULL,
    channel     TEXT NOT NULL DEFAULT 'discord',
    enabled     BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Rithmic manual pending queue (persisted across restarts)
CREATE TABLE IF NOT EXISTS rithmic_pending_queue (
    id              TEXT PRIMARY KEY,    -- signal_id from Janus proto
    symbol          TEXT NOT NULL,
    direction       TEXT NOT NULL,       -- LONG | SHORT | FLAT
    confidence      FLOAT,
    suggested_size  FLOAT,
    stop_loss       FLOAT,
    take_profit     FLOAT,
    status          TEXT NOT NULL DEFAULT 'pending_manual',
    queued_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at      TIMESTAMPTZ,
    raw_signal      JSONB
);

-- Daily performance snapshots (P&L, win rate, trade count per day)
CREATE TABLE IF NOT EXISTS performance_daily (
    date            DATE PRIMARY KEY,
    net_pnl         FLOAT NOT NULL DEFAULT 0.0,
    gross_pnl       FLOAT NOT NULL DEFAULT 0.0,
    fees            FLOAT NOT NULL DEFAULT 0.0,
    trade_count     INT NOT NULL DEFAULT 0,
    win_count       INT NOT NULL DEFAULT 0,
    loss_count      INT NOT NULL DEFAULT 0,
    largest_win     FLOAT,
    largest_loss    FLOAT,
    avg_win         FLOAT,
    avg_loss        FLOAT,
    expectancy      FLOAT,
    notes           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_enabled_assets_exchange  ON enabled_assets(exchange);
CREATE INDEX IF NOT EXISTS idx_strategy_configs_active  ON strategy_configs(active);
CREATE INDEX IF NOT EXISTS idx_rithmic_queue_status     ON rithmic_pending_queue(status);
CREATE INDEX IF NOT EXISTS idx_alert_configs_symbol     ON alert_configs(symbol);
CREATE INDEX IF NOT EXISTS idx_performance_daily_date   ON performance_daily(date DESC);
