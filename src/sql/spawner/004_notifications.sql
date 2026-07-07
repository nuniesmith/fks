-- =============================================================================
-- 004-notifications.sql — Operator-configured notification channels
-- =============================================================================
-- Creates the notification_channels table in ruby_db. Owned by the
-- fks_bot_spawner service (crates/spawner/), which exposes:
--   POST   /notifications        — create/UPSERT a channel (by name)
--   GET    /notifications        — which channels exist (name/kind/events;
--                                  NEVER the target URL)
--   DELETE /notifications/{name} — remove one channel (hard delete)
--
-- WHY A SEPARATE TABLE (not a `kind` column on exchange_secrets):
--   The roadmap (§5.1) sketches a longer-term unified, `kind`-aware secret
--   store with a v2 `{ name, kind, fields }` API. That is a bigger, breaking
--   refactor (relax the NOT NULL key/secret columns, migrate the 3 legacy
--   columns behind a read-compat shim, per-kind validation). This PR is the
--   *additive, zero-risk* slice that unblocks notifications: a new table that
--   models a channel as its own entity (name + kind + encrypted target +
--   events) and reuses the exact exchange_secrets patterns (same cipher, same
--   X-Internal-Token gating, same graceful-without-DB behaviour). The
--   exchange_secrets contract and its UI are untouched.
--
-- SECURITY MODEL (mirrors exchange_secrets / 003_secrets.sql):
--   • The WebUI browser only ever SUBMITS a channel; the target URL is never
--     read back (GET returns name/kind/events only).
--   • Every spawner route is gated by X-Internal-Token (set by nginx); the
--     stack is internal / Tailscale-only.
--   • The `target` URL is ENCRYPTED at rest with the SAME app-layer
--     ChaCha20-Poly1305 cipher as exchange keys (SPAWNER_SECRETS_KEY): a
--     Discord webhook URL is a bearer capability — anyone holding it can post
--     to the channel — so it is treated as a secret. Stored form is
--     `enc:v1:<base64 nonce+ciphertext>`; legacy plaintext rows read back
--     transparently. An invalid/missing key disables the store (fail-safe).
--
-- BOUNDARY: this migration + the spawner routes are the STORE + management API
--   only. Actually SENDING notifications (a notifier task / bots / janus
--   reading channels and POSTing to Discord) is a consumer-side follow-up.
--
-- Prerequisites:
--   • 001_init.sql     — creates the database + uuid-ossp.
--   • 002_spawner.sql  — defines the shared set_updated_at() trigger function,
--                        reused here.
--
-- Idempotent — safe to re-run (CREATE TABLE IF NOT EXISTS, DROP TRIGGER IF EXISTS).
--
-- Manual execution (existing volumes skip initdb — apply by hand once):
--   docker compose exec postgres \
--     psql -U fks_user -d ruby_db -f /docker-entrypoint-initdb.d/27-notifications.sql
-- =============================================================================

\getenv fks_user  POSTGRES_USER
\getenv ruby_db   RUBY_DB

\connect :ruby_db

-- =============================================================================
-- notification_channels — one row per operator-configured channel
-- =============================================================================
-- The channel name is the primary key, so re-submitting a channel with the
-- same name UPSERTs (overwrites) rather than duplicating. `kind` classifies the
-- transport ('discord_webhook' today; Slack/Telegram/generic-webhook later).
-- `events` is a JSONB array of event names the channel subscribes to; an EMPTY
-- array is the catch-all ("send everything"). `target` is the encrypted URL.
-- =============================================================================

CREATE TABLE IF NOT EXISTS notification_channels (
    -- Operator-chosen channel name (e.g. 'ops-alerts'). Primary key so
    -- re-submission UPSERTs.
    name        TEXT        PRIMARY KEY,

    -- Transport kind. 'discord_webhook' today; future: 'slack_webhook',
    -- 'telegram', 'generic_webhook'. Validated at the API layer.
    kind        TEXT        NOT NULL DEFAULT 'discord_webhook',

    -- The webhook URL — ENCRYPTED at rest (never selected by GET). A Discord
    -- webhook URL is a bearer capability, so it is stored like a secret.
    target      TEXT        NOT NULL,

    -- Subscribed event names as a JSONB array. Empty array = catch-all.
    -- e.g. ["spawn","stop","live_flip","pnl_digest"].
    events      JSONB       NOT NULL DEFAULT '[]'::jsonb,

    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE  notification_channels        IS 'Operator-configured notification channels (Discord webhooks, …). Submitted via the WebUI, target URL stored encrypted server-side, never returned to the browser.';
COMMENT ON COLUMN notification_channels.name   IS 'Operator-chosen channel name; primary key so re-submission UPSERTs';
COMMENT ON COLUMN notification_channels.kind   IS 'Transport kind: discord_webhook (today), slack_webhook/telegram/generic_webhook (future)';
COMMENT ON COLUMN notification_channels.target IS 'Webhook URL — encrypted at rest (ChaCha20-Poly1305); never selected by GET /notifications';
COMMENT ON COLUMN notification_channels.events IS 'JSONB array of subscribed event names; empty array = catch-all (send everything)';

-- Stamp updated_at on every change. Reuses set_updated_at() from 002_spawner.sql.
DROP TRIGGER IF EXISTS trg_notification_channels_updated_at ON notification_channels;
CREATE TRIGGER trg_notification_channels_updated_at
    BEFORE UPDATE ON notification_channels
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- =============================================================================
-- Privileges
-- =============================================================================

GRANT ALL PRIVILEGES ON ALL TABLES    IN SCHEMA public TO :fks_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO :fks_user;
