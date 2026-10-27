-- =============================================================================
-- 026_channel_platform_events.sql — a bot's own notification channel
-- =============================================================================
-- A saved bot config can take a webhook from Settings -> Notifications
-- (fks-spawner `webhooks: {ENV_VAR: channel}`): the channel's URL is set in
-- the bot's env at every spawn, encrypted at rest, never in GitHub or .env.
-- Such a channel is usually the bot's own (the crypto bot's #crypto reports),
-- and must not also receive every bot's lifecycle events from the
-- dispatcher. platform_events = FALSE says so; the dispatcher then sends it
-- nothing, not even the always-delivered kinds.
--
-- Default TRUE: every existing channel keeps receiving what it did.
-- Idempotent.
-- =============================================================================

\getenv fks_db   RUBY_DB

\connect :fks_db

ALTER TABLE notification_channels
    ADD COLUMN IF NOT EXISTS platform_events BOOLEAN NOT NULL DEFAULT TRUE;

COMMENT ON COLUMN notification_channels.platform_events IS
    'FALSE: a bot''s own channel (its webhook set at spawn); the dispatcher sends it no '
    'platform events.';
