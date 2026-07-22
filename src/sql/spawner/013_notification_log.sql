-- =============================================================================
-- 013-notification_log.sql — Discord-notification delivery ledger (spawner)
-- =============================================================================
-- Companion wiring for the fks-spawner notification ledger (webui plan 03
-- Phase B): every webhook delivery attempt — real events and test probes —
-- gets a row, so "did the crash page actually send at 3am?" is answerable
-- from the webui instead of docker logs.
--
-- DESIGN POINTS:
--   • detail NEVER contains the webhook URL (the dispatcher's no-URL-logging
--     contract extends to this table); it is a truncated (≤512) event snippet.
--   • outcome is CHECK-bounded to the dispatcher's arms: sent / http_error /
--     send_failed / decrypt_failed / test_sent / test_failed.
--   • Ledger writes are best-effort + off-path in the spawner (a ledger
--     failure must never delay or fail a webhook send).
--   • RETENTION: pruned by the spawner (prune beyond newest N, default 5000)
--     riding the net-worth sampler tick — deliberately NOT a SQL job.
--
-- Owned/written by the spawner's full-access fks_user role (the same one that
-- owns notification_channels) — no new role grants needed.
--
-- Idempotent — safe to re-run and safe to apply BY HAND to the live, non-empty
-- database (baked initdb scripts only run on an EMPTY volume).
--
-- Prerequisites:
--   • 001_init.sql — creates the database (RUBY_DB env, fks_db).
--
-- Manual execution (existing volumes skip initdb — apply by hand once):
--   docker exec -i fks_postgres \
--     sh -c 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d postgres' \
--     < src/sql/spawner/013_notification_log.sql
-- =============================================================================

\getenv fks_db RUBY_DB

\connect :fks_db

CREATE TABLE IF NOT EXISTS notification_log (
    id           BIGSERIAL PRIMARY KEY,
    ts           TIMESTAMPTZ NOT NULL DEFAULT now(),
    event        TEXT NOT NULL,             -- wire kind (bot_spawned, bot_crashed, …)
    bot_id       TEXT NOT NULL DEFAULT '',
    channel_name TEXT NOT NULL,             -- notification_channels.name at send time
    kind         TEXT NOT NULL,             -- transport (discord_webhook)
    outcome      TEXT NOT NULL CHECK (outcome IN
                 ('sent','http_error','send_failed','decrypt_failed',
                  'test_sent','test_failed')),
    status_code  SMALLINT,                  -- HTTP status when one was received
    detail       TEXT NOT NULL DEFAULT ''   -- truncated event snippet; NEVER the URL
);

CREATE INDEX IF NOT EXISTS notification_log_ts_idx
    ON notification_log (ts DESC);
CREATE INDEX IF NOT EXISTS notification_log_event_ts_idx
    ON notification_log (event, ts DESC);
