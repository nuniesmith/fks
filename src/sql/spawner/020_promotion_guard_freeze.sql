-- ============================================================================
-- 020 — the promotion guard could authorise its own shortcut
-- ============================================================================
-- Migration 018 exists so that "a UI check is a suggestion" does not apply to
-- the promotion ladder. External review (Sol, 2026-09-03) found that its
-- central protection was defeatable by doing two things in one statement.
--
-- THREE DEFECTS, all in `edge_deployments_promotion_guard()`.
--
-- 1. THE FREEZE WAS SCOPED TO SAME-STAGE EDITS.
--
--    `forward_sessions_required` is frozen once a deployment leaves backtest —
--    but that check lives inside `IF NEW.stage = OLD.stage`. An UPDATE that
--    changes the stage never enters that branch, so
--
--        UPDATE edge_deployments
--           SET stage = 'live', forward_sessions_required = 1
--         WHERE id = ...;
--
--    walks straight past the freeze. Pre-registration that can be rewritten
--    during the act of promotion is not pre-registration.
--
-- 2. THE GATE COMPARED NEW AGAINST NEW.
--
--    `NEW.forward_sessions_observed < NEW.forward_sessions_required` measures
--    the evidence against the requirement AS REVISED BY THE SAME STATEMENT.
--    With defect 1 fixed the two values are necessarily equal, but comparing
--    OLD is the honest expression of "the requirement declared in advance",
--    and it keeps the gate correct even if a future edit reopens the freeze.
--
-- 3. A NULL REQUIREMENT PASSED SILENTLY.
--
--    `observed < NULL` evaluates to NULL, which is not TRUE, so the exception
--    never fired. Setting the requirement to NULL was therefore a complete
--    bypass — and NULL is exactly what an incomplete form submission sends.
--    In SQL an unknown requirement must fail closed; it is the one comparison
--    where "not false" and "true" differ and the difference is the whole gate.
--
-- No behaviour changes for a legitimate promotion: declare the requirement at
-- backtest->forward, accumulate sessions, promote. Only the shortcuts close.
--
-- ── RETRACTION, same day ────────────────────────────────────────────────────
--
-- An earlier version of this header claimed a FOURTH defect: that 018's file
-- queried `rithmic_accounts.id` for `account_class` and had drifted from the
-- deployed function. THAT WAS FALSE, and the external reviewer was right to
-- refuse it.
--
-- 018 queries `accounts WHERE account_id = NEW.account_id`, it always has, and
-- `FROM rithmic_accounts` has never appeared in that file at any commit. The
-- claim came from a grep that matched nothing, read as though it had matched
-- something — absence of evidence taken for evidence. The function body below
-- was never affected; only the story around it was.
--
-- Left in place rather than deleted: a retracted claim that disappears is one
-- that gets rediscovered.
--
-- Idempotent: CREATE OR REPLACE, and the trigger binding is unchanged from 018.

-- Runs against fks_db. Every spawner migration from 001-015 carries this
-- preamble; 016 shipped without it, so on a CLEAN bootstrap the objects below
-- were created in POSTGRES_DB (janus_db) instead — where set_updated_at() does
-- not exist, so initdb failed. The live database is correct only because these
-- were applied by hand with `psql -d fks_db`. Found 2026-09-04 by actually
-- building the image and booting an empty database, which is the only way this
-- class of defect is visible.

\getenv fks_db   RUBY_DB

\connect :fks_db

CREATE OR REPLACE FUNCTION edge_deployments_promotion_guard()
RETURNS TRIGGER AS $$
DECLARE
    v_class   TEXT;
    v_verdict TEXT;
BEGIN
    -- `accounts.account_class`, matching the FK
    -- (edge_deployments.account_id -> accounts.account_id) and unchanged from 018.
    IF NEW.execution = 'auto' THEN
        SELECT account_class INTO v_class
          FROM accounts WHERE account_id = NEW.account_id;
        IF v_class = 'prop' THEN
            RAISE EXCEPTION
                'execution=auto is refused on prop account % (class=%): the '
                'firm prohibits automated decisions, so a human places every '
                'order on this account', NEW.account_id, v_class
                USING ERRCODE = 'check_violation';
        END IF;
    END IF;

    IF TG_OP = 'INSERT' THEN
        -- New deployments start at the bottom. Inserting straight at 'live'
        -- would walk around every rule below, which is the obvious attack on
        -- any state machine whose transitions are guarded but whose entry
        -- point is not.
        IF NEW.stage <> 'backtest' THEN
            RAISE EXCEPTION
                'a new deployment must start at stage=backtest (got %); the '
                'ladder is climbed, not entered partway up', NEW.stage
                USING ERRCODE = 'check_violation';
        END IF;
        RETURN NEW;
    END IF;

    -- ── THE FREEZE, now evaluated on EVERY update ───────────────────────────
    -- Hoisted out of the same-stage branch (defect 1). Once a deployment has
    -- left backtest its declared requirement is immutable, whether or not the
    -- same statement also moves the stage. Retirement is exempt: abandoning a
    -- test must never be harder than completing it.
    IF OLD.stage <> 'backtest' AND NEW.stage <> 'retired'
       AND NEW.forward_sessions_required IS DISTINCT FROM OLD.forward_sessions_required THEN
        RAISE EXCEPTION
            'forward_sessions_required is frozen once a deployment leaves '
            'backtest (% -> %): it is declared in advance or it is not '
            'evidence', OLD.forward_sessions_required, NEW.forward_sessions_required
            USING ERRCODE = 'check_violation';
    END IF;

    IF NEW.stage = OLD.stage THEN
        RETURN NEW;
    END IF;

    -- Retirement is always available, needs no approval, and is the only
    -- transition anything automatic may perform. Demotion must be cheaper than
    -- promotion, or the system acquires a bias toward staying deployed.
    IF NEW.stage = 'retired' THEN
        RETURN NEW;
    END IF;

    -- ...and it is terminal. Re-deploying is a new decision and deserves a new
    -- row with its own evidence, not a quiet un-retirement of the old one.
    IF OLD.stage = 'retired' THEN
        RAISE EXCEPTION
            'retired is terminal; create a new deployment rather than '
            'un-retiring this one'
            USING ERRCODE = 'check_violation';
    END IF;

    IF OLD.stage = 'backtest' AND NEW.stage = 'forward' THEN
        SELECT verdict INTO v_verdict
          FROM edge_experiments WHERE id = NEW.experiment_id;
        IF v_verdict IS DISTINCT FROM 'USABLE' THEN
            RAISE EXCEPTION
                'backtest->forward requires the experiment verdict to be '
                'USABLE (experiment % is %)', NEW.experiment_id,
                COALESCE(v_verdict, '<missing>')
                USING ERRCODE = 'check_violation';
        END IF;
        IF NEW.forward_sessions_required IS NULL THEN
            RAISE EXCEPTION
                'backtest->forward requires forward_sessions_required to be '
                'declared in advance'
                USING ERRCODE = 'check_violation';
        END IF;
        RETURN NEW;
    END IF;

    IF OLD.stage = 'forward' AND NEW.stage = 'live' THEN
        -- Fail closed on an unknown requirement (defect 3). `observed < NULL`
        -- is NULL, not TRUE, so without this the exception never fires and a
        -- NULL requirement is a complete bypass.
        IF OLD.forward_sessions_required IS NULL THEN
            RAISE EXCEPTION
                'forward->live refused: forward_sessions_required is NULL, so '
                'there is no declared requirement to have met'
                USING ERRCODE = 'check_violation';
        END IF;
        -- Measure against the requirement declared IN ADVANCE (defect 2).
        IF NEW.forward_sessions_observed IS NULL
           OR NEW.forward_sessions_observed < OLD.forward_sessions_required THEN
            RAISE EXCEPTION
                'forward->live requires % forward session(s), only % observed',
                OLD.forward_sessions_required,
                COALESCE(NEW.forward_sessions_observed::TEXT, 'NULL')
                USING ERRCODE = 'check_violation';
        END IF;
        RETURN NEW;
    END IF;

    -- Everything else — skipping a rung, or climbing back down to anything but
    -- retired — is refused. There is no legitimate backtest->live.
    RAISE EXCEPTION
        'illegal stage transition % -> %; the ladder is backtest -> forward -> '
        'live, and any stage may go to retired', OLD.stage, NEW.stage
        USING ERRCODE = 'check_violation';
END;
$$ LANGUAGE plpgsql;
