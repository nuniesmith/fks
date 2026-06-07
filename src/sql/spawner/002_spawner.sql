-- =============================================================================
-- 002-spawner.sql — Bot Spawner schema (SPAWN-C)
-- =============================================================================
-- Creates bot_configs and bot_runs tables in ruby_db (see 001_init.sql for why
-- the database keeps the ruby_db name). Owned by the fks_bot_spawner service
-- (crates/spawner/) and the Bot Manager WebUI.
--
-- Prerequisites: 001_init.sql (creates the database). Self-contained otherwise —
-- the only foreign key (bot_runs.bot_config_id → bot_configs.id) is in-file, and
-- gen_random_uuid() is built into PostgreSQL 13+.
--
-- Idempotent — safe to re-run (CREATE TABLE IF NOT EXISTS, DROP TRIGGER IF EXISTS).
--
-- Manual execution:
--   docker compose exec postgres \
--     psql -U fks_user -d ruby_db -f /docker-entrypoint-initdb.d/25-spawner.sql
-- =============================================================================

\getenv fks_user  POSTGRES_USER
\getenv ruby_db   RUBY_DB

\connect :ruby_db

-- =============================================================================
-- bot_configs — reusable bot configuration profiles
-- =============================================================================
-- Stores named bot configuration profiles. A single config can be used to
-- spawn multiple bot_runs (e.g. the same strategy on different accounts).
-- Soft-delete via is_active rather than hard DELETE to preserve run history.
-- =============================================================================

CREATE TABLE IF NOT EXISTS bot_configs (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Human-readable name; used as container name suffix hint
    name            TEXT        NOT NULL,

    -- Raw YAML injected into the container as BOT_CONFIG env var
    config_yaml     TEXT,

    -- Structured config for UI rendering and programmatic access
    config_json     JSONB,

    -- Execution mode
    mode            TEXT        NOT NULL DEFAULT 'paper',

    -- Docker image; must start with fks-bot-
    image           TEXT        NOT NULL DEFAULT 'fks-bot-generic:latest',

    -- Optional template this config was cloned from
    template_name   TEXT,

    -- Optional resource overrides
    cpu_limit       NUMERIC(5, 2),
    memory_mb       INTEGER,

    -- Soft-delete: set false rather than deleting referenced configs
    is_active       BOOLEAN     NOT NULL DEFAULT TRUE,

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT bot_configs_name_unique UNIQUE (name),
    CONSTRAINT bot_configs_mode_valid  CHECK (
        mode IN ('paper', 'live', 'backtest', 'optimise', 'train')
    )
);

COMMENT ON TABLE  bot_configs              IS 'Reusable bot configuration profiles for the spawner service';
COMMENT ON COLUMN bot_configs.config_yaml  IS 'Raw YAML injected into the container as BOT_CONFIG env var';
COMMENT ON COLUMN bot_configs.config_json  IS 'Structured config for UI rendering';
COMMENT ON COLUMN bot_configs.mode         IS 'Execution mode: paper | live | backtest | optimise | train';
COMMENT ON COLUMN bot_configs.image        IS 'Docker image; must start with fks-bot-';
COMMENT ON COLUMN bot_configs.is_active    IS 'Soft-delete flag — set false rather than deleting referenced configs';

-- =============================================================================
-- bot_runs — individual container execution records
-- =============================================================================
-- One row per container spawn. Populated and updated by the spawner service
-- (which polls bot container metrics/health from each bot's /metrics endpoint).
-- bot_config_id is SET NULL on delete so run history is preserved.
-- =============================================================================

CREATE TABLE IF NOT EXISTS bot_runs (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Config used for this run (nullable — supports ad-hoc spawns)
    bot_config_id   UUID        REFERENCES bot_configs(id) ON DELETE SET NULL,

    -- Docker identifiers
    container_id    TEXT        NOT NULL,       -- Short form, 12 chars
    container_name  TEXT,                       -- fks-bot-<bot_id>
    image           TEXT        NOT NULL,

    -- Execution mode at time of spawn
    mode            TEXT        NOT NULL DEFAULT 'paper',

    -- Lifecycle status (updated by spawner + polling)
    status          TEXT        NOT NULL DEFAULT 'spawning',

    started_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    stopped_at      TIMESTAMPTZ,

    -- Populated by trigger when stopped_at is first set
    runtime_secs    INTEGER,

    -- Final P&L collected from the bot's /metrics endpoint before stop
    pnl_final       NUMERIC(20, 8),

    -- Cumulative counts from bot metrics
    signal_count    INTEGER     NOT NULL DEFAULT 0,
    trade_count     INTEGER     NOT NULL DEFAULT 0,
    win_rate        NUMERIC(5, 4),   -- 0.0000–1.0000

    -- Last known resource snapshot (for the Bot Manager resource panel)
    last_cpu_pct    NUMERIC,
    last_mem_mb     NUMERIC,
    last_heartbeat  TIMESTAMPTZ,

    -- Last error message when status = 'error'
    error_message   TEXT,

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT bot_runs_status_valid CHECK (
        status IN ('spawning', 'running', 'stopping', 'stopped', 'error', 'pruned')
    )
);

COMMENT ON TABLE  bot_runs                IS 'Individual bot container execution records';
COMMENT ON COLUMN bot_runs.container_id   IS 'Short Docker container ID (12 chars)';
COMMENT ON COLUMN bot_runs.status         IS 'spawning | running | stopping | stopped | error | pruned';
COMMENT ON COLUMN bot_runs.runtime_secs   IS 'Seconds elapsed; set by trigger when stopped_at is first written';
COMMENT ON COLUMN bot_runs.pnl_final      IS 'Final P&L from fks_bot_pnl_dollars metric at stop time';
COMMENT ON COLUMN bot_runs.win_rate       IS 'Win rate 0.0–1.0 at stop time';

-- =============================================================================
-- Indexes
-- =============================================================================

CREATE INDEX IF NOT EXISTS idx_bot_configs_mode         ON bot_configs(mode);
CREATE INDEX IF NOT EXISTS idx_bot_configs_active       ON bot_configs(is_active);

CREATE INDEX IF NOT EXISTS idx_bot_runs_status          ON bot_runs(status);
CREATE INDEX IF NOT EXISTS idx_bot_runs_started_at      ON bot_runs(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_bot_runs_container_id    ON bot_runs(container_id);
-- Partial index: bot_config_id is nullable so only index non-null rows
CREATE INDEX IF NOT EXISTS idx_bot_runs_bot_config_id   ON bot_runs(bot_config_id)
    WHERE bot_config_id IS NOT NULL;

-- =============================================================================
-- Trigger functions
-- =============================================================================

-- Stamp updated_at whenever a bot_config row is modified.
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_bot_configs_updated_at ON bot_configs;
CREATE TRIGGER trg_bot_configs_updated_at
    BEFORE UPDATE ON bot_configs
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- Compute runtime_secs once when stopped_at is first set.
CREATE OR REPLACE FUNCTION compute_bot_run_runtime()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.stopped_at IS NOT NULL AND OLD.stopped_at IS NULL THEN
        NEW.runtime_secs = EXTRACT(EPOCH FROM (NEW.stopped_at - NEW.started_at))::INTEGER;
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_bot_runs_runtime ON bot_runs;
CREATE TRIGGER trg_bot_runs_runtime
    BEFORE UPDATE ON bot_runs
    FOR EACH ROW EXECUTE FUNCTION compute_bot_run_runtime();

-- =============================================================================
-- Privileges
-- =============================================================================

GRANT ALL PRIVILEGES ON ALL TABLES    IN SCHEMA public TO :fks_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO :fks_user;
