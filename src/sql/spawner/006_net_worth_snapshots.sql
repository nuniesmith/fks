-- =============================================================================
-- 006-net_worth_snapshots.sql — Durable net-worth history backbone
-- =============================================================================
-- Creates the net_worth_snapshots table in fks_db (see 001_init.sql for why
-- the database keeps the fks_db name). Owned by the fks_bot_spawner service
-- (crates/spawner/), whose periodic sampler polls each running bot's /status
-- endpoint (:9091 on fks_network) and appends one row per bot per interval.
--
-- WHY A DURABLE TABLE (not just Prometheus):
--   Today the only net-worth series is the bots' `fks_bot_*` Prometheus gauges,
--   which live under a 30-day retention window — fine for ops dashboards, wrong
--   for a years-horizon net-worth record. This table is the append-only backbone
--   that record survives on; Prometheus stays the short-horizon ops view.
--
-- SHAPE:
--   One row = one net-worth reading for one bot at one instant. `net_worth` is
--   the bot's total account value in `currency` (USD by default). `venue` is
--   nullable — a bot-level total spans venues (NULL); it exists so a future
--   per-venue breakdown, or the planned on-chain xpub watcher, can write finer
--   rows into the SAME table (`source` distinguishes writers: 'bot_status' now,
--   'onchain' later — see docs/architecture/WEBUI_PLATFORM_ROADMAP.md §4.2/§4.3
--   — plus 'bot_status_stale', a mark-not-delete provenance re-label applied
--   retroactively by 015_net_worth_stale_provenance.sql, never written directly
--   by the sampler).
--
-- ID CHOICE: unlike bot_configs/bot_runs (UUID) this is a high-frequency,
--   append-only time series, so it uses a monotonic BIGINT identity PK — lighter
--   index, natural ins-order clustering — rather than a random UUID.
--
-- Prerequisites: 001_init.sql (creates the database + gen_random_uuid, though
--   this table needs neither an extension nor a foreign key — bot_id is the
--   logical bot identity (the fks.bot_id label), stable across container
--   restarts, deliberately NOT a FK to bot_runs.container_id).
--
-- Idempotent — safe to re-run (CREATE TABLE IF NOT EXISTS, CREATE INDEX IF NOT
-- EXISTS).
--
-- Manual execution (existing volumes skip initdb — apply by hand once):
--   docker exec -i fks_postgres sh -c \
--     'psql -U "$POSTGRES_USER" -d fks_db' < src/sql/spawner/006_net_worth_snapshots.sql
-- =============================================================================

\getenv fks_user  POSTGRES_USER
\getenv fks_db   RUBY_DB

\connect :fks_db

-- =============================================================================
-- net_worth_snapshots — one row per bot per sample tick
-- =============================================================================

CREATE TABLE IF NOT EXISTS net_worth_snapshots (
    -- Monotonic surrogate key for an append-only series (see header).
    id          BIGINT      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    -- Logical bot identity — the fks.bot_id label the spawner stamps on every
    -- container. Stable across restarts, so a bot's history stitches together
    -- even as containers come and go. Not a FK (bot_runs is keyed by the
    -- ephemeral container id/uuid).
    bot_id      TEXT        NOT NULL,

    -- Instant the reading was taken (== insert time; the sampler lets this
    -- default so the DB clock is authoritative).
    ts          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Total account value at `ts`, denominated in `currency`. NUMERIC (not
    -- float) so a years-horizon record never accrues binary-rounding drift;
    -- wide precision covers both USD totals and crypto-denominated quantities.
    net_worth   NUMERIC(38, 18) NOT NULL,

    -- Denomination of `net_worth`. USD for the crypto bots' aggregate total.
    currency    TEXT        NOT NULL DEFAULT 'USD',

    -- Optional venue/exchange for a per-venue row. NULL for a bot-level total
    -- (which spans venues).
    venue       TEXT,

    -- Which writer produced the row / how it got its provenance:
    --   'bot_status'       — the spawner sampler polling a bot's /status (today).
    --   'onchain'          — the future xpub watcher (later).
    --   'bot_status_stale' — a 'bot_status' row re-labelled, never written
    --                        directly, by 015_net_worth_stale_provenance.sql
    --                        (a frozen /status reading recorded as if it were
    --                        a live one; mark-not-delete, see 015 for why).
    --                        Readers exclude it — see NET_WORTH_WINDOW_SQL and
    --                        siblings in crates/spawner.
    -- No CHECK constraint: 006 is `CREATE TABLE IF NOT EXISTS`, so adding one
    -- here would not reach the already-live production table without a
    -- separate ALTER TABLE migration — deferred, not skipped by oversight.
    source      TEXT        NOT NULL DEFAULT 'bot_status'
);

COMMENT ON TABLE  net_worth_snapshots           IS 'Durable append-only net-worth history (spawner sampler + future on-chain watcher). Not bound to Prometheus retention.';
COMMENT ON COLUMN net_worth_snapshots.bot_id    IS 'Logical bot identity (fks.bot_id label); stable across container restarts; not a FK';
COMMENT ON COLUMN net_worth_snapshots.ts        IS 'Instant the reading was taken (defaults to insert time)';
COMMENT ON COLUMN net_worth_snapshots.net_worth IS 'Total account value at ts, in `currency`; NUMERIC to avoid float drift over a years horizon';
COMMENT ON COLUMN net_worth_snapshots.currency  IS 'Denomination of net_worth (USD for the aggregate bot total)';
COMMENT ON COLUMN net_worth_snapshots.venue     IS 'Optional venue/exchange for a per-venue row; NULL for a bot-level total';
COMMENT ON COLUMN net_worth_snapshots.source    IS 'Row writer/provenance: bot_status (spawner sampler) | onchain (future xpub watcher) | bot_status_stale (bot_status re-labelled by 015, never written directly — excluded by readers)';

-- =============================================================================
-- Indexes
-- =============================================================================

-- Primary access pattern: one bot's history, newest first (the panel query).
CREATE INDEX IF NOT EXISTS idx_net_worth_snapshots_bot_ts
    ON net_worth_snapshots (bot_id, ts DESC);

-- Cross-bot time-range scans (total-net-worth-over-time roll-ups).
CREATE INDEX IF NOT EXISTS idx_net_worth_snapshots_ts
    ON net_worth_snapshots (ts DESC);

-- =============================================================================
-- Privileges
-- =============================================================================

GRANT ALL PRIVILEGES ON ALL TABLES    IN SCHEMA public TO :fks_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO :fks_user;
