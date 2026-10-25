-- =============================================================================
-- 023_account_leases_fks_db.sql — move account_leases into fks_db
--
-- 022 omitted the \getenv/\connect header every other spawner file
-- carries. fks-migrate applies each file connected to the ENTRY database
-- (POSTGRES_DB — janus_db in the oryx compose) and each file is
-- responsible for connecting to its own database, so 022's CREATE TABLE
-- landed in janus_db while its ledger row was recorded against fks_db.
-- The deploy was green and the ledger agreed; only the table was in the
-- wrong database (found by checking the table, not the ledger,
-- 2026-10-25). The spawner connects to fks_db and would have failed
-- closed on every lease acquire.
--
-- This file therefore runs in two places: it starts in the entry
-- database and drops the stray table 022 left there, then connects to
-- fks_db and creates the table where it belongs. Idempotent like every
-- file here; on a fresh volume the initdb copies of 022+023 net out to
-- the same end state.
-- =============================================================================

-- Still in the entry database (janus_db): drop 022's stray table.
DROP TABLE IF EXISTS account_leases;

\getenv fks_db RUBY_DB
\connect :fks_db

CREATE TABLE IF NOT EXISTS account_leases (
    account      TEXT        PRIMARY KEY,
    bot_id       TEXT        NOT NULL,
    container_id TEXT,
    acquired_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    heartbeat_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at   TIMESTAMPTZ NOT NULL
);

COMMENT ON TABLE account_leases IS
    'Spawner account leases: at most one live bot per exchange account (fks-spawner crate::leases).';
