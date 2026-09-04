-- ============================================================================
-- 019 — let the webui see WHETHER a Rithmic credential exists, and nothing more
-- ============================================================================
-- Migration 016 gave `fks_webui` full CRUD on `rithmic_accounts` but granted it
-- nothing at all on `exchange_secrets`. The Rithmic accounts panel lists
-- accounts with a "has credentials" flag, computed as an EXISTS subquery
-- against `exchange_secrets` — so every load of that panel hit
--
--     permission denied for table exchange_secrets
--
-- and the whole endpoint 502'd. Observed on the live settings page 2026-09-03.
--
-- The store's own comment assumed a missing grant would make the subquery
-- "yield false, which reads as no credential, the safe direction". That is not
-- how Postgres behaves: a privilege failure ABORTS the statement, it does not
-- evaluate to false. The degradation was never reachable. That half is fixed in
-- fks-web; this half grants the access the panel actually needs.
--
-- WHY A COLUMN-LEVEL GRANT. `exchange_secrets` holds ChaCha20-Poly1305
-- ciphertext for every venue credential on the platform. The webui needs to
-- answer exactly one question — "is there a row for this account?" — which
-- touches only the `exchange` key column. Granting SELECT on the TABLE would
-- also hand it api_key/api_secret/api_passphrase, and the only thing standing
-- between that and a leak would be the current text of a query. A column grant
-- makes reading the ciphertext impossible rather than merely unintended, which
-- is the difference between a policy and a control.
--
-- Idempotent: re-running a GRANT that is already held is a no-op.

GRANT SELECT (exchange) ON exchange_secrets TO fks_webui;

-- The spawner's role keeps full access — it is the component that encrypts,
-- decrypts, and injects these at bot-spawn time.
GRANT SELECT, INSERT, UPDATE, DELETE ON exchange_secrets TO fks_user;
