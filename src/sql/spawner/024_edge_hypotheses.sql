-- ============================================================================
-- 024_edge_hypotheses.sql — stage 2 of the edge process: the hypothesis,
-- registered BEFORE the search
-- ============================================================================
-- WHY. EDGE_PROCESS_2026-10-26 §2: the idea, its dataset and split, its
-- parameters and ranges, its baseline and its metric net of costs are written
-- down before the first trial runs, and "a hypothesis written after the
-- results is a description, not a test". edge_experiments (017) records a
-- SEARCH: it needs n_trials > 0 and a verdict, so it cannot hold an idea that
-- has not been searched yet. This table holds the idea from the moment it is
-- registered, and the experiment that searches it points back here.
--
-- WHAT THE DATABASE GUARANTEES, so no code path can quietly undo it:
--   1. Once registered, the hypothesis is FROZEN: its idea, dataset, split,
--      parameters, baseline, metric, costs and registration time cannot be
--      edited. Changing any of them is a new hypothesis (a new row, a new
--      registration time). Only the status may change: registered ->
--      withdrawn, with a reason, and withdrawn is terminal.
--   2. A hypothesis is never deleted. A withdrawn one still counts: it is part
--      of what was tried.
--   3. An experiment that names a hypothesis cannot have finished before the
--      hypothesis was registered (U2 in EDGE_PROCESS §3-4).
--
-- registered_at comes from the column default (the API never sends it), and
-- the guards fire on UPDATE and DELETE only, so a data-only restore of this
-- table keeps its original registration times.
--
-- The † thresholds of EDGE_PROCESS §9 (holdout share, trade counts, ...) are
-- NOT enforced here: they are proposals until confirmed, and the search job
-- reads them from its config. The CHECKs below only refuse nonsense.
-- ============================================================================

\getenv fks_db   RUBY_DB

\connect :fks_db

CREATE TABLE IF NOT EXISTS edge_hypotheses (
    id               BIGSERIAL   PRIMARY KEY,

    -- The edge this is a hypothesis about (edges, 008). RESTRICT: an edge
    -- with registered hypotheses is soft-deleted (active = FALSE), never
    -- dropped from under them.
    edge_id          TEXT        NOT NULL
                                 REFERENCES edges (edge_id) ON DELETE RESTRICT,

    -- §2.1 The idea in one sentence, with the mechanism.
    idea             TEXT        NOT NULL,
    -- §2.2 The data and the split. `dataset` names it in words (the lake
    -- folder and the date range) until dataset manifests exist (plan 4.1,
    -- 4.3); `holdout_share` is the last part of the window that nothing
    -- touches until the holdout is scored once.
    symbols          TEXT[]      NOT NULL,
    dataset          TEXT        NOT NULL,
    holdout_share    DOUBLE PRECISION NOT NULL,
    -- §2.3 The parameters and their ranges, few of them:
    --   [{"name": "lookback", "min": 10, "max": 200, "step": 10},
    --    {"name": "side", "choices": ["long", "short"]}]
    params           JSONB       NOT NULL,
    -- §2.4 What the edge must beat on the same holdout, and §2.5 the score,
    -- net of these costs (bps): {"maker_bps": 40, "taker_bps": 80,
    -- "slippage_bps": 5} is Kraken tier 1 plus a stated slippage.
    baseline         TEXT        NOT NULL,
    metric           TEXT        NOT NULL,
    costs            JSONB       NOT NULL,

    registered_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- The web UI user (or API token) that registered it.
    registered_by    TEXT,

    status           TEXT        NOT NULL DEFAULT 'registered',
    withdrawn_reason TEXT,
    withdrawn_at     TIMESTAMPTZ,

    CONSTRAINT edge_hypotheses_status_known
        CHECK (status IN ('registered', 'withdrawn')),
    CONSTRAINT edge_hypotheses_withdrawn_has_reason
        CHECK (status <> 'withdrawn' OR (withdrawn_reason IS NOT NULL AND withdrawn_at IS NOT NULL)),
    CONSTRAINT edge_hypotheses_idea_written
        CHECK (length(btrim(idea)) >= 20),
    CONSTRAINT edge_hypotheses_symbols_named
        CHECK (cardinality(symbols) >= 1),
    CONSTRAINT edge_hypotheses_dataset_named
        CHECK (length(btrim(dataset)) > 0),
    CONSTRAINT edge_hypotheses_holdout_sane
        CHECK (holdout_share > 0 AND holdout_share < 1),
    CONSTRAINT edge_hypotheses_params_listed
        CHECK (jsonb_typeof(params) = 'array' AND jsonb_array_length(params) >= 1),
    CONSTRAINT edge_hypotheses_costs_object
        CHECK (jsonb_typeof(costs) = 'object'),
    CONSTRAINT edge_hypotheses_baseline_named
        CHECK (length(btrim(baseline)) > 0),
    CONSTRAINT edge_hypotheses_metric_named
        CHECK (length(btrim(metric)) > 0)
);

CREATE INDEX IF NOT EXISTS edge_hypotheses_edge_idx
    ON edge_hypotheses (edge_id, registered_at DESC);

COMMENT ON TABLE edge_hypotheses IS
    'Stage 2 of the edge process: an idea registered before its search, frozen once '
    'registered. The search that tests it is an edge_experiments row pointing here.';
COMMENT ON COLUMN edge_hypotheses.registered_at IS
    'Set by the database at registration. An experiment that names this hypothesis '
    'must finish after it (U2).';

-- ── 1 + 2: frozen once registered, never deleted ────────────────────────────
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
       OR NEW.registered_at IS DISTINCT FROM OLD.registered_at
       OR NEW.registered_by IS DISTINCT FROM OLD.registered_by THEN
        RAISE EXCEPTION
            'hypothesis % is frozen since it was registered (%): its idea, data, '
            'split, parameters, baseline, metric and costs cannot change. Register '
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

DROP TRIGGER IF EXISTS trg_edge_hypotheses_frozen ON edge_hypotheses;
CREATE TRIGGER trg_edge_hypotheses_frozen
    BEFORE UPDATE OR DELETE ON edge_hypotheses
    FOR EACH ROW EXECUTE FUNCTION edge_hypotheses_frozen();

-- ── 3: the experiment that searches a hypothesis comes after it ─────────────
ALTER TABLE edge_experiments
    ADD COLUMN IF NOT EXISTS hypothesis_id BIGINT
        REFERENCES edge_hypotheses (id) ON DELETE RESTRICT;

CREATE INDEX IF NOT EXISTS edge_experiments_hypothesis_idx
    ON edge_experiments (hypothesis_id);

COMMENT ON COLUMN edge_experiments.hypothesis_id IS
    'The registered hypothesis this search tests (024). Its registered_at must come '
    'before this row''s finished_at.';

CREATE OR REPLACE FUNCTION edge_experiments_after_hypothesis()
RETURNS TRIGGER AS $$
DECLARE
    v_registered TIMESTAMPTZ;
BEGIN
    IF NEW.hypothesis_id IS NULL THEN
        RETURN NEW;
    END IF;
    SELECT registered_at INTO v_registered
      FROM edge_hypotheses WHERE id = NEW.hypothesis_id;
    IF NEW.finished_at IS NOT NULL AND NEW.finished_at <= v_registered THEN
        RAISE EXCEPTION
            'experiment % finished at %, before hypothesis % was registered (%): '
            'a hypothesis written after the result is a description, not a test',
            NEW.study_name, NEW.finished_at, NEW.hypothesis_id, v_registered
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_edge_experiments_after_hypothesis ON edge_experiments;
CREATE TRIGGER trg_edge_experiments_after_hypothesis
    BEFORE INSERT OR UPDATE OF hypothesis_id, finished_at ON edge_experiments
    FOR EACH ROW EXECUTE FUNCTION edge_experiments_after_hypothesis();

GRANT SELECT ON edge_hypotheses TO fks_webui;
