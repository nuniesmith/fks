-- ============================================================================
-- 016_rithmic_accounts.sql — multiple Rithmic logins, categorised by JOB
-- ============================================================================
-- WHY. `exchange_secrets` is keyed by `exchange` as its PRIMARY KEY: exactly
-- one row per exchange name, so exactly one Rithmic login could ever be stored.
-- The operator needs several at once — a DATA-only login that streams
-- GC/NQ/ES continuously, plus one or more prop-firm TRADING logins — because
-- Rithmic permits only ONE session per credential, and today the platform and
-- R|Trader Pro fight over a single one every trading day.
--
-- CREDENTIALS DO NOT LIVE HERE. This table is metadata only. The username and
-- password stay in `exchange_secrets` under the key `rithmic:<id>`, which
-- reuses the spawner's existing ChaCha20-Poly1305 encryption-at-rest and its
-- never-return-the-secret read path unchanged. Splitting them this way means a
-- SELECT on this table — for a settings page, a status panel, an audit — can
-- never expose a secret, and no new decryption path had to be written.
--
-- THE STAGE-2 FIELDS ARE MODELLED BUT INERT. `role = 'copytrade'` describes an
-- account the operator intends to mirror trades onto. NOTHING in the platform
-- can place an order today: the Rithmic connector holds `read_only = true` and
-- `order_plant_open = false` as constants, asserted in its tests, with no
-- order-entry code path anywhere. Storing the intent now keeps the schema
-- stable when that capability is built behind its own arming gate; it does not
-- grant it.
-- ============================================================================

CREATE TABLE IF NOT EXISTS rithmic_accounts (
    -- Operator-chosen slug, also the `exchange_secrets` key suffix
    -- (`rithmic:<id>`). Stable: renaming would orphan the credential.
    id                  TEXT PRIMARY KEY,
    label               TEXT NOT NULL,

    -- WHAT THIS LOGIN IS FOR. The whole point of the table: a data feed and a
    -- funded prop account are different jobs with different risk, and mixing
    -- them is how a streaming reconnect ends up contending with the session
    -- holding real positions.
    kind                TEXT NOT NULL CHECK (kind IN ('data', 'trading')),

    -- Disabled by default. A credential that is merely PRESENT must never be
    -- connected on the strength of having been typed in — enabling is a
    -- separate, deliberate act.
    enabled             BOOLEAN NOT NULL DEFAULT FALSE,

    -- 'main'      = the ONE account the operator trades by hand.
    -- 'copytrade' = mirrors the main account (Stage 2; inert today).
    -- The trading page shows only 'main', so a copytrade account can never be
    -- picked up and hand-traded by mistake.
    role                TEXT CHECK (role IN ('main', 'copytrade')),

    -- Prop-firm lifecycle. Drives which rule set and payout split apply:
    -- TakeProfit Trader PRO pays 80%, PRO+ 90%, and PRO+ drops the buffer-zone
    -- requirement — so this is not cosmetic, it changes the numbers shown.
    stage               TEXT CHECK (stage IN ('test', 'pro', 'pro_plus')),

    -- Rithmic routing identifiers. Without the account triple the connector
    -- SKIPS positions silently, so these belong with the account, not in a
    -- global env var that can only ever describe one of them.
    system_name         TEXT,
    fcm_id              TEXT,
    ib_id               TEXT,
    account_id          TEXT,

    -- Prop-firm parameters, per account, because they differ per account and
    -- per stage. NUMERIC (not float) — these are money and are compared against
    -- a liquidation threshold.
    starting_balance    NUMERIC(14, 2),
    profit_target       NUMERIC(14, 2),
    -- The hard rule: touching this balance, INCLUDING on unrealised loss,
    -- liquidates the account immediately. It TRAILS, so it is stored as the
    -- current absolute figure and updated as the firm moves it — never derived
    -- from a stale starting balance.
    min_account_balance NUMERIC(14, 2),
    max_contracts       INTEGER CHECK (max_contracts IS NULL OR max_contracts > 0),

    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- A data feed has no trading role and no prop-firm stage. Letting those be
    -- set on a data login invites a UI that reads them back and renders a
    -- profit target for a credential that cannot hold a position.
    CONSTRAINT rithmic_accounts_data_has_no_trading_fields
        CHECK (kind = 'trading' OR (role IS NULL AND stage IS NULL)),

    -- Conversely a trading login MUST declare whether it is the hand-traded
    -- account or a mirror. NULL here would be a third, undefined state that
    -- every consumer would have to guess at.
    CONSTRAINT rithmic_accounts_trading_has_role
        CHECK (kind = 'data' OR role IS NOT NULL)
);

-- EXACTLY ONE ENABLED 'main', ENFORCED BY THE DATABASE.
--
-- "There should only be one Rithmic account I can manually trade with" is the
-- operator's rule, and it is enforced here rather than in the UI because the UI
-- is not the only writer — an API call, a migration, or a hand-run UPDATE would
-- all bypass a form-level check. A partial unique index makes a second enabled
-- main a constraint violation at the moment of the write.
--
-- Scoped to `enabled` deliberately: keeping several DISABLED mains on file is
-- how the operator switches which account is live without deleting the others.
CREATE UNIQUE INDEX IF NOT EXISTS rithmic_accounts_one_enabled_main
    ON rithmic_accounts ((role))
    WHERE role = 'main' AND enabled;

-- The connector asks "which logins should I open?" on every start; both
-- lookups are by (kind, enabled).
CREATE INDEX IF NOT EXISTS rithmic_accounts_kind_enabled
    ON rithmic_accounts (kind, enabled);

CREATE TRIGGER trg_rithmic_accounts_updated_at
    BEFORE UPDATE ON rithmic_accounts
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

GRANT SELECT, INSERT, UPDATE, DELETE ON rithmic_accounts TO fks_user;
