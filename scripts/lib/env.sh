#!/usr/bin/env bash
# Purpose: Environment & mode detection, .env loading (idempotent), namespace + root discovery
# Exports: detect_mode, load_dotenv, require_cmd, PROJECT_ROOT, SCRIPT_ROOT, PROJECT_NS

set -euo pipefail

SCRIPT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Root discovery: ascend until marker found or stop at filesystem root
_discover_root() {
  local probe="$SCRIPT_ROOT"
  [[ -n "${OVERRIDE_ROOT:-}" ]] && { echo "$OVERRIDE_ROOT"; return 0; }
  while [[ "$probe" != "/" ]]; do
    if [[ -f "$probe/.project-root" || -d "$probe/config" && -d "$probe/scripts" ]]; then
      echo "$probe"; return 0
    fi
    probe="$(dirname "$probe")"
  done
  echo "$SCRIPT_ROOT" # fallback
}
PROJECT_ROOT="$(_discover_root)"

# shellcheck source=log.sh
[[ -f "$SCRIPT_ROOT/log.sh" ]] && source "$SCRIPT_ROOT/log.sh"

: "${FKS_MODE:=}"
: "${PROJECT_NS:=fks}"
: "${CI:=false}"

_detect_ci() { [[ "${GITHUB_ACTIONS:-}" == "true" || "${CI}" == "true" ]]; }

detect_mode() {
  if [[ -n "$FKS_MODE" ]]; then echo "$FKS_MODE"; return 0; fi
  if _detect_ci; then echo "ci"; return 0; fi
  if [[ -n "${FKS_DEV:-}" ]]; then echo "dev"; return 0; fi
  echo "local"
}

# Load key=value lines from a .env style file
load_dotenv() {
  local file=${1:-.env}
  [[ -f "$file" ]] || { log_warn ".env file $file not found" || true; return 0; }
  while IFS= read -r line; do
    [[ -z "$line" || "$line" =~ ^# ]] && continue
    if [[ "$line" =~ ^[A-Za-z_][A-Za-z0-9_]*= ]]; then
      export "$line"
    fi
  done <"$file"
}

require_cmd() {
  local c
  for c in "$@"; do
    command -v "$c" >/dev/null 2>&1 || { log_error "Missing required command: $c"; return 127; }
  done
}

export -f detect_mode load_dotenv require_cmd
export PROJECT_NS PROJECT_ROOT SCRIPT_ROOT
