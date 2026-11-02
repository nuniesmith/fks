-- =============================================================================
-- 029_edge_forward_sessions.sql — the forward ledger, and the counter it backs
-- =============================================================================
-- EDGE_PROCESS §5-§6: a deployment goes live only once
-- forward_sessions_observed >= forward_sessions_required. Until now that
-- number was a plain column: `UPDATE edge_deployments SET
-- forward_sessions_observed = 999` passed the guard (a same-stage update
-- returns early), and nothing recorded WHICH sessions were observed. Nor was
-- params_snapshot frozen, despite its comment, and `since` was whatever the
-- application wrote.
--
-- THE LEDGER. One row per forward session a runner observed, written as it
-- happens:
--   • append-only (no UPDATE, no DELETE);
--   • only while the deployment is at stage=forward, and only for sessions
--     AFTER the day it entered forward;
--   • recorded_at is the database's clock, at least the day after the
--     session (it is over) and at most 10 days† after it (later is a
--     backfill, not an observation: a gap stays a gap);
--   • it names the lake files it read (path + sha256) and the code version,
--     so a session can be replayed and checked;
--   • one row per deployment and session.
--
-- THE COUNTER. After every ledger insert, forward_sessions_observed is set
-- to the ledger's row count (SECURITY DEFINER: the runner's role can't
-- update deployments). Set, not incremented: row triggers fire after the
-- whole statement, so a two-row insert sees both rows.
--
-- WHAT IS DEPLOYED IS WHAT WAS SEARCHED. The selection lived only in the
-- search job's verdict.json: a deployment's params_snapshot was typed by
-- hand (fks-web's deploy form), so a deployment could trade parameters no
-- search ever selected. Now:
--   • edge_experiments.selected_params holds the winner, written by the job;
--   • a deployment's params_snapshot must EQUAL its experiment's;
--   • an experiment is frozen once it has FINISHED (finished_at set): only
--     `outcome` may change, and it is never deleted (a deleted DO NOT PASTE
--     would also drop its trials from N; an UPDATE of verdict to USABLE
--     opened backtest->forward). A study still running (finished_at NULL)
--     is still being written, and can't be deployed.
--
-- THE GUARD (re-created from 020, every earlier rule kept) also:
--   • refuses a new deployment with observed <> 0;
--   • refuses any change to observed that leaves it unequal to the ledger;
--   • freezes experiment_id, account_id, symbol and params_snapshot from
--     creation;
--   • stamps `since` on every stage change, and refuses moving it otherwise.
--
-- Grants: the research role (fks_backtest: the search job and the forward
-- runner) reads deployments and writes the ledger. Idempotent.
-- Prerequisites: 017, 018, 020, 024, 025.
-- =============================================================================

\getenv fks_db RUBY_DB

\connect :fks_db

-- ── The search's selection, and experiments that stay as written ─────────────
ALTER TABLE edge_experiments ADD COLUMN IF NOT EXISTS selected_params JSONB;
COMMENT ON COLUMN edge_experiments.selected_params IS
    'The selected parameter set (the search job writes it); a deployment of '
    'this experiment trades exactly this, params_snapshot = selected_params.';

CREATE OR REPLACE FUNCTION edge_experiments_frozen()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION
            'experiment % is a result and is never deleted: a DO NOT PASTE '
            'counts toward N like any other search', OLD.id
            USING ERRCODE = 'check_violation';
    END IF;
    -- A study still running (no finished_at) is still being written.
    IF OLD.finished_at IS NULL THEN
        RETURN NEW;
    END IF;
    IF (to_jsonb(NEW) - 'outcome' - 'updated_at') IS DISTINCT FROM
       (to_jsonb(OLD) - 'outcome' - 'updated_at') THEN
        RAISE EXCEPTION
            'experiment % finished at % and is frozen as the search wrote it: '
            'only its outcome may change', OLD.id, OLD.finished_at
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_edge_experiments_frozen ON edge_experiments;
CREATE TRIGGER trg_edge_experiments_frozen
    BEFORE UPDATE OR DELETE ON edge_experiments
    FOR EACH ROW EXECUTE FUNCTION edge_experiments_frozen();

-- ── The forward ledger ───────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS edge_forward_sessions (
    id              BIGSERIAL   PRIMARY KEY,
    deployment_id   BIGINT      NOT NULL REFERENCES edge_deployments (id) ON DELETE RESTRICT,
    session_date    DATE        NOT NULL,
    symbol          TEXT        NOT NULL,
    traded          BOOLEAN     NOT NULL,
    -- side, entry/exit minute and price, return: NULL when flat.
    trade           JSONB,
    -- net, over the notional at entry; 0 when flat.
    session_return  DOUBLE PRECISION NOT NULL,
    -- [{"path": "...", "sha256": "..."}]: the lake files it read.
    data_ref        JSONB       NOT NULL,
    runner          TEXT        NOT NULL,
    code_version    TEXT        NOT NULL,
    recorded_at     TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT edge_forward_sessions_one_per_day UNIQUE (deployment_id, session_date),
    CONSTRAINT edge_forward_sessions_trade_iff_traded CHECK (traded = (trade IS NOT NULL)),
    CONSTRAINT edge_forward_sessions_flat_is_zero CHECK (traded OR session_return = 0),
    CONSTRAINT edge_forward_sessions_return_sane
        CHECK (session_return = session_return AND abs(session_return) < 1),
    CONSTRAINT edge_forward_sessions_data_named
        CHECK (jsonb_typeof(data_ref) = 'array' AND jsonb_array_length(data_ref) >= 1),
    CONSTRAINT edge_forward_sessions_runner_named CHECK (length(btrim(runner)) > 0),
    CONSTRAINT edge_forward_sessions_code_named CHECK (length(btrim(code_version)) > 0)
);

-- How late a session may still be recorded (†, EDGE_PROCESS §9).
CREATE OR REPLACE FUNCTION edge_forward_late_days() RETURNS INTEGER
    LANGUAGE sql IMMUTABLE AS $$ SELECT 10 $$;

CREATE OR REPLACE FUNCTION edge_forward_sessions_admit()
RETURNS TRIGGER AS $$
DECLARE
    v_stage  TEXT;
    v_since  TIMESTAMPTZ;
    v_symbol TEXT;
    v_today  DATE := (now() AT TIME ZONE 'UTC')::DATE;
BEGIN
    IF TG_OP <> 'INSERT' THEN
        RAISE EXCEPTION
            'the forward ledger is append-only: a recorded session is never '
            'changed or deleted (row %)', OLD.id
            USING ERRCODE = 'check_violation';
    END IF;
    SELECT stage, since, symbol INTO v_stage, v_since, v_symbol
      FROM edge_deployments WHERE id = NEW.deployment_id;
    IF v_stage IS DISTINCT FROM 'forward' THEN
        RAISE EXCEPTION
            'deployment % is at stage %, not forward: forward sessions are '
            'observed only while it is forward', NEW.deployment_id, COALESCE(v_stage, '<missing>')
            USING ERRCODE = 'check_violation';
    END IF;
    IF NEW.symbol IS DISTINCT FROM v_symbol THEN
        RAISE EXCEPTION
            'deployment % trades %, not %', NEW.deployment_id, v_symbol, NEW.symbol
            USING ERRCODE = 'check_violation';
    END IF;
    IF NEW.session_date <= (v_since AT TIME ZONE 'UTC')::DATE THEN
        RAISE EXCEPTION
            'session % is not after the day deployment % entered forward (%)',
            NEW.session_date, NEW.deployment_id, (v_since AT TIME ZONE 'UTC')::DATE
            USING ERRCODE = 'check_violation';
    END IF;
    NEW.recorded_at := now();
    IF NEW.session_date >= v_today THEN
        RAISE EXCEPTION
            'session % is not over yet (today is % UTC): a session is recorded '
            'once it has happened', NEW.session_date, v_today
            USING ERRCODE = 'check_violation';
    END IF;
    IF v_today - NEW.session_date > edge_forward_late_days() THEN
        RAISE EXCEPTION
            'session % is % days old: a forward session is recorded as it '
            'happens (within % days), and a later one is a backfill',
            NEW.session_date, v_today - NEW.session_date, edge_forward_late_days()
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_edge_forward_sessions_admit ON edge_forward_sessions;
CREATE TRIGGER trg_edge_forward_sessions_admit
    BEFORE INSERT OR UPDATE OR DELETE ON edge_forward_sessions
    FOR EACH ROW EXECUTE FUNCTION edge_forward_sessions_admit();

-- The counter follows the ledger. SECURITY DEFINER: the runner's role writes
-- ledger rows but has no UPDATE on deployments.
CREATE OR REPLACE FUNCTION edge_forward_sessions_count()
RETURNS TRIGGER
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
BEGIN
    UPDATE edge_deployments
       SET forward_sessions_observed =
           (SELECT count(*)::INTEGER FROM edge_forward_sessions WHERE deployment_id = NEW.deployment_id)
     WHERE id = NEW.deployment_id;
    RETURN NULL;
END;
$$;

DROP TRIGGER IF EXISTS trg_edge_forward_sessions_count ON edge_forward_sessions;
CREATE TRIGGER trg_edge_forward_sessions_count
    AFTER INSERT ON edge_forward_sessions
    FOR EACH ROW EXECUTE FUNCTION edge_forward_sessions_count();

-- The promotion guard, re-created from 020 with 029's rules added (marked).
CREATE OR REPLACE FUNCTION edge_deployments_promotion_guard()
RETURNS TRIGGER AS $$
DECLARE
    v_class    TEXT;
    v_verdict  TEXT;
    v_selected JSONB;
    v_finished TIMESTAMPTZ;
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
        -- 029: it trades exactly what its search selected, once that search
        -- has finished.
        SELECT selected_params, finished_at INTO v_selected, v_finished
          FROM edge_experiments WHERE id = NEW.experiment_id;
        IF NOT FOUND THEN
            -- Said here, before NOT NULL or the foreign key word it worse.
            RAISE EXCEPTION
                'experiment % is not present: a deployment deploys a search',
                NEW.experiment_id
                USING ERRCODE = 'check_violation';
        END IF;
        IF v_finished IS NULL THEN
            RAISE EXCEPTION
                'experiment % hasn''t finished: a running search has no verdict to deploy',
                NEW.experiment_id
                USING ERRCODE = 'check_violation';
        END IF;
        IF v_selected IS NULL THEN
            RAISE EXCEPTION
                'experiment % has no selected parameters on record (searched '
                'before 029, or written by hand): nothing to deploy',
                NEW.experiment_id
                USING ERRCODE = 'check_violation';
        END IF;
        IF NEW.params_snapshot IS DISTINCT FROM v_selected THEN
            RAISE EXCEPTION
                'params_snapshot % is not what experiment % selected (%): a '
                'deployment trades exactly what was searched',
                NEW.params_snapshot, NEW.experiment_id, v_selected
                USING ERRCODE = 'check_violation';
        END IF;
        -- 029: no deployment is born with evidence.
        IF NEW.forward_sessions_observed <> 0 THEN
            RAISE EXCEPTION
                'a new deployment observes 0 forward sessions (got %): sessions '
                'are counted from the forward ledger, edge_forward_sessions',
                NEW.forward_sessions_observed
                USING ERRCODE = 'check_violation';
        END IF;
        RETURN NEW;
    END IF;

    -- ── 029: what is deployed is frozen from creation ───────────────────────
    -- The object traded and the object tested must be provably the same; a
    -- different one is a new deployment.
    IF NEW.params_snapshot IS DISTINCT FROM OLD.params_snapshot
       OR NEW.experiment_id IS DISTINCT FROM OLD.experiment_id
       OR NEW.account_id   IS DISTINCT FROM OLD.account_id
       OR NEW.symbol       IS DISTINCT FROM OLD.symbol THEN
        RAISE EXCEPTION
            'deployment % is frozen: its experiment, account, symbol and '
            'params_snapshot cannot change; create a new deployment', OLD.id
            USING ERRCODE = 'check_violation';
    END IF;

    -- ── 029: the observed count is the forward ledger's ─────────────────────
    -- Not a number anyone can write: a change must leave it equal to the
    -- ledger's row count for this deployment.
    IF NEW.forward_sessions_observed IS DISTINCT FROM OLD.forward_sessions_observed
       AND NEW.forward_sessions_observed IS DISTINCT FROM
           (SELECT count(*)::INTEGER FROM edge_forward_sessions WHERE deployment_id = NEW.id) THEN
        RAISE EXCEPTION
            'forward_sessions_observed is counted from edge_forward_sessions '
            '(% rows for deployment %), not set: got %',
            (SELECT count(*) FROM edge_forward_sessions WHERE deployment_id = NEW.id),
            NEW.id, NEW.forward_sessions_observed
            USING ERRCODE = 'check_violation';
    END IF;

    -- ── 029: `since` is stamped here, on every stage change ─────────────────
    -- It is when the deployment entered its stage. A same-stage update can't
    -- move it: moving the forward start earlier would admit older sessions.
    IF NEW.stage IS DISTINCT FROM OLD.stage THEN
        NEW.since := now();
    ELSIF NEW.since IS DISTINCT FROM OLD.since THEN
        RAISE EXCEPTION
            'since is stamped when the stage changes (% -> % refused)', OLD.since, NEW.since
            USING ERRCODE = 'check_violation';
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

COMMENT ON TABLE edge_forward_sessions IS
    'The forward ledger (EDGE_PROCESS §5): one row per session a forward '
    'runner observed, append-only, recorded as it happens; '
    'edge_deployments.forward_sessions_observed is its row count.';

-- ---------------------------------------------------------------------------
-- Privileges: the research role reads deployments and writes the ledger.
-- ---------------------------------------------------------------------------
GRANT SELECT ON edge_deployments TO fks_backtest;
GRANT SELECT, INSERT ON edge_forward_sessions TO fks_backtest;
GRANT USAGE ON SEQUENCE edge_forward_sessions_id_seq TO fks_backtest;
