#!/usr/bin/env bash
# =============================================================================
# backtest-runs-probe.sh — publish the edge factory's run outcomes.
#
# WHY. `backtest_runs` had NO metric and NO alert rule anywhere. That is exactly
# how TEN consecutive scheduled runs failed between 2026-07-19 and 08-16 — every
# one with `Docker API error: 404 No such image: fks-bot-backtest-orb:latest`,
# because the image had never been built — and nobody noticed for five weeks.
#
# The cost was not the failures. It was that the ORB go/no-go verdicts silently
# froze at 2026-07-13 while the operator kept trading against them, and ES was
# never evaluated at all despite being one of the three symbols in the plan.
#
# WHAT IT WATCHES, and why these three and not "did a run fail".
#
#   fks_backtest_last_success_timestamp_seconds
#     The one that matters. A verdict distilled from a run that stopped
#     succeeding gets stale, and staleness is invisible: the verdict file still
#     renders, still carries an as-of date, still looks authoritative.
#
#   fks_backtest_consecutive_failures
#     ONE failure is noise — a busy host, a transient pull. TEN IN A ROW is a
#     broken pipeline. Counting the streak since the last success distinguishes
#     them, where a naive "a run failed" alert would have fired on 2026-07-19,
#     been acknowledged as a blip, and then said nothing new for five weeks.
#
#   fks_backtest_runs_total{status}
#     Context for a human reading the alert, not an alerting signal itself.
#
# NOTE the labels avoid `service`/`instance`/`job`: these arrive via the
# node_exporter textfile collector, whose scrape job sets STATIC target labels
# that win over metric labels. See discord-digest-deadman.sh for the
# `service` -> `exported_service` trap this platform already hit once.
#
# Measurement only; alerting lives in
# infrastructure/config/prometheus/alerts/edge-factory.yml.
# =============================================================================
set -uo pipefail

DIR="${FKS_TEXTFILE_DIR:-/var/lib/node_exporter/textfile}"
OUT="$DIR/fks_backtest_runs.prom"
CONTAINER="${FKS_POSTGRES_CONTAINER:-fks_postgres}"
DB="${FKS_BACKTEST_DB:-fks_db}"
DBUSER="${FKS_BACKTEST_DB_USER:-fks_user}"

[[ -d "$DIR" && -w "$DIR" ]] || {
  echo "backtest-runs-probe: textfile dir '$DIR' missing or unwritable" >&2
  exit 1
}

q() { docker exec "$CONTAINER" psql -U "$DBUSER" -d "$DB" -tAc "$1" 2>/dev/null; }

body=""
add() { body+="$1"$'\n'; }

# Probe reachability FIRST. A psql failure and a genuinely empty table both
# yield no rows, and they are opposite situations: one is an outage, the other
# is a factory that has simply never run.
if ! probe="$(q "SELECT 1")" || [[ "$probe" != "1" ]]; then
  add "fks_backtest_probe_ok 0"
else
  add "fks_backtest_probe_ok 1"

  last_ok="$(q "SELECT COALESCE(EXTRACT(EPOCH FROM max(finished_at))::bigint, 0) FROM backtest_runs WHERE status = 'completed'")"
  [[ -n "$last_ok" ]] && add "fks_backtest_last_success_timestamp_seconds ${last_ok}"

  # Failures NEWER than the newest success. Counting "since the last success"
  # rather than "in the last N days" is what makes one blip and a dead pipeline
  # distinguishable — and it self-clears the moment a run succeeds, with no
  # window to tune.
  streak="$(q "
    SELECT count(*) FROM backtest_runs
    WHERE status = 'failed'
      AND started_at > COALESCE(
        (SELECT max(started_at) FROM backtest_runs WHERE status = 'completed'),
        '-infinity'::timestamptz)")"
  [[ -n "$streak" ]] && add "fks_backtest_consecutive_failures ${streak}"

  while IFS='|' read -r st n; do
    [[ -n "$st" ]] || continue
    add "fks_backtest_runs_total{status=\"${st}\"} ${n}"
  done < <(q "SELECT status||'|'||count(*) FROM backtest_runs GROUP BY status")
fi

{
  echo "# HELP fks_backtest_probe_ok Whether this probe could read backtest_runs (1) or not (0)."
  echo "# TYPE fks_backtest_probe_ok gauge"
  echo "# HELP fks_backtest_last_success_timestamp_seconds Unix time the newest backtest run COMPLETED. 0 = never."
  echo "# TYPE fks_backtest_last_success_timestamp_seconds gauge"
  echo "# HELP fks_backtest_consecutive_failures Failed runs started since the last successful one."
  echo "# TYPE fks_backtest_consecutive_failures gauge"
  echo "# HELP fks_backtest_runs_total Runs by terminal status, for context when reading an alert."
  echo "# TYPE fks_backtest_runs_total gauge"
  printf '%s' "$body"
} > "$OUT.tmp" && mv -f "$OUT.tmp" "$OUT"
