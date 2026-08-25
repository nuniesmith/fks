#!/usr/bin/env bash
# =============================================================================
# rithmic-connector-probe.sh — publish the Rithmic connector's health.
#
# WHY. The connector is the SOURCE of the bars the operator's morning ORB plan
# is built from — real prop-firm money is traded against those levels — and it
# had NO monitoring of any kind: it is not a Prometheus target, exposes no
# /metrics, and no alert rule mentioned it. Its only evidence of life was bars
# quietly appearing in QuestDB.
#
# That is not hypothetical. On 2026-08-24 the connector wrote NOTHING for eight
# minutes of the 09:30-09:45 opening window (all three symbols, contiguous)
# while reporting connected=true, persist_errors=0, and zero warnings. The
# resulting opening range was built from 2 of 3 five-minute bars — and a range
# missing its middle is TOO NARROW, which makes the stop too tight and the
# position too large. The day-plan disclosed it ("2/3 bars — window
# incomplete"), but only at 09:47, when the window had already passed.
#
# WHY AN EXTERNAL PROBE, not a /metrics endpoint on the connector. Adding one
# means changing, rebuilding and RESTARTING the connector — and a restart is
# exactly what costs opening-range bars, since Rithmic allows only ONE session
# per credential and re-login is not instant. This reads the /status the
# connector already serves and needs no restart, ever. If the connector later
# grows a real /metrics, retire this.
#
# Emits (node_exporter textfile collector, atomically):
#   fks_rithmic_connected              1 = session up
#   fks_rithmic_killed                 1 = operator RELEASED it (not a fault)
#   fks_rithmic_subscribed_instruments count
#   fks_rithmic_candles_written        counter — the liveness signal that matters
#   fks_rithmic_candles_persisted      counter
#   fks_rithmic_persist_errors         counter
#   fks_rithmic_probe_ok               1 = probe reached /status, 0 = could not
#
# The `killed` gauge is what keeps this from crying wolf: with ONE credential
# the operator MUST hand the session to R|Trader Pro to place a trade, so a
# disconnect is routine and expected. Alerting on `connected == 0` alone would
# page on every trade. The rules pair it with `killed == 0`.
#
# NOTE the metric names avoid `service`/`instance`/`job` as LABELS entirely —
# these arrive via the node_exporter textfile collector, whose scrape job sets
# static target labels that WIN over metric labels (see
# discord-digest-deadman.sh for the `service` -> `exported_service` trap this
# platform already hit once).
#
# Measurement only; alerting lives in
# infrastructure/config/prometheus/alerts/rithmic-connector.yml.
# =============================================================================
set -uo pipefail

URL="${RITHMIC_STATUS_URL:-http://127.0.0.1:9094/status}"
DIR="${FKS_TEXTFILE_DIR:-/var/lib/node_exporter/textfile}"
OUT="$DIR/fks_rithmic_connector.prom"
TIMEOUT="${RITHMIC_PROBE_TIMEOUT:-5}"

[[ -d "$DIR" && -w "$DIR" ]] || {
  echo "rithmic-connector-probe: textfile dir '$DIR' missing or unwritable" >&2
  exit 1
}

body=""
add() { body+="$1"$'\n'; }

# /status is unauthenticated by design (kill/resume are the guarded routes), so
# no token handling here — nothing secret passes through this probe.
status="$(curl -sS -m "$TIMEOUT" "$URL" 2>/dev/null)"
rc=$?

if [[ $rc -ne 0 || -z "$status" ]]; then
  # probe_ok=0 rather than emitting nothing: an ABSENT metric (timer stopped)
  # and a FAILING one (timer ran, connector unreachable) are different states
  # and the rules distinguish them. The connector is profile-gated and is
  # legitimately absent when RITHMIC_ENABLED is off, so this must not be
  # treated as an outage on its own.
  add "fks_rithmic_probe_ok 0"
else
  # Parse with python rather than grep: a truncated or non-JSON body must fail
  # the probe LOUDLY, not silently yield 0 for every gauge, which would read as
  # "connector down" and page on a probe bug.
  parsed="$(printf '%s' "$status" | python3 -c '
import json, sys
try:
    d = json.load(sys.stdin)
except Exception:
    sys.exit(1)
def num(v):
    if isinstance(v, bool):
        return 1 if v else 0
    return v if isinstance(v, (int, float)) else None
out = {
    "fks_rithmic_connected": num(d.get("connected")),
    "fks_rithmic_killed": num(d.get("killed")),
    "fks_rithmic_subscribed_instruments": num(d.get("subscribed_instruments")),
    "fks_rithmic_candles_written": num(d.get("candles_written")),
    "fks_rithmic_candles_persisted": num(d.get("candles_persisted")),
    "fks_rithmic_persist_errors": num(d.get("persist_errors")),
}
for k, v in out.items():
    if v is not None:
        print(f"{k} {v}")
' 2>/dev/null)"
  if [[ -z "$parsed" ]]; then
    add "fks_rithmic_probe_ok 0"
  else
    while IFS= read -r line; do
      [[ -n "$line" ]] && add "$line"
    done <<<"$parsed"
    add "fks_rithmic_probe_ok 1"
  fi
fi

{
  echo "# HELP fks_rithmic_connected Whether the Rithmic session is currently up (1) or not (0)."
  echo "# TYPE fks_rithmic_connected gauge"
  echo "# HELP fks_rithmic_killed Whether the operator has RELEASED the session via the kill switch (1) — an expected state with one credential, not a fault."
  echo "# TYPE fks_rithmic_killed gauge"
  echo "# HELP fks_rithmic_subscribed_instruments Number of instruments the session is subscribed to."
  echo "# TYPE fks_rithmic_subscribed_instruments gauge"
  echo "# HELP fks_rithmic_candles_written Candles the connector has produced since start."
  echo "# TYPE fks_rithmic_candles_written counter"
  echo "# HELP fks_rithmic_candles_persisted Candles successfully written to QuestDB since start."
  echo "# TYPE fks_rithmic_candles_persisted counter"
  echo "# HELP fks_rithmic_persist_errors QuestDB write failures since start."
  echo "# TYPE fks_rithmic_persist_errors counter"
  echo "# HELP fks_rithmic_probe_ok Whether this probe could read the connector's /status (1) or not (0)."
  echo "# TYPE fks_rithmic_probe_ok gauge"
  printf '%s' "$body"
} > "$OUT.tmp" && mv -f "$OUT.tmp" "$OUT"
