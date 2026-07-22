-- =============================================================================
-- 005-ui_layouts.sql — Operator-saved WebUI dock layouts
-- =============================================================================
-- Creates the ui_layouts table in fks_db. Owned by the fks_bot_spawner
-- service (crates/spawner/), which exposes:
--   GET    /ui/layouts        — list saved layout names (+ updated_at); NOT the
--                               full layout blobs (keeps the list light)
--   GET    /ui/layouts/{name} — fetch one full layout envelope
--   POST   /ui/layouts        — create/UPSERT a layout (by name)
--   DELETE /ui/layouts/{name} — remove one layout (hard delete)
--
-- WHY: the /workspace dockview host autosaves to the browser's localStorage,
-- which is per-device. This table lets a named layout be saved server-side so
-- the operator's arrangements follow them across browsers/devices (single
-- operator; Tailscale + X-Internal-Token gated — no per-user column needed).
--
-- NOT A SECRET: a dock layout is panel ids + sizes + params (symbols,
-- intervals, PromQL). It carries no credentials, so — unlike
-- notification_channels / exchange_secrets — the `layout` JSONB is stored in
-- PLAINTEXT and IS returned by GET. (Panel params never include secrets; the
-- secret store stays the only place credentials live.)
--
-- Mirrors the bot_configs pattern (002_spawner.sql): name-keyed UPSERT, a
-- JSONB blob column, the shared set_updated_at() trigger, and graceful
-- db-absent behaviour on the spawner side.
--
-- Prerequisites:
--   • 001_init.sql     — creates the database + uuid-ossp.
--   • 002_spawner.sql  — defines the shared set_updated_at() trigger function.
--
-- Idempotent — safe to re-run (CREATE TABLE IF NOT EXISTS, DROP TRIGGER IF EXISTS).
--
-- Manual execution (existing volumes skip initdb — apply by hand once):
--   docker exec -i fks_postgres sh -c \
--     'psql -U "$POSTGRES_USER" -d fks_db' < src/sql/spawner/005_ui_layouts.sql
-- =============================================================================

\getenv fks_user  POSTGRES_USER
\getenv fks_db   RUBY_DB

\connect :fks_db

-- =============================================================================
-- ui_layouts — one row per operator-saved dock layout
-- =============================================================================
-- The layout name is the primary key, so re-saving under the same name UPSERTs
-- (overwrites). `layout` is the versioned envelope the /workspace serializer
-- produces (`{ version, savedAt, layout: <dockview SerializedDockview> }`) —
-- opaque to the DB, validated on the client.
-- =============================================================================

CREATE TABLE IF NOT EXISTS ui_layouts (
    -- Operator-chosen layout name (e.g. 'trading-desk'). Primary key so
    -- re-saving UPSERTs.
    name        TEXT        PRIMARY KEY,

    -- The serialized dockview layout envelope (plaintext JSONB — no secrets).
    layout      JSONB       NOT NULL,

    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE  ui_layouts        IS 'Operator-saved WebUI dock layouts. Named, server-side, so /workspace arrangements follow the operator across devices. Plaintext (no secrets).';
COMMENT ON COLUMN ui_layouts.name   IS 'Operator-chosen layout name; primary key so re-saving UPSERTs';
COMMENT ON COLUMN ui_layouts.layout IS 'Serialized dockview layout envelope (version + savedAt + SerializedDockview); opaque to the DB, validated on the client';

-- Stamp updated_at on every change. Reuses set_updated_at() from 002_spawner.sql.
DROP TRIGGER IF EXISTS trg_ui_layouts_updated_at ON ui_layouts;
CREATE TRIGGER trg_ui_layouts_updated_at
    BEFORE UPDATE ON ui_layouts
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- =============================================================================
-- Privileges
-- =============================================================================

GRANT ALL PRIVILEGES ON ALL TABLES    IN SCHEMA public TO :fks_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO :fks_user;
