#!/usr/bin/env bash
# =============================================================================
# fks-state.sh — encrypted backup / restore of the FKS *private* state.
#
# Lets fks (and the bot repos) be PUBLIC by keeping everything sensitive
# OUT of the repo and in an encrypted, versioned snapshot stored in a private
# repo (default: github.com/nuniesmith/fks-state). The public repo ships only
# templates (.env.example, state.example/) + this tool + the manifest.
#
#   ./scripts/fks-state.sh init      one-time: make an age key + clone fks-state
#   ./scripts/fks-state.sh status    what would be backed up (no secret values)
#   ./scripts/fks-state.sh export    snapshot -> age-encrypt -> commit+push
#   ./scripts/fks-state.sh import    pull latest -> decrypt -> restore in place
#   ./scripts/fks-state.sh list      list snapshots in the private repo
#
# SECURITY MODEL
#   • One age keypair is the root secret. The PRIVATE key (~/.config/fks/age.key)
#     decrypts every snapshot — back it up out of band (password manager / paper /
#     hardware). It is the ONLY thing that is not itself recoverable from a backup.
#   • Snapshots are age-encrypted tarballs; the private repo is just transport.
#     Even if that repo leaked, the contents stay encrypted to your key.
#   • This script never prints secret *values* — only paths, sizes, and counts.
#
# DEPENDENCIES: age (one-time: `sudo apt install age` or the static binary from
#   github.com/FiloSottile/age/releases), git, tar, gzip. DB dumps use the
#   postgres *container* (docker compose exec) so no host pg_dump is needed.
# =============================================================================
set -euo pipefail

# ── Config (override via env) ────────────────────────────────────────────────
FKS_STATE_REPO="${FKS_STATE_REPO:-git@github.com:nuniesmith/fks-state.git}"
FKS_STATE_DIR="${FKS_STATE_DIR:-$HOME/.local/share/fks-state}"        # local clone of the private repo
FKS_AGE_KEY="${FKS_AGE_KEY:-$HOME/.config/fks/age.key}"               # your PRIVATE age identity
FKS_AGE_RECIPIENTS="${FKS_AGE_RECIPIENTS:-$HOME/.config/fks/recipients.txt}"  # public recipients (1+/line)
FKS_COMPOSE="${FKS_COMPOSE:-docker compose}"
POSTGRES_SERVICE="${POSTGRES_SERVICE:-postgres}"
POSTGRES_USER="${POSTGRES_USER:-fks_user}"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MANIFEST="${FKS_STATE_MANIFEST:-$REPO_ROOT/state.manifest}"
# Archive anchor: the manifest references sibling repos via `../fks-spawner`,
# `../fks-state`, so files live ABOVE REPO_ROOT. Anchor the snapshot at the
# parent dir and store every file by its path relative to it — a plain
# `files/<manifest-path>` layout collapsed the `..` out of the staging dir
# (the sibling configs escaped `files/` and import never restored them).
FKS_BASE="$(dirname "$REPO_ROOT")"
cd "$REPO_ROOT"

# ── Output helpers (never print secret values) ───────────────────────────────
log()  { printf '\033[36m[fks-state]\033[0m %s\n' "$*"; }
warn() { printf '\033[33m[fks-state] WARN:\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[31m[fks-state] ERROR:\033[0m %s\n' "$*" >&2; exit 1; }

need() { command -v "$1" >/dev/null 2>&1 || die "missing dependency: $1${2:+ — $2}"; }
need_age() {
  command -v age >/dev/null 2>&1 || die "age not installed (one-time): 'sudo apt install age' or https://github.com/FiloSottile/age/releases"
  command -v age-keygen >/dev/null 2>&1 || die "age-keygen not found (ships with age)"
}

# File lines carry an optional `file:` prefix (symmetric with `db:`); strip it
# so the remainder is a bare glob. Without the strip, `compgen -G "file:.env"`
# matched nothing and every file — incl. .env + the live bot configs — was
# silently skipped while the DB dump succeeded (looked like a working backup).
manifest_paths() { grep -vE '^\s*(#|$|db:)' "$MANIFEST" 2>/dev/null | sed -E 's/^\s*file:\s*//' || true; }
manifest_dbs()   { grep -E '^\s*db:' "$MANIFEST" 2>/dev/null | sed -E 's/^\s*db:\s*//' || true; }

# ── init ─────────────────────────────────────────────────────────────────────
cmd_init() {
  need_age; need git
  mkdir -p "$(dirname "$FKS_AGE_KEY")" "$(dirname "$FKS_AGE_RECIPIENTS")"
  if [[ -f "$FKS_AGE_KEY" ]]; then
    log "age identity already present: $FKS_AGE_KEY"
  else
    ( umask 077; age-keygen -o "$FKS_AGE_KEY" >/dev/null )
    chmod 600 "$FKS_AGE_KEY"
    warn "NEW age key at $FKS_AGE_KEY — BACK IT UP OUT OF BAND. It is the only thing that decrypts your state."
  fi
  local pub; pub="$(age-keygen -y "$FKS_AGE_KEY")"
  touch "$FKS_AGE_RECIPIENTS"
  grep -qxF "$pub" "$FKS_AGE_RECIPIENTS" || echo "$pub" >> "$FKS_AGE_RECIPIENTS"
  log "recipient (public, safe to share): $pub"
  if [[ ! -e "$MANIFEST" ]]; then
    cp "$REPO_ROOT/state.manifest.example" "$MANIFEST" 2>/dev/null \
      && log "wrote $MANIFEST from the example — edit it to match what you store" \
      || warn "no state.manifest.example to copy; create $MANIFEST by hand"
  fi
  if [[ ! -d "$FKS_STATE_DIR/.git" ]]; then
    log "cloning private state repo → $FKS_STATE_DIR"
    git clone "$FKS_STATE_REPO" "$FKS_STATE_DIR" 2>/dev/null || {
      warn "clone failed (repo may not exist yet). Creating a local one; push when ready."
      mkdir -p "$FKS_STATE_DIR/snapshots"
      ( cd "$FKS_STATE_DIR" && git init -q && git remote add origin "$FKS_STATE_REPO" 2>/dev/null || true )
    }
  fi
  log "init complete. Next: review $MANIFEST, then  $0 export"
}

# ── status ───────────────────────────────────────────────────────────────────
cmd_status() {
  [[ -f "$MANIFEST" ]] || die "no manifest at $MANIFEST (run: $0 init)"
  log "age identity: $( [[ -f $FKS_AGE_KEY ]] && echo "$FKS_AGE_KEY ($(age-keygen -y "$FKS_AGE_KEY" 2>/dev/null))" || echo 'MISSING — run init' )"
  log "manifest:     $MANIFEST"
  echo "  files/globs:"
  local any=0
  while IFS= read -r pat; do
    [[ -z "$pat" ]] && continue
    # shellcheck disable=SC2086
    local matches; matches=$(compgen -G "$pat" 2>/dev/null || true)
    if [[ -n "$matches" ]]; then
      while IFS= read -r f; do printf "    ✓ %-44s %s\n" "$f" "$(du -sh "$f" 2>/dev/null | cut -f1)"; any=1; done <<<"$matches"
    else
      printf "    · %-44s (no match — skipped)\n" "$pat"
    fi
  done < <(manifest_paths)
  echo "  database tables:"
  while IFS= read -r spec; do [[ -n "$spec" ]] && printf "    • %s\n" "$spec"; done < <(manifest_dbs)
  if $FKS_COMPOSE ps "$POSTGRES_SERVICE" >/dev/null 2>&1; then echo "    (postgres reachable via '$FKS_COMPOSE exec $POSTGRES_SERVICE')"; else warn "postgres container not up — DB tables will be skipped on export"; fi
  [[ -d "$FKS_STATE_DIR/snapshots" ]] && log "snapshots: $(ls -1 "$FKS_STATE_DIR"/snapshots/*.tar.age 2>/dev/null | wc -l) in $FKS_STATE_DIR"
}

# ── export ───────────────────────────────────────────────────────────────────
cmd_export() {
  need_age; need git; need tar
  [[ -f "$MANIFEST" ]] || die "no manifest at $MANIFEST (run: $0 init)"
  [[ -s "$FKS_AGE_RECIPIENTS" ]] || die "no recipients in $FKS_AGE_RECIPIENTS (run: $0 init)"
  [[ -d "$FKS_STATE_DIR" ]] || die "no state repo at $FKS_STATE_DIR (run: $0 init)"

  local ts stage; ts="$(date -u +%Y%m%dT%H%M%SZ)"
  stage="$(mktemp -d)"; trap 'rm -rf "$stage"' EXIT
  local payload="$stage/payload"; mkdir -p "$payload/files" "$payload/db"

  # Files: copy each manifest match, preserving relative path.
  while IFS= read -r pat; do
    [[ -z "$pat" ]] && continue
    local matches; matches=$(compgen -G "$pat" 2>/dev/null || true)
    [[ -z "$matches" ]] && { warn "skip (no match): $pat"; continue; }
    while IFS= read -r f; do
      # Store by path relative to FKS_BASE so `..` siblings survive the tar
      # (and import restores them to the right place). Refuse anything that
      # still escapes the anchor rather than silently mis-storing it.
      local rel; rel="$(realpath -m --relative-to="$FKS_BASE" "$f")"
      case "$rel" in
        ../*|/*) warn "skip (outside $FKS_BASE): $f"; continue ;;
      esac
      mkdir -p "$payload/files/$(dirname "$rel")"
      cp -a "$f" "$payload/files/$rel"
      log "+ file $rel"
    done <<<"$matches"
  done < <(manifest_paths)

  # DB tables: pg_dump --data-only inside the postgres container.
  if $FKS_COMPOSE ps "$POSTGRES_SERVICE" >/dev/null 2>&1; then
    while IFS= read -r spec; do
      [[ -z "$spec" ]] && continue
      local db tables targs; db="${spec%%:*}"; tables="${spec#*:}"; targs=()
      [[ "$tables" != "$spec" && -n "$tables" ]] && IFS=',' read -ra T <<<"$tables" && for t in "${T[@]}"; do targs+=(-t "$t"); done
      log "+ db   $db (${tables:-all tables})"
      $FKS_COMPOSE exec -T "$POSTGRES_SERVICE" pg_dump -U "$POSTGRES_USER" -d "$db" --data-only --no-owner "${targs[@]}" \
        > "$payload/db/$db.sql" || warn "pg_dump failed for $db (skipped)"
    done < <(manifest_dbs)
  else
    warn "postgres not up — DB tables skipped this snapshot"
  fi

  # Provenance (no secrets): what's in the snapshot + the git SHA it was taken at.
  { echo "created_utc=$ts"; echo "host=$(hostname)"; echo "repo_sha=$(git rev-parse --short HEAD 2>/dev/null || echo n/a)";
    echo "files=$(find "$payload/files" -type f | wc -l)"; echo "dbs=$(ls -1 "$payload/db" 2>/dev/null | wc -l)"; } > "$payload/MANIFEST.txt"

  # Tar + age-encrypt to every recipient.
  local out="$FKS_STATE_DIR/snapshots/fks-state-$ts.tar.gz.age"
  mkdir -p "$FKS_STATE_DIR/snapshots"
  local rargs=(); while IFS= read -r r; do [[ -n "$r" && "${r:0:1}" != "#" ]] && rargs+=(-r "$r"); done < "$FKS_AGE_RECIPIENTS"
  tar -C "$payload" -czf - . | age "${rargs[@]}" -o "$out"
  ln -sf "$(basename "$out")" "$FKS_STATE_DIR/snapshots/latest.tar.gz.age"
  log "encrypted snapshot → $out ($(du -sh "$out" | cut -f1))"

  ( cd "$FKS_STATE_DIR" && git add -A && git commit -q -m "snapshot $ts (${1:-manual})" \
      && { git push -q origin HEAD 2>/dev/null && log "pushed to $FKS_STATE_REPO" || warn "commit done; push failed (set the remote / create the repo, then 'git -C $FKS_STATE_DIR push')"; } )
  trap - EXIT; rm -rf "$stage"
}

# ── import ───────────────────────────────────────────────────────────────────
cmd_import() {
  need_age; need git; need tar
  [[ -f "$FKS_AGE_KEY" ]] || die "no age identity at $FKS_AGE_KEY (run: $0 init, or restore your key)"
  [[ -d "$FKS_STATE_DIR/.git" ]] && ( cd "$FKS_STATE_DIR" && git pull -q --ff-only 2>/dev/null || warn "pull skipped (offline / no upstream)" )
  local snap="${1:-latest}"
  [[ "$snap" == "latest" ]] && snap="$FKS_STATE_DIR/snapshots/latest.tar.gz.age"
  [[ -f "$snap" ]] || snap="$FKS_STATE_DIR/snapshots/$snap"
  [[ -f "$snap" ]] || die "snapshot not found: $snap (try: $0 list)"

  local stage; stage="$(mktemp -d)"; trap 'rm -rf "$stage"' EXIT
  # export archives the payload CONTENTS at the root (`tar -C "$payload" .`),
  # so the snapshot holds ./MANIFEST.txt, ./files/, ./db/ — there is no
  # `payload/` prefix. (This path referenced one, so restore never found a
  # single file.)
  age -d -i "$FKS_AGE_KEY" "$snap" | tar -C "$stage" -xzf -
  log "decrypted $(basename "$snap"):"; sed 's/^/    /' "$stage/MANIFEST.txt" 2>/dev/null || true

  if [[ "${DRY_RUN:-0}" == "1" ]]; then
    log "DRY RUN — files that WOULD be restored:"; ( cd "$stage/files" && find . -type f | sed 's|^\.|    '"$FKS_BASE"'|' )
    log "DB dumps available:"; ls -1 "$stage/db" 2>/dev/null | sed 's/^/    /'
    trap - EXIT; rm -rf "$stage"; return 0
  fi
  printf '\033[33mRestore over the working tree under %s? Existing files WILL be overwritten. [y/N] \033[0m' "$FKS_BASE"
  read -r ans; [[ "$ans" == "y" || "$ans" == "Y" ]] || die "aborted"

  ( cd "$stage/files" && tar -cf - . ) | tar -C "$FKS_BASE" -xf -
  log "restored files into $FKS_BASE"
  if compgen -G "$stage/db/*.sql" >/dev/null && $FKS_COMPOSE ps "$POSTGRES_SERVICE" >/dev/null 2>&1; then
    for f in "$stage"/db/*.sql; do
      local db; db="$(basename "$f" .sql)"
      log "restoring db rows → $db (psql)"; $FKS_COMPOSE exec -T "$POSTGRES_SERVICE" psql -q -U "$POSTGRES_USER" -d "$db" < "$f" || warn "psql restore had errors for $db (often duplicate rows — review)"
    done
  else
    warn "DB dumps present but postgres not up — start the stack and re-run, or load $stage manually"
  fi
  trap - EXIT; rm -rf "$stage"
  log "import complete."
}

cmd_list() { ls -1t "$FKS_STATE_DIR"/snapshots/*.tar.gz.age 2>/dev/null | sed 's|.*/||' || warn "no snapshots in $FKS_STATE_DIR"; }

# ── dispatch ─────────────────────────────────────────────────────────────────
case "${1:-}" in
  init)   cmd_init ;;
  status) cmd_status ;;
  export) shift; cmd_export "${1:-manual}" ;;
  import) shift; [[ "${1:-}" == "--dry-run" ]] && { DRY_RUN=1; shift; }; cmd_import "${1:-latest}" ;;
  list)   cmd_list ;;
  *) cat >&2 <<EOF
fks-state — encrypted backup/restore of the FKS private state.

  $0 init               one-time: create an age key + clone the private state repo
  $0 status             show what the manifest will back up (no secret values)
  $0 export [message]   snapshot -> age-encrypt -> commit+push to the private repo
  $0 import [--dry-run] [snapshot|latest]   pull -> decrypt -> restore in place
  $0 list               list available snapshots

Config via env: FKS_STATE_REPO, FKS_STATE_DIR, FKS_AGE_KEY, FKS_AGE_RECIPIENTS,
                FKS_COMPOSE, POSTGRES_SERVICE, POSTGRES_USER, FKS_STATE_MANIFEST.
See docs/STATE_BACKUP.md.
EOF
    exit 1 ;;
esac
