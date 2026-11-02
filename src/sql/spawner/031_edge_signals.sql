-- =============================================================================
-- 031_edge_signals.sql — the signal ledger: what a deployment told the trader
-- =============================================================================
-- EDGE_PROCESS §6. On a prop account execution is manual (018 refuses
-- 'auto'), so "live" for an orb edge is a signal runner (fks-spawner
-- EDGE_RUNNER=signal): it watches the real-time feed, re-runs the searched
-- code on the session so far, and tells the trader when the range is set,
-- when to enter and when to get out. Every message it sends is a row here,
-- written BEFORE it is sent:
--
--   • one row per deployment, session, symbol and kind (range, entry, exit):
--     a runner that restarts mid-session finds what it already said and
--     doesn't say it twice;
--   • only while the deployment is forward (marked paper) or live, for a
--     symbol it trades, on a session no later than today (UTC);
--   • append-only, except delivered_at, set once when the message went out:
--     a row without it is a signal the trader may never have seen;
--   • the code version that produced it, like the forward ledger.
--
-- What the trader then did (fills, from the broker) is not here: comparing
-- fills with these rows is the live rung's execution check, still to come.
--
-- Grants: the research role (the runner) reads, inserts and sets
-- delivered_at. Idempotent. Prerequisites: 018, 025, 029.
-- =============================================================================

\getenv fks_db RUBY_DB

\connect :fks_db

CREATE TABLE IF NOT EXISTS edge_signals (
    id             BIGSERIAL   PRIMARY KEY,
    deployment_id  BIGINT      NOT NULL REFERENCES edge_deployments (id) ON DELETE RESTRICT,
    session_date   DATE        NOT NULL,
    symbol         TEXT        NOT NULL,
    -- range: the opening range is set; entry: enter now; exit: get out now.
    kind           TEXT        NOT NULL,
    -- The deployment's stage when it was said (set by the database).
    stage          TEXT        NOT NULL,
    contract       TEXT        NOT NULL,
    side           SMALLINT,
    price          DOUBLE PRECISION,
    stop           DOUBLE PRECISION,
    target         DOUBLE PRECISION,
    -- The bar it was decided on (its start, UTC).
    bar_at         TIMESTAMPTZ NOT NULL,
    reason         TEXT        NOT NULL,
    runner         TEXT        NOT NULL,
    code_version   TEXT        NOT NULL,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    delivered_at   TIMESTAMPTZ,

    CONSTRAINT edge_signals_once UNIQUE (deployment_id, session_date, symbol, kind),
    CONSTRAINT edge_signals_kind_known CHECK (kind IN ('range', 'entry', 'exit')),
    CONSTRAINT edge_signals_stage_known CHECK (stage IN ('forward', 'live')),
    CONSTRAINT edge_signals_side_known CHECK (side IS NULL OR side IN (-1, 1)),
    CONSTRAINT edge_signals_trade_has_side CHECK (kind = 'range' OR (side IS NOT NULL AND price IS NOT NULL)),
    CONSTRAINT edge_signals_named CHECK (length(btrim(runner)) > 0 AND length(btrim(code_version)) > 0
                                         AND length(btrim(contract)) > 0)
);

CREATE OR REPLACE FUNCTION edge_signals_admit()
RETURNS TRIGGER AS $$
DECLARE
    v_stage  TEXT;
    v_symbol TEXT;
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'signal % was said and is never deleted', OLD.id
            USING ERRCODE = 'check_violation';
    END IF;
    IF TG_OP = 'UPDATE' THEN
        IF (to_jsonb(NEW) - 'delivered_at') IS DISTINCT FROM (to_jsonb(OLD) - 'delivered_at')
           OR (OLD.delivered_at IS NOT NULL AND NEW.delivered_at IS DISTINCT FROM OLD.delivered_at) THEN
            RAISE EXCEPTION 'signal % is kept as said: only delivered_at is set, once', OLD.id
                USING ERRCODE = 'check_violation';
        END IF;
        RETURN NEW;
    END IF;
    SELECT stage, symbol INTO v_stage, v_symbol FROM edge_deployments WHERE id = NEW.deployment_id;
    IF v_stage IS NULL OR v_stage NOT IN ('forward', 'live') THEN
        RAISE EXCEPTION 'deployment % is at stage %: signals come only from a forward or live deployment',
            NEW.deployment_id, COALESCE(v_stage, '<missing>')
            USING ERRCODE = 'check_violation';
    END IF;
    IF NOT (NEW.symbol = ANY (string_to_array(v_symbol, '+'))) THEN
        RAISE EXCEPTION 'deployment % trades %, not %', NEW.deployment_id, v_symbol, NEW.symbol
            USING ERRCODE = 'check_violation';
    END IF;
    IF NEW.session_date > (now() AT TIME ZONE 'UTC')::DATE THEN
        RAISE EXCEPTION 'session % hasn''t started', NEW.session_date
            USING ERRCODE = 'check_violation';
    END IF;
    NEW.stage := v_stage;
    NEW.created_at := now();
    NEW.delivered_at := NULL;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_edge_signals_admit ON edge_signals;
CREATE TRIGGER trg_edge_signals_admit
    BEFORE INSERT OR UPDATE OR DELETE ON edge_signals
    FOR EACH ROW EXECUTE FUNCTION edge_signals_admit();

COMMENT ON TABLE edge_signals IS
    'What a signal runner told the trader (031): one row per deployment, session, symbol and '
    'kind, written before it is sent; delivered_at once it went out.';

GRANT SELECT, INSERT ON edge_signals TO fks_backtest;
GRANT UPDATE (delivered_at) ON edge_signals TO fks_backtest;
GRANT USAGE ON SEQUENCE edge_signals_id_seq TO fks_backtest;
