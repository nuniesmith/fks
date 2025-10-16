#!/usr/bin/env bash
# Purpose: Central logging utilities with consistent formatting & colors / JSON.
# Safe to source multiple times.
# Exports: log_debug, log_info, log_warn, log_error, log_success, LOG_LEVEL, LOG_FORMAT

set -euo pipefail

: "${LOG_LEVEL:=INFO}"      # DEBUG|INFO|WARN|ERROR
: "${LOG_FORMAT:=plain}"    # plain|json

if [[ -t 1 && "${NO_COLOR:-}" == "" && "$LOG_FORMAT" != "json" ]]; then
  _CLR_RESET='\033[0m'
  _CLR_DIM='\033[2m'
  _CLR_RED='\033[0;31m'
  _CLR_GREEN='\033[0;32m'
  _CLR_YELLOW='\033[1;33m'
  _CLR_BLUE='\033[0;34m'
  _CLR_MAGENTA='\033[0;35m'
else
  _CLR_RESET=''; _CLR_DIM=''; _CLR_RED=''; _CLR_GREEN=''; _CLR_YELLOW=''; _CLR_BLUE=''; _CLR_MAGENTA=''
fi

_ts() { date -u +'%Y-%m-%dT%H:%M:%SZ'; }
_lvl_enabled() {
  local want=$1
  case "$LOG_LEVEL:$want" in
    DEBUG:DEBUG) return 0 ;;
    DEBUG:INFO|DEBUG:WARN|DEBUG:ERROR) return 0 ;;
    INFO:INFO|INFO:WARN|INFO:ERROR) return 0 ;;
    WARN:WARN|WARN:ERROR) return 0 ;;
    ERROR:ERROR) return 0 ;;
  esac
  return 1
}
_emit_plain() {
  local ts=$1 level=$2 color=$3 icon=$4 msg=$5
  printf '%s %b[%s]%b %b%s%b\n' "$ts" "$color" "$level" "$_CLR_RESET" "$icon " "$msg" "$_CLR_RESET" 1>&2
}
_emit_json() {
  local ts=$1 level=$2 msg=$3 icon=$4
  # minimal JSON escaping (no newlines expected in msg normally)
  local esc msg_json
  esc=${msg//"/\"}
  msg_json="{\"ts\":\"$ts\",\"level\":\"$level\",\"icon\":\"$icon\",\"msg\":\"$esc\"}"
  printf '%s\n' "$msg_json" 1>&2
}
_log() {
  local level=$1 color=$2 icon=$3 msg=${*:4}
  _lvl_enabled "$level" || return 0
  local ts; ts=$(_ts)
  if [[ "$LOG_FORMAT" == "json" ]]; then
    _emit_json "$ts" "$level" "$msg" "$icon"
  else
    _emit_plain "$ts" "$level" "$color" "$icon" "$msg"
  fi
}
log_debug() { _log DEBUG "$_CLR_DIM" '·' "$*"; }
log_info() { _log INFO "$_CLR_BLUE" 'ℹ' "$*"; }
log_warn() { _log WARN "$_CLR_YELLOW" '⚠' "$*"; }
log_error() { _log ERROR "$_CLR_RED" '✖' "$*"; }
log_success() { _log INFO "$_CLR_GREEN" '✔' "$*"; }

export -f log_debug log_info log_warn log_error log_success
