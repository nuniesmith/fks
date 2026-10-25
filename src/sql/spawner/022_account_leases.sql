-- =============================================================================
-- 022_account_leases.sql — one live bot per exchange account
--
-- The spawner's account-lease table (fks-spawner crate::leases): a bot that
-- declares an `account` (e.g. "kraken:spot:default") may only be spawned
-- while the spawner holds that account's lease, and a second bot declaring
-- the same account is refused while the lease is live.
--
-- `account` is the PRIMARY KEY on purpose: the uniqueness the whole guard
-- rests on is enforced by the schema, not by application care. `bot_id` is
-- the current holder; `container_id` is stamped once the holder's container
-- exists so stop/remove can release exactly that run's lease. `expires_at`
-- is the liveness deadline — the spawner heartbeats it forward for bots
-- Docker reports running, and a crashed/exited bot's lease lapses on its
-- own (default TTL 90s), so a dead holder can never lock an account forever.
--
-- Motivating incident: 2026-10-11 → 10-15 two bots traded the same Kraken
-- account for four days because nothing anywhere modelled one-account-one-
-- trader (EDGE_FACTORY_PLAN §6.3).
-- =============================================================================

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
