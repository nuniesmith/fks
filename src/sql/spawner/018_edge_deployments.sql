-- ⚠ SUPERSEDED IN PART BY 020_promotion_guard_freeze.sql (2026-09-04).
-- `edge_deployments_promotion_guard()` below has two defects, both in the
-- promotion path:
--
--   1. The `forward_sessions_required` freeze is scoped to same-stage edits, so
--      a single UPDATE that changes the stage AND lowers the bar walks past it
--      (demonstrated: promoted to live on 5 of a declared 20 sessions).
--   2. A NULL requirement bypasses the gate entirely, because
--      `observed < NULL` is NULL rather than TRUE.
--
-- 020 replaces the function with a corrected body. Apply 018 then 020.
--
-- RETRACTED 2026-09-04, same day: an earlier version of this note also claimed
-- the prop-account guard here queries `rithmic_accounts.id` and had drifted
-- from the deployed function. THAT WAS FALSE. This file queries
-- `accounts WHERE account_id = NEW.account_id`, it always has, and
-- `FROM rithmic_accounts` has never appeared in its history. The claim came
-- from reading a grep that matched nothing and treating that as evidence of a
-- mismatch. Recorded rather than deleted so the wrong story cannot come back.

-- ============================================================================
-- 018_edge_deployments.sql — binding an edge to an asset, on an account
-- ============================================================================
-- WHY. `edge_experiments` (017) records what was SEARCHED. It says nothing
-- about what is being TRADED. Today that binding is implicit — a
-- `Params.for_root("GC")` call plus a verdict in a TOML file — so there is no
-- way to ask "what is live right now, on what, since when, and on the strength
-- of which experiment?"
--
-- This table makes the binding explicit and, more importantly, makes the
-- PROMOTION LADDER a database invariant instead of a habit:
--
--     backtest --> forward --> live
--          \          |          /
--           `------ retired <---'
--
-- THE RULES LIVE HERE, NOT IN THE UI. A check in the web layer is a
-- suggestion: it is bypassed by psql, by a script, by a future second client,
-- and by the operator at 3am who is certain this once is fine. The whole value
-- of a ladder is that each rung is harder to climb than the last, and a rung
-- that can be stepped over on request is not a rung. So the transitions are
-- enforced by a trigger that RAISES, and the trigger is the only authority.
--
-- THE ACCOUNT DIMENSION IS LOAD-BEARING. The manual-execution constraint is
-- per-ACCOUNT, not per-platform, and `stage = 'live'` means two different
-- things depending on where it lands:
--
--     prop account (TakeProfit)  ->  the plan renders with more confidence.
--                                    A HUMAN still places every order.
--     personal account           ->  the machine may place orders.
--
-- Those cannot share one unqualified `stage` column, because then the cheap
-- transition (change a font weight) silently authorises the expensive one (arm
-- an order path). Hence `execution`, and hence the constraint that a prop
-- account can never hold an `auto` deployment — that makes the prop firm's
-- no-bot rule something the database refuses rather than something we remember.
--
-- The platform already runs both classes: crypto-spot is live and autonomous
-- while the entire futures path is manual. That split was never a principle; it
-- was the prop firm. This names it.
--
-- Idempotent — safe to re-run (CREATE TABLE IF NOT EXISTS, CREATE OR REPLACE
-- FUNCTION, DROP TRIGGER IF EXISTS, CREATE INDEX IF NOT EXISTS).
-- ============================================================================

-- Runs against fks_db. Every spawner migration from 001-015 carries this
-- preamble; 016 shipped without it, so on a CLEAN bootstrap the objects below
-- were created in POSTGRES_DB (janus_db) instead — where set_updated_at() does
-- not exist, so initdb failed. The live database is correct only because these
-- were applied by hand with `psql -d fks_db`. Found 2026-09-04 by actually
-- building the image and booting an empty database, which is the only way this
-- class of defect is visible.

\getenv fks_db   RUBY_DB

\connect :fks_db

CREATE TABLE IF NOT EXISTS edge_deployments (
    id                        BIGSERIAL PRIMARY KEY,

    -- ── What is deployed, and on the strength of what ───────────────────────
    -- RESTRICT, not CASCADE: deleting the experiment that justified a live
    -- deployment must not silently succeed and leave the deployment orphaned
    -- of its evidence. Retire the deployment first.
    experiment_id             BIGINT      NOT NULL
                                          REFERENCES edge_experiments (id)
                                          ON DELETE RESTRICT,

    -- Reuses the existing account registry (007) rather than inventing a
    -- second one. `accounts.account_class` is what decides whether `live` may
    -- mean autonomous execution — see the promotion guard below.
    account_id                TEXT        NOT NULL
                                          REFERENCES accounts (account_id)
                                          ON DELETE RESTRICT,

    symbol                    TEXT        NOT NULL,

    -- ── Where it sits on the ladder ─────────────────────────────────────────
    stage                     TEXT        NOT NULL DEFAULT 'backtest',

    -- Who pulls the trigger. Defaults to the safe value; promoting to 'auto'
    -- is refused outright on a prop account.
    execution                 TEXT        NOT NULL DEFAULT 'manual',

    -- ── The thing actually being traded ─────────────────────────────────────
    -- Frozen at deployment so a live edge cannot silently drift from what was
    -- validated. The object being traded and the object that was tested must
    -- be provably the same object; without this, "it passed the holdout" is a
    -- claim about a parameter set nobody can produce afterwards.
    params_snapshot           JSONB       NOT NULL,

    -- ── The forward-test contract, declared BEFORE the evidence arrives ─────
    -- Set when entering `forward` and immutable thereafter (enforced below).
    -- Deciding how many sessions count as proof AFTER seeing the sessions is
    -- how a forward test becomes a second selection set.
    forward_sessions_required INTEGER,
    forward_sessions_observed INTEGER     NOT NULL DEFAULT 0,

    -- ── Live outcome, for the divergence monitor ────────────────────────────
    live_trades               INTEGER     NOT NULL DEFAULT 0,
    live_r_sum                DOUBLE PRECISION NOT NULL DEFAULT 0,
    divergence_vs_backtest    DOUBLE PRECISION,

    -- ── Bookkeeping ─────────────────────────────────────────────────────────
    since                     TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- Required on retirement. This is a NOTE, not an approval — retirement is
    -- still unconditional — but a demotion nobody can explain later is a
    -- demotion that teaches nothing.
    retired_reason            TEXT,

    created_at                TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at                TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT edge_deployments_stage_known
        CHECK (stage IN ('backtest', 'forward', 'live', 'retired')),
    CONSTRAINT edge_deployments_execution_known
        CHECK (execution IN ('manual', 'auto')),
    CONSTRAINT edge_deployments_forward_required_positive
        CHECK (forward_sessions_required IS NULL OR forward_sessions_required > 0),
    CONSTRAINT edge_deployments_observed_not_negative
        CHECK (forward_sessions_observed >= 0),
    CONSTRAINT edge_deployments_retired_has_reason
        CHECK (stage <> 'retired' OR retired_reason IS NOT NULL)
);

-- One live edge per instrument per account. Two edges both live on GC in the
-- same account is not a portfolio, it is two systems fighting over one
-- position. Partial, so retired/backtest rows may pile up freely.
CREATE UNIQUE INDEX IF NOT EXISTS edge_deployments_one_live_per_symbol_account
    ON edge_deployments (account_id, symbol)
    WHERE stage = 'live';

CREATE INDEX IF NOT EXISTS edge_deployments_stage_idx
    ON edge_deployments (stage);
CREATE INDEX IF NOT EXISTS edge_deployments_experiment_idx
    ON edge_deployments (experiment_id);

-- ── The ladder, enforced ────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION edge_deployments_promotion_guard()
RETURNS TRIGGER AS $$
DECLARE
    v_verdict TEXT;
    v_class   TEXT;
BEGIN
    -- An `auto` deployment on a prop account would be a trading bot on an
    -- account whose firm prohibits automated decisions. Refuse it at the
    -- source, on INSERT and UPDATE alike, so no code path can create one.
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

    -- Same-stage edits: allowed, EXCEPT moving the goalposts. Once a forward
    -- test is underway its required session count is frozen; lowering it after
    -- seeing results is precisely the thing pre-registration prevents.
    IF NEW.stage = OLD.stage THEN
        IF OLD.stage <> 'backtest'
           AND NEW.forward_sessions_required IS DISTINCT FROM OLD.forward_sessions_required THEN
            RAISE EXCEPTION
                'forward_sessions_required is frozen once a deployment leaves '
                'backtest (% -> %): it is declared in advance or it is not '
                'evidence', OLD.forward_sessions_required, NEW.forward_sessions_required
                USING ERRCODE = 'check_violation';
        END IF;
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
        IF NEW.forward_sessions_observed < NEW.forward_sessions_required THEN
            RAISE EXCEPTION
                'forward->live requires % forward session(s), only % observed',
                NEW.forward_sessions_required, NEW.forward_sessions_observed
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

DROP TRIGGER IF EXISTS trg_edge_deployments_promotion ON edge_deployments;
CREATE TRIGGER trg_edge_deployments_promotion
    BEFORE INSERT OR UPDATE ON edge_deployments
    FOR EACH ROW EXECUTE FUNCTION edge_deployments_promotion_guard();

-- Stamp updated_at on every change. Reuses set_updated_at() from 002_spawner.sql.
DROP TRIGGER IF EXISTS trg_edge_deployments_updated_at ON edge_deployments;
CREATE TRIGGER trg_edge_deployments_updated_at
    BEFORE UPDATE ON edge_deployments
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE edge_deployments IS
    'One row per edge bound to an asset on an account, with its rung on the '
    'promotion ladder. Transitions are enforced by a trigger, not by the UI.';
COMMENT ON COLUMN edge_deployments.execution IS
    'manual = a human places every order (the only value a prop account may '
    'hold) | auto = the machine may place orders';
COMMENT ON COLUMN edge_deployments.params_snapshot IS
    'Frozen at deployment so a live edge cannot drift from what was validated.';
COMMENT ON COLUMN edge_deployments.forward_sessions_required IS
    'Declared on entering forward and immutable after — deciding the bar after '
    'seeing the results turns a forward test into a second selection set.';

GRANT SELECT, INSERT, UPDATE ON edge_deployments TO fks_webui;
GRANT USAGE, SELECT ON SEQUENCE edge_deployments_id_seq TO fks_webui;
