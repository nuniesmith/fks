#!/usr/bin/env bash
# =============================================================================
# discord-digest-deadman.sh — dead-man for the scheduled Discord digests.
#
# WHAT IT COVERS (FKS_DIGEST_SERVICES, "container=service" pairs):
#   fks_orb_briefing  briefing 08:30 ET + trade plan 10:00 ET, trading days
#   fks_advisor       daily digest 17:30 ET
#
# WHY. These messages are LIVE DECISION INPUTS — real prop-firm money is traded
# against the ORB plan, one manual futures position per morning. Neither service
# publishes a port, exposes /metrics, nor is scraped, and no alert rule mentioned
# either of them. Their only evidence of life was a Discord message arriving. A
# wedged scheduler or a dead webhook means the message never comes, which on a
# busy morning is easy to miss — the same silent-failure shape as the venue that
# sat dead for 13 days behind a green badge.
#
# HOW. Both services log the same two lines, so one parser covers both:
#     next: <kind> at Mon 2026-08-24 08:30 ET
#     sent <kind> to Discord (chunk 1/1, 691 chars)
#
# Keying the dead-man to the service's OWN next-due line makes it calendar-aware
# for free — orb-briefing computes that line with its trading calendar and
# holiday table, and advisor with its own (it runs weekends too). Re-deriving
# "should it have run today?" out here would duplicate both calendars and the
# copies would drift; a dead-man that cries wolf on Thanksgiving gets muted.
# It also checks the OUTCOME (a message went out) rather than process liveness,
# which is what a wedged-scheduler-in-a-healthy-process defeats.
#
# Emits (node_exporter textfile collector, atomically):
#   fks_digest_next_due_timestamp_seconds{digest_service,kind}
#   fks_digest_last_send_timestamp_seconds{digest_service,kind}
#   fks_digest_probe_ok{digest_service}   1 = probe read it, 0 = could not
#
# The label is `digest_service`, NOT `service`, and that is deliberate. These
# metrics reach Prometheus through the node_exporter textfile collector, and
# node-exporter's scrape job attaches a STATIC target label service="node-exporter".
# Target labels win: with honor_labels off (the default) a colliding metric
# label is renamed to `exported_service` and the target's value takes `service`.
# Every series then reports service="node-exporter" and any alert templated on
# {{ $labels.service }} names the wrong thing. Anything published via the
# textfile collector must avoid the target label names on that job.
#
# Measurement only; alerting lives in
# infrastructure/config/prometheus/alerts/discord-digests.yml.
# =============================================================================
set -uo pipefail

SERVICES="${FKS_DIGEST_SERVICES:-fks_orb_briefing=orb-briefing,fks_advisor=advisor}"
DIR="${FKS_TEXTFILE_DIR:-/var/lib/node_exporter/textfile}"
OUT="$DIR/fks_discord_digests.prom"
LOOKBACK="${FKS_DIGEST_LOOKBACK:-240h}" # spans a holiday weekend

[[ -d "$DIR" && -w "$DIR" ]] || {
  echo "discord-digest-deadman: textfile dir '$DIR' missing or unwritable" >&2
  exit 1
}

body=""
add() { body+="$1"$'\n'; }

IFS=',' read -ra PAIRS <<<"$SERVICES"
for pair in "${PAIRS[@]}"; do
  container="${pair%%=*}"; service="${pair##*=}"
  [[ -n "$container" && -n "$service" ]] || continue

  # Strip ANSI first — tracing logs with its colour layer on, so a naive grep
  # matches the escape sequences too.
  logs="$(docker logs "$container" --since "$LOOKBACK" 2>&1 | sed 's/\x1b\[[0-9;]*m//g')"
  if [[ $? -ne 0 || -z "$logs" ]]; then
    # ok=0 rather than emitting nothing: an ABSENT metric (timer stopped) and a
    # FAILING one (timer ran, service unreadable) are different states, and the
    # alert rules distinguish them.
    add "fks_digest_probe_ok{digest_service=\"$service\"} 0"
    continue
  fi

  # ONE forward event per service. Both schedulers keep a single "next" and
  # rewrite it after each send (orb-briefing alternates briefing -> plan), so
  # the most recent line of ANY kind is the only live one. Emitting a series
  # per kind leaves the just-superseded kind stuck in the past — 37h overdue
  # while nothing is wrong, which fires daily and gets muted in a week.
  nxt="$(grep -oE "next: [a-z]+ at [A-Za-z]{3} [0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2} ET" <<<"$logs" | tail -1)"
  if [[ -n "$nxt" ]]; then
    kind="$(awk '{print $2}' <<<"$nxt")"
    d="$(awk '{print $5}' <<<"$nxt")"; t="$(awk '{print $6}' <<<"$nxt")"
    # America/New_York resolves EST vs EDT for the date in question — never
    # hardcode an offset, these schedules straddle both halves of the year.
    if epoch="$(TZ=America/New_York date -d "$d $t" +%s 2>/dev/null)" && [[ -n "$epoch" ]]; then
      add "fks_digest_next_due_timestamp_seconds{digest_service=\"$service\",kind=\"$kind\"} $epoch"
    fi
  fi

  # Last send per kind IS meaningful per-kind (it is history, not a schedule).
  while IFS= read -r k; do
    [[ -n "$k" ]] || continue
    line="$(grep -oE "^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9:.]+Z .*sent ${k} to Discord" <<<"$logs" | tail -1)"
    [[ -n "$line" ]] || continue
    if e="$(date -u -d "$(awk '{print $1}' <<<"$line")" +%s 2>/dev/null)" && [[ -n "$e" ]]; then
      add "fks_digest_last_send_timestamp_seconds{digest_service=\"$service\",kind=\"$k\"} $e"
    fi
  done < <(grep -oE "sent [a-z]+ to Discord" <<<"$logs" | awk '{print $2}' | sort -u)

  add "fks_digest_probe_ok{digest_service=\"$service\"} 1"
done

{
  echo "# HELP fks_digest_next_due_timestamp_seconds Unix time the service itself says its next send is due (calendar/holiday-aware; parsed from its own log). One series per service."
  echo "# TYPE fks_digest_next_due_timestamp_seconds gauge"
  echo "# HELP fks_digest_last_send_timestamp_seconds Unix time a send of this kind last reached Discord."
  echo "# TYPE fks_digest_last_send_timestamp_seconds gauge"
  echo "# HELP fks_digest_probe_ok Whether the probe could read this service (1) or not (0)."
  echo "# TYPE fks_digest_probe_ok gauge"
  printf '%s' "$body"
} > "$OUT.tmp" && mv -f "$OUT.tmp" "$OUT"
