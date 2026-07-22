-- =============================================================================
-- 010-webui_auth.sql — WebUI Phase-1 user-management schema + scoped LOGIN role
-- =============================================================================
-- Companion wiring for fks-web #47 (auth-chain H7). The webui now fail-closes
-- when its auth store is unreachable: a bare WEB_COMMIT repin with no schema +
-- role bricks every page 503. This bakes the schema + the scoped fks_webui role
-- into the fresh-host initdb path so a volume-loss / new-host bootstrap comes up
-- auth-ready, and documents the by-hand apply for the existing live volume.
--
-- SCHEMA (design §4.1): three tables in fks_db —
--   • webui_users        — accounts (scrypt hash, role, lockout, must-change)
--   • webui_sessions      — opaque-token sessions (sha256 at rest, idle+abs TTL)
--   • webui_auth_audit    — append-only login/rotation audit trail
-- The CREATE TABLE block below is kept BYTE-IDENTICAL to fks-web's
-- src/lib/server/auth/schema.sql (= the SCHEMA_SQL constant in schema.ts). The
-- webui's PgStore.init also runs this DDL at startup, guarded by a to_regclass
-- probe (pgStore.ts) — so the scoped role (no CREATE) never attempts a doomed
-- migration; the tables must pre-exist, which is exactly what this script does.
--
-- ROLE (009 pattern): fks_webui is the LOGIN role the webui connects as
-- (WEBUI_DATABASE_URL), NOT the spawner's full-access fks_user. It gets, and
-- ONLY gets:
--   • CONNECT on fks_db + USAGE on schema public
--   • SELECT,INSERT,UPDATE,DELETE on the three webui_* tables
--   • USAGE,SELECT on the three webui_*_id_seq sequences ONLY
--
-- Deliberately NOT granted: exchange_secrets, transfers, accounts,
-- net_worth_snapshots, edges, bot_configs, bot_runs, notification_channels,
-- ui_layouts, backtest_runs — nor any other sequence in schema public. The
-- sequence grant is scoped to the three webui sequences by NAME (not
-- "ALL SEQUENCES IN SCHEMA public", which would sweep in every spawner-owned
-- sequence — auth-chain L2). 001_init.sql's ALTER DEFAULT PRIVILEGES targets
-- fks_user only, so future tables/sequences are not auto-granted here either.
--
-- Password comes from the container env var WEBUI_DB_PASSWORD (passed by
-- docker-compose to the postgres service), consumed via psql \getenv — the
-- same mechanism 009_backtest_role.sql uses. Empty/unset WEBUI_DB_PASSWORD →
-- the role is created (grants and all) but keeps NO valid password, so logins
-- fail closed until the script is re-run with the password set — re-running is
-- also how you rotate it.
--
-- Idempotent — safe to re-run and safe to apply BY HAND to the live, non-empty
-- database (baked initdb scripts only run on an EMPTY volume): CREATE TABLE IF
-- NOT EXISTS, role creation is existence-guarded, ALTER ROLE/GRANT are
-- idempotent.
--
-- Prerequisites:
--   • 001_init.sql — creates fks_db (02-spawner-init.sql, runs first).
--
-- Manual execution (existing volumes skip initdb — apply by hand once, with the
-- password injected into the exec env; -d postgres because role creation is
-- cluster-wide and the script \connects to fks_db itself):
--   docker exec -i -e WEBUI_DB_PASSWORD="$WEBUI_DB_PASSWORD" \
--     fks_postgres sh -c 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d postgres' \
--     < src/sql/spawner/010_webui_auth.sql
-- =============================================================================

\getenv fks_user  POSTGRES_USER
\getenv fks_db   RUBY_DB

-- Default the password to '' so the script also runs where the env var is
-- absent entirely (\getenv leaves the variable untouched when unset).
\set webui_password ''
\getenv webui_password WEBUI_DB_PASSWORD

-- ---------------------------------------------------------------------------
-- Create the role if it does not already exist (CREATE ROLE has no
-- IF NOT EXISTS — the SELECT … \gexec pattern mirrors 009_backtest_role.sql).
-- ---------------------------------------------------------------------------
SELECT 'CREATE ROLE fks_webui WITH LOGIN'
WHERE NOT EXISTS (
    SELECT FROM pg_roles WHERE rolname = 'fks_webui'
)\gexec

-- Set/rotate the password whenever one is provided (skipped when empty, so a
-- password-less bootstrap cannot silently enable empty-password logins).
SELECT format('ALTER ROLE fks_webui WITH LOGIN PASSWORD %L',
              :'webui_password')
WHERE length(:'webui_password') > 0\gexec

GRANT CONNECT ON DATABASE :fks_db TO fks_webui;

\connect :fks_db

-- ---------------------------------------------------------------------------
-- Schema (BYTE-IDENTICAL to fks-web src/lib/server/auth/schema.sql). Created as
-- the privileged initdb user (owner = fks_user), so the scoped fks_webui role
-- never needs CREATE.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS webui_users (
    id            BIGSERIAL PRIMARY KEY,
    username      TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    role          TEXT NOT NULL DEFAULT 'admin'
                  CHECK (role IN ('admin','operator','viewer')),
    must_change_credentials BOOLEAN NOT NULL DEFAULT FALSE,
    disabled      BOOLEAN NOT NULL DEFAULT FALSE,
    failed_logins INT NOT NULL DEFAULT 0,
    locked_until  TIMESTAMPTZ,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS webui_users_username_idx
    ON webui_users (lower(username));

CREATE TABLE IF NOT EXISTS webui_sessions (
    id              BIGSERIAL PRIMARY KEY,
    token_hash      TEXT NOT NULL UNIQUE,
    user_id         BIGINT NOT NULL REFERENCES webui_users(id) ON DELETE CASCADE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    idle_expires_at TIMESTAMPTZ NOT NULL,
    expires_at      TIMESTAMPTZ NOT NULL,
    ip              TEXT NOT NULL DEFAULT '',
    user_agent      TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS webui_sessions_user_idx ON webui_sessions (user_id);

CREATE TABLE IF NOT EXISTS webui_auth_audit (
    id       BIGSERIAL PRIMARY KEY,
    at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    username TEXT NOT NULL,
    action   TEXT NOT NULL,
    ip       TEXT NOT NULL DEFAULT '',
    detail   TEXT NOT NULL DEFAULT ''
);

-- ---------------------------------------------------------------------------
-- Minimal privileges (see header). GRANTs are idempotent.
-- ---------------------------------------------------------------------------
GRANT USAGE ON SCHEMA public TO fks_webui;

GRANT SELECT, INSERT, UPDATE, DELETE ON webui_users       TO fks_webui;
GRANT SELECT, INSERT, UPDATE, DELETE ON webui_sessions    TO fks_webui;
GRANT SELECT, INSERT, UPDATE, DELETE ON webui_auth_audit  TO fks_webui;

-- Sequence USAGE for the BIGSERIAL id columns — scoped to the three webui
-- sequences BY NAME (auth-chain L2: never "ALL SEQUENCES IN SCHEMA public",
-- which would grant nextval/currval over every spawner-owned sequence).
GRANT USAGE, SELECT ON SEQUENCE webui_users_id_seq       TO fks_webui;
GRANT USAGE, SELECT ON SEQUENCE webui_sessions_id_seq    TO fks_webui;
GRANT USAGE, SELECT ON SEQUENCE webui_auth_audit_id_seq  TO fks_webui;
