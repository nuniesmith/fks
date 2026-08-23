#!/usr/bin/env bash
# =============================================================================
# questdb-integrity-probe.sh — publish QuestDB candle-table storage properties.
#
# WHY. The candle tables carry DEDUP UPSERT KEYS so a reconnect, a resubscribe,
# or overlapping ILP writes can never double-count a bar. That property is the
# foundation every edge measurement stands on: duplicated candles inflate
# volume, distort ranges, and quietly bias any backtest computed over them.
#
# It is also FRAGILE IN A SILENT WAY. QuestDB has no initdb/auto-migration, and
# ILP AUTO-CREATES A MISSING TABLE WITHOUT DEDUP. So if a candle table is ever
# dropped — a bad restore, a DR rehearsal, a manual cleanup — the next write
# recreates it de-duped-off and nothing anywhere says so. Rows keep arriving,
# dashboards keep drawing, and the corruption only shows up as an edge that
# quietly fails to replicate.
#
# This probe makes that state visible. It does not fix anything; alerting lives
# in infrastructure/config/prometheus/alerts/questdb-integrity.yml.
#
# Emits:
#   fks_questdb_table_dedup_enabled{table}  1 = dedup on, 0 = OFF (corruption risk)
#   fks_questdb_table_wal_enabled{table}    1 = WAL on   (dedup REQUIRES WAL)
#   fks_questdb_table_rows{table}           row count, for context in the alert
#   fks_questdb_integrity_probe_ok          1 = the probe itself queried QuestDB
# =============================================================================
set -uo pipefail

QDB="${QUESTDB_HTTP:-http://127.0.0.1:9000}"
DIR="${FKS_TEXTFILE_DIR:-/var/lib/node_exporter/textfile}"
OUT="$DIR/fks_questdb_integrity.prom"
# Tables whose dedup property is load-bearing. Others are ignored on purpose —
# a probe that reports on everything gets skimmed.
WATCH="${QUESTDB_WATCH_TABLES:-candles_crypto,candles_futures}"

[[ -d "$DIR" && -w "$DIR" ]] || {
  echo "questdb-integrity-probe: textfile dir '$DIR' missing or unwritable" >&2
  exit 1
}

emit() { { cat; } > "$OUT.tmp" && mv -f "$OUT.tmp" "$OUT"; }

q() { curl -s --max-time 15 -G "$QDB/exec" --data-urlencode "query=$1" 2>/dev/null; }

meta="$(q "SELECT table_name, dedup, walEnabled FROM tables();")"
if [[ -z "$meta" ]] || ! grep -q '"dataset"' <<<"$meta"; then
  emit <<EOF
# HELP fks_questdb_integrity_probe_ok Whether the probe could query QuestDB (1) or not (0).
# TYPE fks_questdb_integrity_probe_ok gauge
fks_questdb_integrity_probe_ok 0
EOF
  exit 0
fi

{
  echo "# HELP fks_questdb_table_dedup_enabled Whether DEDUP UPSERT KEYS is active (1) or OFF (0) — 0 means duplicate bars can accumulate silently."
  echo "# TYPE fks_questdb_table_dedup_enabled gauge"
  echo "# HELP fks_questdb_table_wal_enabled Whether the table is WAL-enabled (1); DEDUP requires WAL."
  echo "# TYPE fks_questdb_table_wal_enabled gauge"
  # NB: the script goes in -c, the JSON goes on stdin. A `python3 - <<'PY'`
  # heredoc PLUS a `<<<"$meta"` herestring is two stdin redirections on one
  # command — the herestring wins, python reads the JSON as its own source, and
  # you get `NameError: name 'true' is not defined` from parsing the payload.
  WATCH="$WATCH" python3 -c '
import json, os, sys
watch = [t.strip() for t in os.environ["WATCH"].split(",") if t.strip()]
seen = {r[0]: r for r in json.load(sys.stdin).get("dataset", [])}
for t in watch:
    r = seen.get(t)
    if r is None:
        # A watched table that does not exist yet is NOT reported as dedup=0 —
        # that would be indistinguishable from "exists with dedup off", which is
        # the actually-dangerous state. Absence is left to absent() in the rules.
        continue
    print(f"fks_questdb_table_dedup_enabled{{table=\"{t}\"}} {1 if r[1] else 0}")
    print(f"fks_questdb_table_wal_enabled{{table=\"{t}\"}} {1 if r[2] else 0}")
' <<<"$meta"
  echo "# HELP fks_questdb_table_rows Row count, for context when a dedup alert fires."
  echo "# TYPE fks_questdb_table_rows gauge"
  IFS=',' read -ra TABLES <<<"$WATCH"
  for t in "${TABLES[@]}"; do
    t="$(tr -d '[:space:]' <<<"$t")"
    [[ -n "$t" ]] || continue
    # Guard the table name: it comes from config, but interpolating anything
    # unvalidated into SQL is a habit worth not having.
    [[ "$t" =~ ^[A-Za-z0-9_]+$ ]] || continue
    n="$(q "SELECT count() FROM $t;" | python3 -c "
import json,sys
try: print(json.load(sys.stdin)['dataset'][0][0])
except Exception: print('')" 2>/dev/null)"
    [[ -n "$n" ]] && echo "fks_questdb_table_rows{table=\"$t\"} $n"
  done
  echo "# HELP fks_questdb_integrity_probe_ok Whether the probe could query QuestDB (1) or not (0)."
  echo "# TYPE fks_questdb_integrity_probe_ok gauge"
  echo "fks_questdb_integrity_probe_ok 1"
} | emit
