-- =============================================================================
-- 012-webui_invites.sql — WebUI one-time invite links + fks_webui grants
-- =============================================================================
-- Companion wiring for the fks-web invite flow (webui plan 01 Phase C): an
-- admin mints a single-use signup URL with a role; the invitee sets their own
-- credentials on first use. No email, ever — the URL is handed over out-of-band.
--
-- DESIGN POINTS:
--   • token_hash only — the raw token exists once, in the URL the admin copies.
--     sha256 at rest, same discipline as webui_sessions.
--   • role CHECK excludes 'admin' — no admin-by-invite (plan OD-5): admin
--     creation stays a deliberate /users act (or psql).
--   • Single-use is enforced ATOMICALLY in the webui (UPDATE … WHERE
--     redeemed_at IS NULL AND revoked_at IS NULL RETURNING …) — two concurrent
--     claims yield exactly one user.
--   • expires_at is set by the service (default now()+48h at mint time).
--
-- The CREATE TABLE block is kept BYTE-IDENTICAL to fks-web's
-- src/lib/server/auth/schema.sql invites block (the webui probes to_regclass
-- for THIS table — the newest — so additive migrations run on privileged dev
-- DBs; on the scoped live role the table must pre-exist via this script).
--
-- Idempotent — safe to re-run and safe to apply BY HAND to the live, non-empty
-- database (baked initdb scripts only run on an EMPTY volume).
--
-- Prerequisites:
--   • 001_init.sql — creates the database (RUBY_DB env, fks_db).
--   • 010_webui_auth.sql — creates webui_users + the fks_webui role.
--
-- Manual execution (existing volumes skip initdb — apply by hand once):
--   docker exec -i fks_postgres \
--     sh -c 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d postgres' \
--     < src/sql/spawner/012_webui_invites.sql
-- =============================================================================

\getenv fks_db RUBY_DB

\connect :fks_db

-- ---------------------------------------------------------------------------
-- Schema (BYTE-IDENTICAL to the fks-web invites schema block). Created as the
-- privileged initdb user (owner = fks_user), so the scoped fks_webui role
-- never needs CREATE.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS webui_invites (
    id          BIGSERIAL PRIMARY KEY,
    token_hash  TEXT NOT NULL UNIQUE,          -- sha256(token); raw token only in the URL, once
    role        TEXT NOT NULL DEFAULT 'viewer'
                CHECK (role IN ('operator','viewer')),  -- no admin-by-invite
    created_by  BIGINT NOT NULL REFERENCES webui_users(id),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at  TIMESTAMPTZ NOT NULL,          -- service sets now()+TTL at mint
    redeemed_by BIGINT REFERENCES webui_users(id),
    redeemed_at TIMESTAMPTZ,
    revoked_at  TIMESTAMPTZ
);

-- ---------------------------------------------------------------------------
-- Privileges: the webui mints (INSERT), lists (SELECT), and redeems/revokes
-- (UPDATE) invites. No DELETE — expired/redeemed/revoked rows are audit
-- history. Sequence granted BY NAME (auth-chain L2 rule).
-- ---------------------------------------------------------------------------
GRANT SELECT, INSERT, UPDATE ON webui_invites TO fks_webui;
GRANT USAGE, SELECT ON SEQUENCE webui_invites_id_seq TO fks_webui;
