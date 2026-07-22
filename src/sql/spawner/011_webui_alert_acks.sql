-- =============================================================================
-- 011-webui_alert_acks.sql — WebUI alert-ack inbox table + fks_webui grants
-- =============================================================================
-- Companion wiring for the fks-web alert-ack inbox (webui plan 04 Phase B):
-- a fired armed-path alert (halt / breaker / stop-divergence / silent-stall)
-- can be acknowledged by a named operator; acked incidents stop re-showing.
--
-- INCIDENT IDENTITY (the core design point): Prometheus /api/v1/alerts gives
-- labels + activeAt. alert_key = sha256(canonical-json(labels) + "|" + activeAt)
-- — a resolved alert that RE-FIRES gets a new activeAt → a NEW incident →
-- re-shows unacked. Acking can never permanently silence an alertname.
--
-- THE TABLE IS THE AUDIT: append-only in practice. UNIQUE(alert_key) makes ack
-- idempotent (double-ack returns the existing row). fks_webui deliberately gets
-- NO UPDATE/DELETE — acks are irrevocable rows (an "un-ack" would be a new
-- design decision, plan 04 OD-2). Retention sweeps are equally deliberate
-- non-goals: rows for incidents no longer firing are harmless history.
--
-- The CREATE TABLE block is kept BYTE-IDENTICAL to fks-web's
-- src/lib/server/alertAck/schema.sql (the webui probes to_regclass and reports
-- configured:false when the table is missing — an ack-store outage must never
-- hide a live alert, so the inbox degrades to read-only, never crashes).
--
-- Idempotent — safe to re-run and safe to apply BY HAND to the live, non-empty
-- database (baked initdb scripts only run on an EMPTY volume).
--
-- Prerequisites:
--   • 001_init.sql — creates fks_db.
--   • 010_webui_auth.sql — creates the fks_webui role this script GRANTs to.
--
-- Manual execution (existing volumes skip initdb — apply by hand once):
--   docker exec -i fks_postgres \
--     sh -c 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d postgres' \
--     < src/sql/spawner/011_webui_alert_acks.sql
-- =============================================================================

\getenv fks_db RUBY_DB

\connect :fks_db

-- ---------------------------------------------------------------------------
-- Schema (BYTE-IDENTICAL to fks-web src/lib/server/alertAck/schema.sql).
-- Created as the privileged initdb user (owner = fks_user), so the scoped
-- fks_webui role never needs CREATE.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS webui_alert_acks (
    id          BIGSERIAL PRIMARY KEY,
    alert_key   TEXT NOT NULL UNIQUE,      -- sha256(canonical labels + "|" + activeAt)
    alertname   TEXT NOT NULL,             -- denormalized for the audit view
    labels      JSONB NOT NULL,
    active_at   TIMESTAMPTZ NOT NULL,
    acked_by    TEXT NOT NULL,             -- session username (operatorName idiom)
    acked_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    note        TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS webui_alert_acks_alertname_idx
    ON webui_alert_acks (alertname);

-- ---------------------------------------------------------------------------
-- Minimal privileges: SELECT + INSERT only (no UPDATE/DELETE — irrevocable
-- audit rows, see header). Sequence grant BY NAME per the auth-chain L2 rule
-- (never "ALL SEQUENCES IN SCHEMA public").
-- ---------------------------------------------------------------------------
GRANT SELECT, INSERT ON webui_alert_acks TO fks_webui;
GRANT USAGE, SELECT ON SEQUENCE webui_alert_acks_id_seq TO fks_webui;
