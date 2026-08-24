#!/usr/bin/env bash
# =============================================================================
# rithmic-secrets-refresh.sh — pull the webui-stored Rithmic credential out of
# exchange_secrets and stage it for `docker compose --profile rithmic up`.
#
# WHY THIS EXISTS. A credential entered through the webui's Rithmic form lands
# in `exchange_secrets`, encrypted at rest. `rithmic-connector` is a plain
# docker-compose service (not a spawner-managed bot), so it never goes through
# `inject_secrets` — the bridge every other broker uses. `export-secret-env`
# (fks-spawner #50) is that bridge for non-bot services: it runs INSIDE the
# spawner container (same trust boundary, same SPAWNER_SECRETS_KEY) and writes
# the decrypted value to a file — never returns it over HTTP, never logs it.
#
# WHY A SHELL-SOURCE STEP, NOT `env_file:` ON THE CONNECTOR SERVICE. Tested
# empirically 2026-08-24: docker compose reads a service's `env_file:` content
# ONCE, at the start of the whole `up` invocation — not fresh, just before
# that service's own container is created. A one-shot writer plus
# `depends_on: condition: service_completed_successfully` on the SAME `up` run
# would therefore read STALE (pre-write) content. The only reliable path is
# exporting the values into the INVOKING SHELL's environment before running
# `docker compose up`, so compose's `${RITHMIC_USER:-}` interpolation — which
# genuinely IS re-read fresh per invocation — picks up the current value.
#
# WHAT THIS SCRIPT NEVER DOES: print a credential value. It runs the export
# binary (which itself only logs var names, never values — see its own
# doc-comment), and this script's own output is limited to the exit status.
#
# USAGE
#   source scripts/rithmic-secrets-refresh.sh && \
#     docker compose --profile rithmic up -d rithmic-connector
#
# `source`, not execute — the whole point is to leave RITHMIC_USER/PASSWORD/
# SYSTEM_NAME exported in YOUR current shell for the next command. Running it
# as a subprocess (`./scripts/...sh`) would export into a shell that exits
# immediately after, achieving nothing.
# =============================================================================

_rithmic_secrets_refresh() {
  # Prefer $PWD over ${BASH_SOURCE[0]}-relative resolution. The latter is the
  # usual idiom for a self-locating script, but it silently resolved to the
  # WRONG directory (one level up, /home/jordan/github instead of .../fks) in
  # this platform's interactive/tool-driven shell sessions, where BASH_SOURCE
  # does not behave the way it does in a plain `bash script.sh` invocation —
  # confirmed reproducible even with a correct $PWD. A wrong-but-successful
  # path write is worse than a loud failure, so check for the repo's own
  # marker file rather than trust either source blindly.
  local repo_root="$PWD"
  if [ ! -f "$repo_root/docker-compose.yml" ]; then
    repo_root="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")/.." && pwd)"
  fi
  if [ ! -f "$repo_root/docker-compose.yml" ]; then
    echo "rithmic-secrets-refresh: can't find the fks repo root (checked \$PWD=$PWD)." >&2
    echo "  Run this from the repo root: cd ~/github/fks && source scripts/rithmic-secrets-refresh.sh" >&2
    return 1
  fi
  local secrets_dir="$repo_root/.secrets"
  local out_file="$secrets_dir/rithmic.env"

  mkdir -p "$secrets_dir"
  chmod 700 "$secrets_dir"
  # Placeholder so a FIRST-EVER run of a service that references this path via
  # env_file (not currently the case here, but keep the invariant true for any
  # future consumer) never hits compose's upfront existence check. Harmless if
  # the export below immediately overwrites it.
  [ -f "$out_file" ] || : > "$out_file"

  if ! docker ps --format '{{.Names}}' 2>/dev/null | grep -qx fks_bot_spawner; then
    echo "rithmic-secrets-refresh: fks_bot_spawner is not running — start the stack first" >&2
    return 1
  fi

  if ! docker exec fks_bot_spawner test -x /app/export-secret-env 2>/dev/null; then
    echo "rithmic-secrets-refresh: export-secret-env is not in the running spawner image." >&2
    echo "  Rebuild + recreate it first:" >&2
    echo "    docker compose build fks_bot_spawner && docker compose up -d --no-deps fks_bot_spawner" >&2
    return 1
  fi

  if ! docker exec fks_bot_spawner /app/export-secret-env \
    rithmic /secrets/rithmic.env \
    RITHMIC_USER=api_key RITHMIC_PASSWORD=api_secret RITHMIC_SYSTEM_NAME=api_passphrase; then
    echo "rithmic-secrets-refresh: export failed (see the line above — never a secret value)." >&2
    echo "  Common cause: no 'rithmic' row in exchange_secrets yet — add it via the webui" >&2
    echo "  (Settings -> API Keys -> Rithmic) before retrying." >&2
    return 1
  fi

  if [ ! -s "$out_file" ]; then
    echo "rithmic-secrets-refresh: export reported success but $out_file is empty — aborting" >&2
    return 1
  fi

  # NOT `source "$out_file"`. The file is .env-shaped (bare KEY=value, no
  # quoting) — correct for docker compose's own env_file parser, which treats
  # the right-hand side as an opaque string. bash `source` instead RE-PARSES
  # the file as shell code: a value containing a space (Rithmic system names
  # commonly do, e.g. "Rithmic Paper Trading") splits into a truncated
  # assignment plus a stray command bash tries to execute — hit exactly this
  # 2026-08-24, `source`ing this same file: `RITHMIC_SYSTEM_NAME` silently
  # became just "Rithmic" and bash printed
  # ".../rithmic.env: line 3: Paper: command not found". A wrong-but-non-empty
  # credential is worse than a loud failure, so parse it as data instead.
  local key value
  while IFS='=' read -r key value; do
    [ -n "$key" ] || continue
    export "$key=$value"
  done <"$out_file"
  echo "rithmic-secrets-refresh: RITHMIC_USER/RITHMIC_PASSWORD/RITHMIC_SYSTEM_NAME exported into this shell (values not shown)."
}

_rithmic_secrets_refresh
unset -f _rithmic_secrets_refresh
