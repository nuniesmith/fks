-- =============================================================================
-- 003-secrets.sql — Exchange API credential storage (WebUI Phase E)
-- =============================================================================
-- Creates the exchange_secrets table in ruby_db. Owned by the fks_bot_spawner
-- service (crates/spawner/), which exposes:
--   POST /secrets         — store/UPSERT credentials for one exchange
--   GET  /secrets/status  — which exchanges are configured (never the secrets)
--
-- SECURITY MODEL (see docs/architecture/WEBUI_BUILDOUT_PLAN.md, Phase E):
--   • The WebUI browser only ever SUBMITS credentials; they are never read back.
--   • Every spawner route is gated by X-Internal-Token (set by nginx); the whole
--     stack is internal / Tailscale-only with no external ports.
--   • Storage is plaintext-at-rest for now — column-level encryption (pgcrypto)
--     is a tracked follow-up. Keys unlock the authenticated/live order path
--     (exchange-apiws), which stays behind the manual execution gate. Default
--     operation is keyless/public.
--
-- Prerequisites:
--   • 001_init.sql     — creates the database + uuid-ossp.
--   • 002_spawner.sql  — defines the shared set_updated_at() trigger function,
--                        reused here. (Init scripts run in lexicographic order,
--                        so 25-spawner.sql lands before 26-secrets.sql.)
--
-- Idempotent — safe to re-run (CREATE TABLE IF NOT EXISTS, DROP TRIGGER IF EXISTS).
--
-- Manual execution (existing volumes skip initdb — apply by hand once):
--   docker compose exec postgres \
--     psql -U fks_user -d ruby_db -f /docker-entrypoint-initdb.d/26-secrets.sql
-- =============================================================================

\getenv fks_user  POSTGRES_USER
\getenv ruby_db   RUBY_DB

\connect :ruby_db

-- =============================================================================
-- exchange_secrets — one row per exchange (kraken, kucoin, binance, …)
-- =============================================================================
-- The exchange name is the primary key, so re-submitting credentials for an
-- exchange UPSERTs (overwrites) rather than duplicating. api_passphrase is
-- nullable — only some exchanges (KuCoin, Coinbase) require it; Kraken/Binance
-- leave it NULL.
-- =============================================================================

CREATE TABLE IF NOT EXISTS exchange_secrets (
    -- Exchange identifier, lowercased by the spawner (e.g. 'kraken', 'kucoin').
    exchange        TEXT        PRIMARY KEY,

    -- API key (public part) + secret (private part). Stored server-side only;
    -- api_secret is never selected by the status endpoint.
    api_key         TEXT        NOT NULL,
    api_secret      TEXT        NOT NULL,

    -- Optional passphrase (KuCoin / Coinbase). NULL for Kraken / Binance.
    api_passphrase  TEXT,

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE  exchange_secrets                IS 'Exchange API credentials for the authenticated/live order path (exchange-apiws). Submitted via the WebUI, stored server-side, never returned to the browser.';
COMMENT ON COLUMN exchange_secrets.exchange       IS 'Lowercased exchange id; primary key so re-submission UPSERTs';
COMMENT ON COLUMN exchange_secrets.api_secret     IS 'Private secret — never selected by GET /secrets/status';
COMMENT ON COLUMN exchange_secrets.api_passphrase IS 'Optional passphrase (KuCoin/Coinbase); NULL otherwise';

-- Stamp updated_at on every change. Reuses set_updated_at() from 002_spawner.sql.
DROP TRIGGER IF EXISTS trg_exchange_secrets_updated_at ON exchange_secrets;
CREATE TRIGGER trg_exchange_secrets_updated_at
    BEFORE UPDATE ON exchange_secrets
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- =============================================================================
-- Privileges
-- =============================================================================

GRANT ALL PRIVILEGES ON ALL TABLES    IN SCHEMA public TO :fks_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO :fks_user;
