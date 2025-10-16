#!/usr/bin/env bash
# Purpose: Validation helpers (files, commands, ports)
# Exports: assert_file, assert_dir, assert_cmd, assert_port_free
set -euo pipefail
# shellcheck source=log.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/log.sh"

assert_file() { [[ -f "$1" ]] || { log_error "Required file missing: $1"; return 1; }; }
assert_dir() { [[ -d "$1" ]] || { log_error "Required dir missing: $1"; return 1; }; }
assert_cmd() { command -v "$1" >/dev/null 2>&1 || { log_error "Required command missing: $1"; return 127; }; }
assert_port_free() { local p=$1; (echo >/dev/tcp/127.0.0.1/$p) >/dev/null 2>&1 && { log_error "Port $p in use"; return 1; } || return 0; }

export -f assert_file assert_dir assert_cmd assert_port_free
