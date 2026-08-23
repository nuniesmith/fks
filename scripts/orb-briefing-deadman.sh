#!/usr/bin/env bash
# =============================================================================
# orb-briefing-deadman.sh — emit a Prometheus dead-man for the ORB briefing.
#
# WHY THIS EXISTS. `orb-briefing` sends the operator a Discord briefing at
# 08:30 ET and a trade plan at 10:00 ET each trading day, and those messages are
# a LIVE DECISION INPUT — real prop-firm money is traded against them. The
# service publishes no ports, exposes no /metrics, is not scraped, and no alert
# rule mentions it. If the scheduler wedges or the Discord webhook dies, the
# message simply never arrives and nothing says so. That is the same silent-
# failure shape as the venue that sat dead for 13 days behind a green badge.
#
# WHY IT READS THE SERVICE'S OWN SCHEDULE. After every send the service logs:
#
#     next: briefing at Mon 2026-08-24 08:30 ET
#
# That line is computed with the service's own trading calendar and holiday
# table, so keying the dead-man to it is holiday-aware FOR FREE. Re-deriving
# "was today a trading day?" out here would duplicate holidays.rs and the two
# copies would drift — and a dead-man that cries wolf on Thanksgiving is a
# dead-man that gets muted.
#
# It also checks the OUTCOME (a message was actually sent) rather than mere
# process liveness. A wedged scheduler in a healthy process is exactly the
# failure a liveness probe misses.
#
# Emits (atomically, node_exporter textfile collector):
#   fks_orb_briefing_next_due_timestamp_seconds{kind}  when the next send is due
#   fks_orb_briefing_last_send_timestamp_seconds{kind} when one last went out
#   fks_orb_briefing_deadman_ok                        1 = script itself ran fine
#
# Deliberately NOT alerting in here: this only measures. Alerting lives in
# infrastructure/config/prometheus/alerts/orb-briefing.yml so it is reviewable
# and testable like every other rule.
# =============================================================================
set -uo pipefail

CONTAINER="${ORB_BRIEFING_CONTAINER:-fks_orb_briefing}"
DIR="${FKS_TEXTFILE_DIR:-/var/lib/node_exporter/textfile}"
OUT="$DIR/fks_orb_briefing.prom"
LOOKBACK="${ORB_DEADMAN_LOOKBACK:-240h}" # long enough to span a holiday weekend

[[ -d "$DIR" && -w "$DIR" ]] || {
  echo "orb-briefing-deadman: textfile dir '$DIR' missing or unwritable" >&2
  exit 1
}

emit() { { cat; } > "$OUT.tmp" && mv -f "$OUT.tmp" "$OUT"; }

# Strip ANSI colour before parsing — the service logs with tracing's ANSI layer
# on, so a naive grep matches the escape sequences too.
logs="$(docker logs "$CONTAINER" --since "$LOOKBACK" 2>&1 | sed 's/\x1b\[[0-9;]*m//g')"
rc=$?

if [[ $rc -ne 0 || -z "$logs" ]]; then
  # Container gone, renamed, or no output. Emit ok=0 rather than nothing: an
  # ABSENT metric and a FAILING metric are different states and the alert
  # rules distinguish them (absent = the timer stopped; 0 = the timer ran and
  # could not see the service).
  emit <<EOF
# HELP fks_orb_briefing_deadman_ok Whether the ORB briefing dead-man probe could read the service (1) or not (0).
# TYPE fks_orb_briefing_deadman_ok gauge
fks_orb_briefing_deadman_ok 0
EOF
  exit 0
fi

# "next: briefing at Mon 2026-08-24 08:30 ET" -> kind=briefing, due=<unix>
#
# CRITICAL: there is exactly ONE forward schedule, not one per kind. The
# service alternates briefing -> plan -> briefing and rewrites a single "next:"
# line after each send, so the most recent line of ANY kind is the only live
# one. An earlier version of this script emitted a series per kind, which left
# the just-superseded kind sitting permanently in the past (37h overdue while
# nothing was wrong) — an alert keyed to that would have fired every single day
# and been muted within a week.
#
# Emits ONE series; `kind` is a descriptive label on it, not a series key.
parse_next() {
  local line
  line="$(grep -oE "next: (briefing|plan) at [A-Za-z]{3} [0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2} ET" <<<"$logs" | tail -1)"
  [[ -n "$line" ]] || return 1
  local kind d t epoch
  kind="$(awk '{print $2}' <<<"$line")"
  d="$(awk '{print $5}' <<<"$line")"
  t="$(awk '{print $6}' <<<"$line")"
  # America/New_York resolves EST vs EDT correctly for the date in question —
  # do NOT hardcode an offset, the briefing straddles both halves of the year.
  epoch="$(TZ=America/New_York date -d "$d $t" +%s 2>/dev/null)" || return 1
  [[ -n "$epoch" ]] || return 1
  printf '%s %s\n' "$kind" "$epoch"
}

parse_last_send() {
  local kind="$1" line
  line="$(grep -oE "^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9:.]+Z .*sent ${kind} to Discord" <<<"$logs" | tail -1)"
  [[ -n "$line" ]] || return 1
  date -u -d "$(awk '{print $1}' <<<"$line")" +%s 2>/dev/null
}

{
  echo "# HELP fks_orb_briefing_next_due_timestamp_seconds Unix time the service itself says its next send is due (holiday-aware; parsed from its own log). Exactly one series — the scheduler has a single forward event."
  echo "# TYPE fks_orb_briefing_next_due_timestamp_seconds gauge"
  if nxt="$(parse_next)" && [[ -n "$nxt" ]]; then
    echo "fks_orb_briefing_next_due_timestamp_seconds{kind=\"${nxt%% *}\"} ${nxt##* }"
  fi
  echo "# HELP fks_orb_briefing_last_send_timestamp_seconds Unix time a send last reached Discord."
  echo "# TYPE fks_orb_briefing_last_send_timestamp_seconds gauge"
  for k in briefing plan; do
    if v="$(parse_last_send "$k")" && [[ -n "$v" ]]; then
      echo "fks_orb_briefing_last_send_timestamp_seconds{kind=\"$k\"} $v"
    fi
  done
  echo "# HELP fks_orb_briefing_deadman_ok Whether the ORB briefing dead-man probe could read the service (1) or not (0)."
  echo "# TYPE fks_orb_briefing_deadman_ok gauge"
  echo "fks_orb_briefing_deadman_ok 1"
} | emit
