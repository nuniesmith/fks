-- =============================================================================
-- 028_hypothesis_evidence.sql — a hypothesis declares its evidence path
-- =============================================================================
-- EDGE_PROCESS §3–4: a low-frequency edge (a trend band trades about 3 times
-- a year per coin) can't reach U4's 30 holdout trades on any history we
-- have. It is judged on a different path instead: many coins with one shared
-- parameter set, pooled trades, results split by regime.
--
-- Which path applies is part of the hypothesis, so it is DECLARED at
-- registration and frozen with the rest. Choosing it after seeing the trade
-- count would be the post-hoc move pre-registration exists to stop.
--
--   evidence = 'trades'         U4 as written (default; every existing row)
--   evidence = 'low-frequency'  the job's low-frequency clause set
--                               (fks-spawner bots/edge-search, EDGE_PROCESS §9)
--
-- Re-creates edge_hypotheses_frozen() from 024 with `evidence` added to the
-- frozen columns; the trigger itself is unchanged. Idempotent.
-- Prerequisites: 024_edge_hypotheses.sql.
-- =============================================================================

\getenv fks_db RUBY_DB

\connect :fks_db

ALTER TABLE edge_hypotheses
    ADD COLUMN IF NOT EXISTS evidence TEXT NOT NULL DEFAULT 'trades';

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'edge_hypotheses_evidence_known'
          AND conrelid = 'edge_hypotheses'::regclass
    ) THEN
        ALTER TABLE edge_hypotheses
            ADD CONSTRAINT edge_hypotheses_evidence_known
            CHECK (evidence IN ('trades', 'low-frequency'));
    END IF;
END $$;

COMMENT ON COLUMN edge_hypotheses.evidence IS
    'The evidence path, declared at registration and frozen: trades (U4) or '
    'low-frequency (pooled trades over many coins, split by regime).';

CREATE OR REPLACE FUNCTION edge_hypotheses_frozen()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION
            'hypothesis % is registered and is never deleted: withdraw it with a '
            'reason instead (a withdrawn hypothesis still counts as tried)', OLD.id
            USING ERRCODE = 'check_violation';
    END IF;

    IF NEW.edge_id       IS DISTINCT FROM OLD.edge_id
       OR NEW.idea          IS DISTINCT FROM OLD.idea
       OR NEW.symbols       IS DISTINCT FROM OLD.symbols
       OR NEW.dataset       IS DISTINCT FROM OLD.dataset
       OR NEW.holdout_share IS DISTINCT FROM OLD.holdout_share
       OR NEW.params        IS DISTINCT FROM OLD.params
       OR NEW.baseline      IS DISTINCT FROM OLD.baseline
       OR NEW.metric        IS DISTINCT FROM OLD.metric
       OR NEW.costs         IS DISTINCT FROM OLD.costs
       OR NEW.evidence      IS DISTINCT FROM OLD.evidence
       OR NEW.registered_at IS DISTINCT FROM OLD.registered_at
       OR NEW.registered_by IS DISTINCT FROM OLD.registered_by THEN
        RAISE EXCEPTION
            'hypothesis % is frozen since it was registered (%): its idea, data, '
            'split, parameters, baseline, metric, costs and evidence path cannot change. Register '
            'a new hypothesis instead', OLD.id, OLD.registered_at
            USING ERRCODE = 'check_violation';
    END IF;

    IF OLD.status = 'withdrawn' AND (NEW.status <> 'withdrawn'
       OR NEW.withdrawn_reason IS DISTINCT FROM OLD.withdrawn_reason
       OR NEW.withdrawn_at IS DISTINCT FROM OLD.withdrawn_at) THEN
        RAISE EXCEPTION
            'hypothesis % was withdrawn (%), which is terminal: register a new one',
            OLD.id, OLD.withdrawn_reason
            USING ERRCODE = 'check_violation';
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
