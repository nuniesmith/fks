-- =============================================================================
-- 015_net_worth_stale_provenance.sql
--
-- Mark the net-worth rows that were recorded from a FROZEN bot reading.
--
-- WHAT HAPPENED
-- On 2026-07-22 14:23–15:33Z the live spot bot lost DNS to every venue. Its
-- /status kept serving the last good figure and the sampler wrote that frozen
-- number every 5 minutes stamped ts=now(), producing 15 consecutive rows
-- identical to 18 decimal places. Two smaller instances exist (2026-07-11,
-- 2026-07-15). The sampler now refuses stale readings (fks-spawner #32/#33),
-- but the rows it already wrote are still in the series that feeds the D5
-- profit decomposition and the milestone detector.
--
-- WHY MARK RATHER THAN DELETE
-- This is durable financial history. Deleting rows destroys the evidence of an
-- incident and cannot be undone; re-labelling their provenance is reversible,
-- auditable, and leaves the incident visible to anyone who looks. Readers
-- exclude `bot_status_stale`, so derived figures are correct while the record
-- of what the sampler actually did stays intact.
--
-- WHY THE FIRST ROW OF EACH RUN IS KEPT
-- The first sample of a frozen run is a genuine reading — it was true at the
-- moment it was written. Only the REPEATS are fabrication, so `pos > 1`.
--
-- ⚠ SCOPED TO crypto-spot ON PURPOSE — DO NOT GENERALISE ⚠
-- The funding bot's series is piecewise-constant BY DESIGN: it marks its book
-- on realized PnL, not mark-to-market. 29 of its 30 net-worth changes coincide
-- with a paper-trade exit record. It has legitimate runs of 500+ identical
-- rows spanning days. A "remove consecutive duplicates" sweep would destroy
-- its entire treasury history. Repetition is an anomaly for crypto-spot
-- (5,206 samples, every one unique except these three runs) and is NORMAL for
-- crypto-funding. Any future cleanup must re-establish that per-bot, not
-- assume it.
--
-- Bounded to ts < 2026-07-27 (when the staleness guard went live) so this is a
-- one-time historical remediation and never silently re-applies to new data.
-- Idempotent: only rows still labelled 'bot_status' are touched.
-- =============================================================================

BEGIN;

WITH s AS (
    SELECT id, ts, net_worth,
           ROW_NUMBER() OVER (ORDER BY ts)
         - ROW_NUMBER() OVER (PARTITION BY net_worth ORDER BY ts) AS grp
    FROM net_worth_snapshots
    WHERE bot_id = 'crypto-spot'
      AND source = 'bot_status'
      AND ts < TIMESTAMPTZ '2026-07-27 00:00:00+00'
), ranked AS (
    SELECT id,
           ROW_NUMBER() OVER (PARTITION BY net_worth, grp ORDER BY ts) AS pos,
           COUNT(*)     OVER (PARTITION BY net_worth, grp)             AS run_len
    FROM s
)
UPDATE net_worth_snapshots n
   SET source = 'bot_status_stale'
  FROM ranked r
 WHERE n.id = r.id
   AND r.run_len >= 3   -- a run this long cannot be real for a marked-to-market book
   AND r.pos > 1;       -- keep the first (genuine) reading of each run

COMMIT;

-- Reversal, if this ever proves wrong:
--   UPDATE net_worth_snapshots SET source = 'bot_status'
--    WHERE source = 'bot_status_stale';
