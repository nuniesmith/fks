-- =============================================================================
-- 027_webui_api_tokens.sql — WebUI personal access tokens (API v1) + grants
-- =============================================================================
-- fks-web's API v1 (EDGE_FACTORY_PLAN §7.2): a signed-in user mints a token on
-- Settings → API tokens, and an agent or script sends it as
-- `Authorization: Bearer fks_pat_…`. The webui resolves it to the owner at
-- min(owner's current role, role_cap).
--
-- DESIGN POINTS:
--   • token_hash only — the raw token is shown once, at mint (same discipline
--     as webui_sessions / webui_invites).
--   • role_cap CHECK excludes 'admin' — no admin tokens. Everything admin-only
--     (keys, webhooks, users, a spawn or promotion that could trade real
--     money) needs a human session (§6.3: no PAT arms money).
--   • expires_at is NOT NULL — every token expires (the service sets it).
--   • ON DELETE CASCADE with the user; revocation is revoked_at, never DELETE
--     (the rows are audit history).
--
-- The CREATE TABLE block is kept BYTE-IDENTICAL to fks-web's
-- src/lib/server/auth/schema.sql tokens block. Unlike invites, this table is
-- OPTIONAL to the webui: if it is missing on the scoped role, tokens are off
-- and login is unaffected.
--
-- Idempotent — safe to re-run and safe to apply BY HAND to the live database
-- (fks-migrate applies it on deploy; baked initdb scripts only run on an
-- EMPTY volume).
--
-- Prerequisites:
--   • 001_init.sql — creates the database (RUBY_DB env, fks_db).
--   • 010_webui_auth.sql — creates webui_users + the fks_webui role.
-- =============================================================================

\getenv fks_db RUBY_DB

\connect :fks_db

CREATE TABLE IF NOT EXISTS webui_api_tokens (
    id           BIGSERIAL PRIMARY KEY,
    user_id      BIGINT NOT NULL REFERENCES webui_users(id) ON DELETE CASCADE,
    name         TEXT NOT NULL,
    token_hash   TEXT NOT NULL UNIQUE,         -- sha256(token); raw token shown once, at mint
    role_cap     TEXT NOT NULL DEFAULT 'viewer'
                 CHECK (role_cap IN ('operator','viewer')),  -- no admin tokens
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at   TIMESTAMPTZ NOT NULL,         -- service sets now()+TTL at mint
    last_used_at TIMESTAMPTZ,
    revoked_at   TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS webui_api_tokens_user_idx ON webui_api_tokens (user_id);

-- ---------------------------------------------------------------------------
-- Privileges: the webui mints (INSERT), resolves and lists (SELECT), and
-- revokes / stamps last use (UPDATE). No DELETE. Sequence granted BY NAME
-- (auth-chain L2 rule).
-- ---------------------------------------------------------------------------
GRANT SELECT, INSERT, UPDATE ON webui_api_tokens TO fks_webui;
GRANT USAGE, SELECT ON SEQUENCE webui_api_tokens_id_seq TO fks_webui;
