#!/usr/bin/env bash
# Purpose: Central error trapping & graceful aborts
# Exports: die, with_temp_dir
set -euo pipefail
# shellcheck source=log.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/log.sh"

_die_cleanup() { :; }

die() { local code=${2:-1}; log_error "$1"; exit "$code"; }

with_temp_dir() {
  local td
  td="$(mktemp -d 2>/dev/null || mktemp -d -t fks)"
  trap 'rm -rf "$td" || true' EXIT
  ( cd "$td" && "$@" )
}

_trap_err() { local ec=$?; log_error "Unexpected error (exit=$ec) at ${BASH_SOURCE[1]}:${BASH_LINENO[0]}"; exit "$ec"; }
trap _trap_err ERR

export -f die with_temp_dir
