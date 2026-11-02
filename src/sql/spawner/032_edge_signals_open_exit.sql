-- =============================================================================
-- 032_edge_signals_open_exit.sql — an open trade's exit is still said after
-- its deployment is retired
-- =============================================================================
-- 031 admits a signal only while the deployment is forward or live. A
-- deployment retired mid-session (by the edge monitor, fks 030, or by hand)
-- with a trade open would then leave the trader holding a position the
-- runner can no longer close: the runner's exit was refused. Now:
--
--   • after a deployment leaves forward/live, an EXIT is still admitted for
--     a session and symbol whose ENTRY is on record (and not yet exited:
--     the unique key allows one exit). It carries the entry's stage, so a
--     paper trade's exit stays paper;
--   • a range or an entry is never admitted once the deployment is
--     retired, and neither is an exit with no entry to close.
--
-- Everything else in 031 is unchanged (re-created whole, marked 032).
-- Idempotent. Prerequisites: 031.
-- =============================================================================

\getenv fks_db RUBY_DB

\connect :fks_db

CREATE OR REPLACE FUNCTION edge_signals_admit()
RETURNS TRIGGER AS $$
DECLARE
    v_stage  TEXT;
    v_symbol TEXT;
    v_entry  TEXT;
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
        -- 032: the exit of a trade already entered is still said.
        IF v_stage IS NOT NULL AND NEW.kind = 'exit' THEN
            SELECT stage INTO v_entry FROM edge_signals
             WHERE deployment_id = NEW.deployment_id AND session_date = NEW.session_date
               AND symbol = NEW.symbol AND kind = 'entry';
        END IF;
        IF v_entry IS NULL THEN
            RAISE EXCEPTION 'deployment % is at stage %: signals come only from a forward or live '
                'deployment (after that, only the exit of a trade already entered)',
                NEW.deployment_id, COALESCE(v_stage, '<missing>')
                USING ERRCODE = 'check_violation';
        END IF;
        v_stage := v_entry;
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
