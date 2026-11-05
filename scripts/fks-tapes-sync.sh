#!/usr/bin/env bash
# =============================================================================
# fks-tapes-sync.sh — off-host copy of the recorder tapes nobody can re-record
# =============================================================================
#
# The lake (/srv/fks-lake) lives on one disk on oryx. Most of it can be
# fetched again (Binance Vision history, Databento, the CME cache), but the
# recorders' liquidation streams (forceOrder) cannot: Binance publishes no
# liquidation history, so a lost day is lost for good. H-LIQ-01 is
# preregistered on exactly that tape. Each recorder's _gaps/ ledger goes with
# it, because research reads a gap as missing data rather than a quiet market.
#
# The tapes are public market data and small (~1.5 MB a day across the
# recorders), so they go UNENCRYPTED into a private git repo, one file per
# recorder-day, at the same path they have under the lake. Only finished days
# are copied (file date before today, UTC): today's files are still being
# written. A finished day is immutable, so git stores each one once and the
# repo grows by the day's bytes, unlike fks-state's full nightly snapshots.
#
#   scripts/fks-tapes-sync.sh            copy new finished days, commit, push
#   scripts/fks-tapes-sync.sh --dry-run  list what would be copied, change nothing
#
# A destination file that already exists and differs is never overwritten,
# with one exception: a _gaps ledger that only GREW (the old copy is a byte
# prefix of the new one), as a gap that spans midnight can append to the
# finished day's ledger. Anything else is reported and fails the run.
#
# Env:
#   FKS_LAKE          lake root                     (/srv/fks-lake)
#   FKS_TAPES_DIR     clone of the private repo     (~/.local/share/fks-tapes)
#   FKS_TAPES_REMOTE  used only to clone if missing (git@github.com:nuniesmith/fks-tapes.git)
#   FKS_TAPES_GLOBS   space-separated globs relative to FKS_LAKE
#   FKS_TEXTFILE_DIR  node_exporter textfile dir    (/var/lib/node_exporter/textfile)
# =============================================================================
set -euo pipefail

FKS_LAKE="${FKS_LAKE:-/srv/fks-lake}"
FKS_TAPES_DIR="${FKS_TAPES_DIR:-$HOME/.local/share/fks-tapes}"
FKS_TAPES_REMOTE="${FKS_TAPES_REMOTE:-git@github.com:nuniesmith/fks-tapes.git}"
FKS_TAPES_GLOBS="${FKS_TAPES_GLOBS:-raw/binance/usdm/*/*/forceOrder/*.jsonl.gz raw/binance/usdm/*/_gaps/*.jsonl raw/binance/usdm/*/_legacy_import_*.jsonl}"
# GitHub refuses blobs over 100 MiB; stop well before that and say so.
MAX_BYTES=$((50 * 1024 * 1024))

DRY_RUN=0
case "${1:-}" in
  --dry-run) DRY_RUN=1 ;;
  "") ;;
  *) echo "usage: $0 [--dry-run]" >&2; exit 2 ;;
esac

log()  { printf '[fks-tapes] %s\n' "$*"; }
warn() { printf '[fks-tapes] WARN: %s\n' "$*" >&2; }

# Metric so a sync that stops is alertable (FksTapesSyncStale). Atomic, and a
# no-op when the textfile directory is missing or not writable.
emit_metric() {
  local ok="$1" files="${2:-}" dir="${FKS_TEXTFILE_DIR:-/var/lib/node_exporter/textfile}"
  [[ $DRY_RUN == 1 ]] && return 0
  [[ -d "$dir" && -w "$dir" ]] || return 0
  local f="$dir/fks_tapes_sync.prom"
  {
    echo "# HELP fks_tapes_sync_ok Whether the last tape sync reached the remote (1) or failed (0)."
    echo "# TYPE fks_tapes_sync_ok gauge"
    echo "fks_tapes_sync_ok $ok"
    if [[ $ok == 1 ]]; then
      echo "# HELP fks_tapes_sync_last_success_timestamp_seconds Unix time of the last sync that reached the remote."
      echo "# TYPE fks_tapes_sync_last_success_timestamp_seconds gauge"
      echo "fks_tapes_sync_last_success_timestamp_seconds $(date +%s)"
      echo "# HELP fks_tapes_files Tape files in the off-host copy."
      echo "# TYPE fks_tapes_files gauge"
      echo "fks_tapes_files $files"
    fi
  } > "$f.tmp" && mv -f "$f.tmp" "$f"
}
fail() { warn "$*"; emit_metric 0; exit 1; }

[[ -d "$FKS_LAKE" ]] || fail "no lake at $FKS_LAKE"
if [[ ! -d "$FKS_TAPES_DIR/.git" ]]; then
  [[ $DRY_RUN == 1 ]] && fail "no clone at $FKS_TAPES_DIR (run once without --dry-run to clone)"
  log "cloning $FKS_TAPES_REMOTE -> $FKS_TAPES_DIR"
  git clone -q "$FKS_TAPES_REMOTE" "$FKS_TAPES_DIR" || fail "clone failed"
fi

today="$(date -u +%F)"
copied=0 grown=0 same=0 conflicts=0

shopt -s nullglob
cd "$FKS_LAKE"
# shellcheck disable=SC2086  # the globs are meant to expand
for rel in $FKS_TAPES_GLOBS; do
  base="${rel##*/}"
  day="${base%%.*}"
  # Day files: finished days only. Other files (the legacy-import manifest)
  # carry no date and are immutable.
  if [[ $day =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ && ! $day < $today ]]; then continue; fi
  src="$FKS_LAKE/$rel" dst="$FKS_TAPES_DIR/$rel"
  size=$(stat -c %s "$src")
  (( size <= MAX_BYTES )) || fail "$rel is $size bytes, over the ${MAX_BYTES}-byte limit for git transport"
  if [[ ! -e "$dst" ]]; then
    copied=$((copied + 1))
    [[ $DRY_RUN == 1 ]] && { log "would copy $rel ($size bytes)"; continue; }
    mkdir -p "$(dirname "$dst")"
    cp --preserve=timestamps "$src" "$dst.part" && mv -f "$dst.part" "$dst"
  elif cmp -s "$src" "$dst"; then
    same=$((same + 1))
  elif [[ $rel == */_gaps/* ]] && cmp -s -n "$(stat -c %s "$dst")" "$src" "$dst"; then
    grown=$((grown + 1))
    [[ $DRY_RUN == 1 ]] && { log "would update grown ledger $rel"; continue; }
    cp --preserve=timestamps "$src" "$dst.part" && mv -f "$dst.part" "$dst"
  else
    conflicts=$((conflicts + 1))
    warn "CHANGED after it was copied, left as is: $rel"
  fi
done

log "new $copied, grown ledgers $grown, unchanged $same, conflicts $conflicts"
[[ $DRY_RUN == 1 ]] && exit 0

cd "$FKS_TAPES_DIR"
git add -A
if ! git diff --cached --quiet; then
  git commit -q -m "tapes through $(date -u -d yesterday +%F): +$copied new, $grown grown ledgers"
fi
# Push even when nothing new was committed: an earlier run may have
# committed and then failed to push.
if [[ -n "$(git rev-list '@{u}..HEAD' 2>/dev/null || git rev-list HEAD 2>/dev/null)" ]]; then
  git push -q -u origin HEAD:main 2>&1 || fail "push failed (commits are only local)"
  log "pushed to $(git remote get-url origin)"
fi
(( conflicts == 0 )) || fail "$conflicts file(s) changed after copying; see the warnings above"

emit_metric 1 "$(git ls-files | wc -l)"
log "ok"
