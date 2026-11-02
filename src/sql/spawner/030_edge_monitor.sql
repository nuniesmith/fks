-- =============================================================================
-- 030_edge_monitor.sql — forward judged against the holdout, and an edge
-- retired when its sessions stop behaving like its backtest
-- =============================================================================
-- EDGE_PROCESS §5 and §7. 029 counts forward sessions but never looks at
-- them: a deployment whose 20 forward sessions all lost could go live like
-- one that matched its backtest, and nothing watched an edge decay.
--
-- THE REFERENCE. edge_experiments.holdout_returns: the selected
-- parameters' session returns over the holdout, in order, as the search
-- scored them (the one series nobody selected on). The search job writes
-- it; 029 freezes it with the rest of a finished row. μ and σ below are its
-- mean and sample standard deviation.
--
-- THE FORWARD BAND (§5). Once the first forward_sessions_required (n)
-- sessions are in, their mean must not fall below
--     floor = μ − 1.645† · σ / √n
-- the 5th percentile of an n-session mean drawn from the holdout (the
-- normal approximation of the bootstrap band: one the database can compute
-- and anyone can check). Evaluated ONCE, on exactly those n sessions: a band
-- re-tested every day fails a sound edge by chance sooner or later.
--
-- THE CUSUM (§7). From the first forward session on, through live: a
-- one-sided lower CUSUM of the standardized session returns,
--     z_t = (x_t − μ) / σ,    S_t = max(0, S_{t−1} − z_t − k),
-- alarming when S_t > h. k is half the holdout's per-session Sharpe (μ/σ:
-- the shift from the backtested edge to none), kept within [0.025, 0.5]†;
-- h is set so that sessions performing exactly like the holdout raise a
-- false alarm once in 500† sessions on average (Siegmund's approximation;
-- checked by simulation for normal and orb-like sessions, 2026-11-02).
-- The cost of that rate: an edge that halves takes on the order of 100-300
-- sessions to catch. Per-session P&L can't do better; mechanics checks are
-- what catch a broken bot quickly.
--
-- ON BREACH the deployment is RETIRED in the same transaction as the
-- session that breached; retired_reason gives the test and its numbers,
-- and an edge_monitor_events row is left for the spawner to deliver
-- (edge_decay). Retirement is terminal (018): testing the edge again is a
-- new deployment with a fresh forward window. Nothing re-promotes.
--
-- WHERE IT APPLIES. Hypotheses with evidence = 'trades' (028's default).
-- A low-frequency edge is judged on mechanics, not P&L (§7): its health
-- says so and neither test runs.
--
-- THE GATES (the promotion guard, re-created from 029, rules marked 030):
--   • backtest→forward needs a holdout series to judge against;
--   • forward→live needs the band to have PASSED.
--
-- THE LEDGER THROUGH LIVE. The forward runner keeps replaying the model
-- once a deployment is live: the model's sessions are what the CUSUM
-- watches. A row records the stage it was observed at (the database sets
-- it), and forward_sessions_observed counts the forward rows only.
--
-- Idempotent. Prerequisites: 017, 018, 020, 024, 025, 028, 029.
-- =============================================================================

\getenv fks_db RUBY_DB

\connect :fks_db

-- ── The reference: the holdout, as the search scored it ─────────────────────
ALTER TABLE edge_experiments ADD COLUMN IF NOT EXISTS holdout_returns DOUBLE PRECISION[];
COMMENT ON COLUMN edge_experiments.holdout_returns IS
    'The selected parameters'' session returns over the holdout, in order (the '
    'search job writes it): what forward and live sessions are judged against (030).';

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint
                    WHERE conname = 'edge_experiments_holdout_returns_finite') THEN
        ALTER TABLE edge_experiments
            ADD CONSTRAINT edge_experiments_holdout_returns_finite
            CHECK (holdout_returns IS NULL
                   OR (cardinality(holdout_returns) >= 1
                       AND NOT ('NaN'::DOUBLE PRECISION = ANY (holdout_returns))
                       AND NOT ('Infinity'::DOUBLE PRECISION = ANY (holdout_returns))
                       AND NOT ('-Infinity'::DOUBLE PRECISION = ANY (holdout_returns))));
    END IF;
END $$;

-- ── The numbers (†, EDGE_PROCESS §9) ────────────────────────────────────────
CREATE OR REPLACE FUNCTION edge_monitor_version() RETURNS TEXT
    LANGUAGE sql IMMUTABLE AS $$ SELECT 'edge-monitor-2026-11-02-proposed'::TEXT $$;

-- The band's one-sided z: its 5th percentile.
CREATE OR REPLACE FUNCTION edge_monitor_band_z() RETURNS DOUBLE PRECISION
    LANGUAGE sql IMMUTABLE AS $$ SELECT 1.6448536269514722::DOUBLE PRECISION $$;

-- Sessions between false alarms, on average, for an edge performing like
-- its holdout.
CREATE OR REPLACE FUNCTION edge_monitor_arl0() RETURNS DOUBLE PRECISION
    LANGUAGE sql IMMUTABLE AS $$ SELECT 500::DOUBLE PRECISION $$;

-- The CUSUM's reference value: half the per-session Sharpe, within bounds.
CREATE OR REPLACE FUNCTION edge_monitor_k(p_mean DOUBLE PRECISION, p_sd DOUBLE PRECISION)
RETURNS DOUBLE PRECISION
    LANGUAGE sql IMMUTABLE AS $$ SELECT least(0.5, greatest(0.025, 0.5 * p_mean / p_sd)) $$;

-- The CUSUM's threshold for reference value k and a mean of p_arl0 sessions
-- between false alarms. Siegmund: ARL0 ≈ (e^u − u − 1) / (2k²) with
-- u = 2k(h + 1.166); solved for u by bisection (e^u − u − 1 rises on u > 0).
CREATE OR REPLACE FUNCTION edge_monitor_cusum_h(p_k DOUBLE PRECISION, p_arl0 DOUBLE PRECISION)
RETURNS DOUBLE PRECISION
LANGUAGE plpgsql IMMUTABLE AS $$
DECLARE
    v_target DOUBLE PRECISION := 2 * p_k * p_k * p_arl0;
    v_lo     DOUBLE PRECISION := 0;
    v_hi     DOUBLE PRECISION := 60;
    v_mid    DOUBLE PRECISION;
BEGIN
    FOR i IN 1..100 LOOP
        v_mid := (v_lo + v_hi) / 2;
        IF exp(v_mid) - v_mid - 1 < v_target THEN
            v_lo := v_mid;
        ELSE
            v_hi := v_mid;
        END IF;
    END LOOP;
    RETURN greatest(0, (v_lo + v_hi) / 2 / (2 * p_k) - 1.166);
END;
$$;

-- ── The ledger records the stage, and keeps going through live ──────────────
ALTER TABLE edge_forward_sessions
    ADD COLUMN IF NOT EXISTS stage TEXT NOT NULL DEFAULT 'forward';
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint
                    WHERE conname = 'edge_forward_sessions_stage_known') THEN
        ALTER TABLE edge_forward_sessions
            ADD CONSTRAINT edge_forward_sessions_stage_known
            CHECK (stage IN ('forward', 'live'));
    END IF;
END $$;
COMMENT ON COLUMN edge_forward_sessions.stage IS
    'The deployment''s stage when the session was recorded (set by the database). '
    'forward_sessions_observed counts the forward rows.';

-- Re-created from 029: admitted while forward OR live (030), and the row's
-- stage is the deployment's, whatever the client sent.
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
    IF v_stage IS NULL OR v_stage NOT IN ('forward', 'live') THEN
        RAISE EXCEPTION
            'deployment % is at stage %: sessions are observed only while it is '
            'forward or live', NEW.deployment_id, COALESCE(v_stage, '<missing>')
            USING ERRCODE = 'check_violation';
    END IF;
    NEW.stage := v_stage;
    IF NEW.symbol IS DISTINCT FROM v_symbol THEN
        RAISE EXCEPTION
            'deployment % trades %, not %', NEW.deployment_id, v_symbol, NEW.symbol
            USING ERRCODE = 'check_violation';
    END IF;
    IF NEW.session_date <= (v_since AT TIME ZONE 'UTC')::DATE THEN
        RAISE EXCEPTION
            'session % is not after the day deployment % entered %s (%)',
            NEW.session_date, NEW.deployment_id, v_stage, (v_since AT TIME ZONE 'UTC')::DATE
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

-- ── Health: both tests, computed from the record ────────────────────────────
-- One JSON document per deployment, the same for the guard, the ledger's
-- trigger, the spawner's board and the runner's metrics:
--   applies  false, with `why`, when there's nothing to judge with;
--   holdout  {n, mean, sd};
--   band     {verdict pending|pass|fail, n, required, mean, floor};
--   cusum    {value, peak, k, h, sessions, alarm, alarm_at}.
-- Reads only what the research role may read (SECURITY INVOKER).
CREATE OR REPLACE FUNCTION edge_deployment_health(p_deployment BIGINT)
RETURNS JSONB
LANGUAGE plpgsql STABLE AS $$
DECLARE
    v_required INTEGER;
    v_exp      BIGINT;
    v_hold     DOUBLE PRECISION[];
    v_evidence TEXT;
    v_mean     DOUBLE PRECISION;
    v_sd       DOUBLE PRECISION;
    v_n_hold   INTEGER;
    v_k        DOUBLE PRECISION;
    v_h        DOUBLE PRECISION;
    v_s        DOUBLE PRECISION := 0;
    v_peak     DOUBLE PRECISION := 0;
    v_alarm_at DATE;
    v_sessions INTEGER := 0;
    v_n_fwd    INTEGER := 0;
    v_sum_fwd  DOUBLE PRECISION := 0;
    v_band     JSONB;
    r          RECORD;
BEGIN
    SELECT forward_sessions_required, experiment_id INTO v_required, v_exp
      FROM edge_deployments WHERE id = p_deployment;
    IF NOT FOUND THEN
        RETURN NULL;
    END IF;
    SELECT e.holdout_returns, COALESCE(h.evidence, 'trades') INTO v_hold, v_evidence
      FROM edge_experiments e LEFT JOIN edge_hypotheses h ON h.id = e.hypothesis_id
     WHERE e.id = v_exp;
    IF v_evidence <> 'trades' THEN
        RETURN jsonb_build_object('applies', false, 'version', edge_monitor_version(),
            'why', 'a low-frequency edge is judged on mechanics, not P&L (EDGE_PROCESS §7)');
    END IF;
    SELECT avg(x), stddev_samp(x), count(*) INTO v_mean, v_sd, v_n_hold
      FROM unnest(v_hold) AS x;
    IF v_hold IS NULL OR v_n_hold < 2 OR v_sd IS NULL OR v_sd = 0 THEN
        RETURN jsonb_build_object('applies', false, 'version', edge_monitor_version(),
            'why', format('experiment %s has no holdout series to judge against (%s)', v_exp,
                          CASE WHEN v_hold IS NULL THEN 'none recorded'
                               WHEN v_n_hold < 2 THEN 'fewer than 2 sessions'
                               ELSE 'every session the same' END));
    END IF;
    v_k := edge_monitor_k(v_mean, v_sd);
    v_h := edge_monitor_cusum_h(v_k, edge_monitor_arl0());

    FOR r IN SELECT session_date, session_return, stage
               FROM edge_forward_sessions
              WHERE deployment_id = p_deployment
              ORDER BY session_date LOOP
        v_sessions := v_sessions + 1;
        v_s := greatest(0, v_s - (r.session_return - v_mean) / v_sd - v_k);
        v_peak := greatest(v_peak, v_s);
        IF v_alarm_at IS NULL AND v_s > v_h THEN
            v_alarm_at := r.session_date;
        END IF;
        IF r.stage = 'forward' THEN
            v_n_fwd := v_n_fwd + 1;
            IF v_n_fwd <= v_required THEN
                v_sum_fwd := v_sum_fwd + r.session_return;
            END IF;
        END IF;
    END LOOP;

    IF v_required IS NULL OR v_n_fwd < v_required THEN
        v_band := jsonb_build_object('verdict', 'pending', 'n', v_n_fwd, 'required', v_required,
            'mean', CASE WHEN v_n_fwd > 0 THEN v_sum_fwd / v_n_fwd END,
            'floor', CASE WHEN v_required IS NOT NULL
                          THEN v_mean - edge_monitor_band_z() * v_sd / sqrt(v_required) END);
    ELSE
        v_band := jsonb_build_object(
            'verdict', CASE WHEN v_sum_fwd / v_required
                                 >= v_mean - edge_monitor_band_z() * v_sd / sqrt(v_required)
                            THEN 'pass' ELSE 'fail' END,
            'n', v_required, 'required', v_required,
            'mean', v_sum_fwd / v_required,
            'floor', v_mean - edge_monitor_band_z() * v_sd / sqrt(v_required));
    END IF;

    RETURN jsonb_build_object(
        'applies', true,
        'version', edge_monitor_version(),
        'holdout', jsonb_build_object('n', v_n_hold, 'mean', v_mean, 'sd', v_sd),
        'band', v_band,
        'cusum', jsonb_build_object('value', v_s, 'peak', v_peak, 'k', v_k, 'h', v_h,
                                    'sessions', v_sessions, 'alarm', v_alarm_at IS NOT NULL,
                                    'alarm_at', v_alarm_at));
END;
$$;

-- ── What the monitor did, for the spawner to deliver ────────────────────────
CREATE TABLE IF NOT EXISTS edge_monitor_events (
    id            BIGSERIAL   PRIMARY KEY,
    deployment_id BIGINT      NOT NULL REFERENCES edge_deployments (id) ON DELETE RESTRICT,
    kind          TEXT        NOT NULL,
    reason        TEXT        NOT NULL,
    health        JSONB       NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- Set once, by the spawner, when it has dispatched the notification.
    delivered_at  TIMESTAMPTZ,

    CONSTRAINT edge_monitor_events_kind_known CHECK (kind IN ('retired'))
);
CREATE INDEX IF NOT EXISTS edge_monitor_events_undelivered_idx
    ON edge_monitor_events (id) WHERE delivered_at IS NULL;

COMMENT ON TABLE edge_monitor_events IS
    'What the edge monitor did (030), oldest first; the spawner delivers each as an '
    'edge_decay notification and sets delivered_at.';

-- A record of what happened: only delivered_at may change, and only once.
CREATE OR REPLACE FUNCTION edge_monitor_events_kept()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'monitor event % is a record and is never deleted', OLD.id
            USING ERRCODE = 'check_violation';
    END IF;
    IF (to_jsonb(NEW) - 'delivered_at') IS DISTINCT FROM (to_jsonb(OLD) - 'delivered_at')
       OR (OLD.delivered_at IS NOT NULL AND NEW.delivered_at IS DISTINCT FROM OLD.delivered_at) THEN
        RAISE EXCEPTION 'monitor event % is kept as written: only delivered_at is set, once', OLD.id
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_edge_monitor_events_kept ON edge_monitor_events;
CREATE TRIGGER trg_edge_monitor_events_kept
    BEFORE UPDATE OR DELETE ON edge_monitor_events
    FOR EACH ROW EXECUTE FUNCTION edge_monitor_events_kept();

-- ── The counter, and the monitor, after every recorded session ──────────────
-- Re-created from 029: counts forward rows only (030), then runs both
-- tests and retires on a breach. SECURITY DEFINER: the runner's role can
-- write ledger rows, not deployments or events.
CREATE OR REPLACE FUNCTION edge_forward_sessions_count()
RETURNS TRIGGER
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE
    v_health JSONB;
    v_why    TEXT;
BEGIN
    UPDATE edge_deployments
       SET forward_sessions_observed =
           (SELECT count(*)::INTEGER FROM edge_forward_sessions
             WHERE deployment_id = NEW.deployment_id AND stage = 'forward')
     WHERE id = NEW.deployment_id;

    v_health := edge_deployment_health(NEW.deployment_id);
    IF NOT COALESCE((v_health ->> 'applies')::BOOLEAN, false) THEN
        RETURN NULL;
    END IF;
    IF v_health -> 'band' ->> 'verdict' = 'fail' THEN
        v_why := format(
            'monitor (%s): the first %s forward sessions averaged %s, below the band floor %s '
            '(holdout mean %s, sd %s, %s sessions)',
            v_health ->> 'version', v_health -> 'band' ->> 'n',
            round((v_health -> 'band' ->> 'mean')::NUMERIC, 6),
            round((v_health -> 'band' ->> 'floor')::NUMERIC, 6),
            round((v_health -> 'holdout' ->> 'mean')::NUMERIC, 6),
            round((v_health -> 'holdout' ->> 'sd')::NUMERIC, 6),
            v_health -> 'holdout' ->> 'n');
    ELSIF (v_health -> 'cusum' ->> 'alarm')::BOOLEAN THEN
        v_why := format(
            'monitor (%s): the CUSUM passed %s on %s after %s sessions (k %s): they stopped '
            'behaving like the holdout (mean %s, sd %s)',
            v_health ->> 'version', round((v_health -> 'cusum' ->> 'h')::NUMERIC, 3),
            v_health -> 'cusum' ->> 'alarm_at', v_health -> 'cusum' ->> 'sessions',
            round((v_health -> 'cusum' ->> 'k')::NUMERIC, 4),
            round((v_health -> 'holdout' ->> 'mean')::NUMERIC, 6),
            round((v_health -> 'holdout' ->> 'sd')::NUMERIC, 6));
    END IF;
    IF v_why IS NULL THEN
        RETURN NULL;
    END IF;
    UPDATE edge_deployments SET stage = 'retired', retired_reason = v_why
     WHERE id = NEW.deployment_id AND stage <> 'retired';
    IF FOUND THEN
        INSERT INTO edge_monitor_events (deployment_id, kind, reason, health)
        VALUES (NEW.deployment_id, 'retired', v_why, v_health);
    END IF;
    RETURN NULL;
END;
$$;

-- The promotion guard, re-created from 029 with 030's rules added (marked).
CREATE OR REPLACE FUNCTION edge_deployments_promotion_guard()
RETURNS TRIGGER AS $$
DECLARE
    v_class    TEXT;
    v_verdict  TEXT;
    v_selected JSONB;
    v_finished TIMESTAMPTZ;
    v_health   JSONB;
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
    -- ledger's count of forward rows for this deployment (030: forward rows).
    IF NEW.forward_sessions_observed IS DISTINCT FROM OLD.forward_sessions_observed
       AND NEW.forward_sessions_observed IS DISTINCT FROM
           (SELECT count(*)::INTEGER FROM edge_forward_sessions
             WHERE deployment_id = NEW.id AND stage = 'forward') THEN
        RAISE EXCEPTION
            'forward_sessions_observed is counted from edge_forward_sessions '
            '(% forward rows for deployment %), not set: got %',
            (SELECT count(*) FROM edge_forward_sessions
              WHERE deployment_id = NEW.id AND stage = 'forward'),
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
        -- 030: a deployment the monitor can't judge doesn't start forward.
        -- (OLD's row is what health reads: the update isn't applied yet, and
        -- what it reads — experiment, requirement — is the same in NEW.)
        v_health := edge_deployment_health(NEW.id);
        IF NOT COALESCE((v_health ->> 'applies')::BOOLEAN, false)
           AND (v_health ->> 'why') NOT LIKE 'a low-frequency edge%' THEN
            RAISE EXCEPTION
                'backtest->forward refused: %; forward sessions would have nothing '
                'to be judged against', v_health ->> 'why'
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
        -- 030: and the forward sessions must look like the backtest's.
        v_health := edge_deployment_health(NEW.id);
        IF COALESCE((v_health ->> 'applies')::BOOLEAN, false) THEN
            IF v_health -> 'band' ->> 'verdict' IS DISTINCT FROM 'pass' THEN
                RAISE EXCEPTION
                    'forward->live requires the forward band to have passed (it is %: '
                    'mean % against a floor of %)', v_health -> 'band' ->> 'verdict',
                    v_health -> 'band' ->> 'mean', v_health -> 'band' ->> 'floor'
                    USING ERRCODE = 'check_violation';
            END IF;
        ELSIF (v_health ->> 'why') NOT LIKE 'a low-frequency edge%' THEN
            RAISE EXCEPTION
                'forward->live refused: %', v_health ->> 'why'
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
    'The forward ledger (EDGE_PROCESS §5, §7): one row per session a runner replayed, '
    'append-only, recorded as it happens, through forward and live; '
    'edge_deployments.forward_sessions_observed counts its forward rows, and '
    'edge_deployment_health() judges them (030).';
