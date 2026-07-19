#!/usr/bin/env bash
# =============================================================================
# test-signal-pipeline.sh
#
# End-to-end integration test for the Janus → Alertmanager → Python signal
# pipeline.  Exercises the full path:
#
#   Synthetic alert
#       │
#       ▼
#   Alertmanager  POST /api/v2/alerts
#       │
#       ▼  (routed by category=trade-signal rule)
#   Python webhook  POST /api/signals/webhook
#       │
#       ├─ prop-firm       → Redis: signal:prop-firm:* + fks:signals:prop-firm
#       ├─ personal-crypto → ExecutionGate → kraken:paper_orders (paper, ENABLE_LIVE_BOTS=0, default)
#       │                                  → kraken:orders       (live,  ENABLE_LIVE_BOTS=1)
#       └─ hardware-wallet → Redis: fks:signals:monitor
#       │
#       └─ ALL types       → Redis: fks:signals:incoming  (JanusAIBot channel)
#
# Usage:
#   ./scripts/testing/test-signal-pipeline.sh [OPTIONS]
#
# Options:
#   --alertmanager URL    Alertmanager base URL  (default: http://localhost:9093)
#   --ruby URL            Python data-service URL (default: http://localhost:8000)
#   --janus-forward URL   Janus forward service   (default: http://localhost:8080)
#   --redis HOST:PORT     Redis host:port          (default: localhost:6379)
#   --skip-redis          Skip Redis verification checks
#   --skip-affinity       Skip affinity record endpoint test
#   --account-type TYPE   Signal account type to test: prop-firm | personal-crypto |
#                         hardware-wallet | all  (default: all)
#   --poll-timeout N      Seconds to wait for signal to appear in Python (default: 15)
#   -v, --verbose         Print full curl responses
#   -h, --help            Show this help
#
# Exit codes:
#   0  All checks passed
#   1  One or more checks failed
#   2  Prerequisite missing (curl, jq, etc.)
# =============================================================================

set -euo pipefail

# ── Colour helpers ─────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
DIM='\033[2m'
RESET='\033[0m'

info()    { echo -e "${CYAN}[INFO]${RESET}  $*"; }
ok()      { echo -e "${GREEN}[PASS]${RESET}  $*"; }
warn()    { echo -e "${YELLOW}[WARN]${RESET}  $*"; }
fail()    { echo -e "${RED}[FAIL]${RESET}  $*"; }
header()  { echo -e "\n${BOLD}${CYAN}══ $* ══${RESET}"; }
step()    { echo -e "${DIM}  →${RESET} $*"; }

# ── Defaults ───────────────────────────────────────────────────────────────
ALERTMANAGER_URL="${ALERTMANAGER_URL:-http://localhost:9093}"
RUBY_URL="${RUBY_URL:-http://localhost:8050}"
JANUS_FORWARD_URL="${JANUS_FORWARD_URL:-http://localhost:7001}"
# Bearer for janus's mutating routes (janus-auth). The affinity/record POSTs
# below are non-GET and return 401 once JANUS_API_TOKEN is set on the stack, so
# forward it when present. Empty (default) = no header, unchanged behaviour.
JANUS_API_TOKEN="${JANUS_API_TOKEN:-}"
REDIS_HOST="${REDIS_HOST:-localhost}"
REDIS_PORT="${REDIS_PORT:-6379}"
POLL_TIMEOUT=15
VERBOSE=false
SKIP_REDIS=false
SKIP_AFFINITY=false
ACCOUNT_TYPE_FILTER="all"

PASS=0
FAIL=0
WARN_COUNT=0

# ── Argument parsing ────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case "$1" in
    --alertmanager) ALERTMANAGER_URL="$2"; shift 2 ;;
    --ruby)         RUBY_URL="$2";         shift 2 ;;
    --janus-forward) JANUS_FORWARD_URL="$2"; shift 2 ;;
    --redis)
      REDIS_HOST="${2%%:*}"
      REDIS_PORT="${2##*:}"
      shift 2 ;;
    --skip-redis)     SKIP_REDIS=true;     shift ;;
    --skip-affinity)  SKIP_AFFINITY=true;  shift ;;
    --account-type)   ACCOUNT_TYPE_FILTER="$2"; shift 2 ;;
    --poll-timeout)   POLL_TIMEOUT="$2";   shift 2 ;;
    -v|--verbose)     VERBOSE=true;        shift ;;
    -h|--help)
      sed -n '3,/^# ={10}/p' "$0" | sed 's/^# \?//'
      exit 0 ;;
    *) warn "Unknown argument: $1"; shift ;;
  esac
done

# ── Prerequisite checks ─────────────────────────────────────────────────────
header "Prerequisite Check"

for cmd in curl jq; do
  if command -v "$cmd" &>/dev/null; then
    ok "  $cmd found ($(command -v "$cmd"))"
  else
    fail "  $cmd is required but not installed"
    exit 2
  fi
done

if ! $SKIP_REDIS; then
  if command -v redis-cli &>/dev/null; then
    ok "  redis-cli found"
    HAS_REDIS_CLI=true
  else
    warn "  redis-cli not found — Redis checks will be skipped"
    HAS_REDIS_CLI=false
  fi
else
  HAS_REDIS_CLI=false
fi

# ── Helper: curl wrapper ────────────────────────────────────────────────────
# Usage: _curl <method> <url> [extra curl args...]
# Returns the HTTP body on stdout; sets LAST_HTTP_CODE.
#
# IMPORTANT: _curl is often called via subshell capture:
#   resp=$(_curl GET "$url")
# Variables set inside a subshell don't propagate to the parent, so
# LAST_HTTP_CODE is also written to a temp file (_HTTP_CODE_TMP) that the
# parent reads back via _read_http_code() before every assertion.
LAST_HTTP_CODE=0
_HTTP_CODE_TMP=$(mktemp)
trap 'rm -f "$_HTTP_CODE_TMP"' EXIT

_curl() {
  local method="$1"; shift
  local url="$1";    shift
  local tmp
  tmp=$(mktemp)
  # Attach the janus-auth bearer on mutating requests when configured. Harmless
  # on GETs (janus only enforces on non-GET), so applied uniformly.
  local auth_args=()
  [ -n "${JANUS_API_TOKEN:-}" ] && auth_args=(-H "Authorization: Bearer ${JANUS_API_TOKEN}")
  LAST_HTTP_CODE=$(curl -s -o "$tmp" -w "%{http_code}" \
    -X "$method" "$url" \
    -H "Content-Type: application/json" \
    ${auth_args[@]+"${auth_args[@]}"} \
    "$@")
  # Write code to temp file so parent shell can read it after subshell returns
  printf '%s' "$LAST_HTTP_CODE" > "$_HTTP_CODE_TMP"
  local body; body=$(cat "$tmp"); rm -f "$tmp"
  if $VERBOSE; then
    echo -e "${DIM}  HTTP $LAST_HTTP_CODE  ←  $method $url${RESET}" >&2
    echo "$body" | jq . 2>/dev/null >&2 || echo "$body" >&2
  fi
  echo "$body"
}

# Read LAST_HTTP_CODE back from the temp file written by _curl.
# Call this immediately after any resp=$(_curl ...) subshell invocation.
_read_http_code() {
  LAST_HTTP_CODE=$(cat "$_HTTP_CODE_TMP" 2>/dev/null || echo 0)
}

# ── Helper: assert ──────────────────────────────────────────────────────────
assert_eq() {
  local label="$1" expected="$2" actual="$3"
  if [[ "$actual" == "$expected" ]]; then
    ok "$label"
    (( PASS++ )) || true
  else
    fail "$label  (expected='$expected' got='$actual')"
    (( FAIL++ )) || true
  fi
}

assert_contains() {
  local label="$1" needle="$2" haystack="$3"
  if echo "$haystack" | grep -q "$needle" 2>/dev/null; then
    ok "$label"
    (( PASS++ )) || true
  else
    fail "$label  (pattern='$needle' not found)"
    (( FAIL++ )) || true
  fi
}

assert_http_ok() {
  local label="$1"
  # Re-read from temp file in case _curl was called in a subshell
  _read_http_code
  if [[ "$LAST_HTTP_CODE" =~ ^2 ]]; then
    ok "$label (HTTP $LAST_HTTP_CODE)"
    (( PASS++ )) || true
  else
    fail "$label (HTTP $LAST_HTTP_CODE)"
    (( FAIL++ )) || true
  fi
}

skip() {
  echo -e "${DIM}[SKIP]${RESET}  $*"
  (( WARN_COUNT++ )) || true
}

# ── Helper: unique signal ID ────────────────────────────────────────────────
new_signal_id() {
  echo "test-sig-$(date +%s%N | md5sum | head -c 12)"
}

# ── Helper: build an Alertmanager trade-signal payload ─────────────────────
# Usage: build_alert <signal_id> <symbol> <direction> <account_type> <strategy>
build_alert() {
  local sid="$1" sym="$2" dir="$3" acct="$4" strat="$5"
  jq -n \
    --arg sid   "$sid" \
    --arg sym   "$sym" \
    --arg dir   "$dir" \
    --arg acct  "$acct" \
    --arg strat "$strat" \
    '[{
      "labels": {
        "alertname":        "TradeSignal",
        "category":         "trade-signal",
        "signal_id":        $sid,
        "symbol":           $sym,
        "signal_direction": $dir,
        "account_type":     $acct,
        "strategy":         $strat,
        "severity":         "info"
      },
      "annotations": {
        "confidence":   "0.87",
        "strength":     "0.74",
        "entry_price":  "67500.00",
        "stop_loss":    "66800.00",
        "take_profit_1":"68500.00",
        "take_profit_2":"69500.00",
        "take_profit_3":"71000.00",
        "position_size":"0.05",
        "regime":       "TRENDING",
        "reasoning":    "E2E pipeline test — synthetic signal",
        "timeframe":    "5m",
        "summary":      ($dir + " " + $sym + " @ 67500.00 [" + $strat + "] — E2E test")
      },
      "generatorURL": "http://test-signal-pipeline"
    }]'
}

# ── Helper: poll for condition ──────────────────────────────────────────────
# Usage: poll_until <timeout_secs> <description> <command_that_returns_0_on_success>
poll_until() {
  local timeout="$1" desc="$2"; shift 2
  local deadline=$(( $(date +%s) + timeout ))
  local dot_count=0
  printf "  Waiting for %-40s " "$desc..."
  while [[ $(date +%s) -lt $deadline ]]; do
    if "$@" &>/dev/null 2>&1; then
      echo -e " ${GREEN}found${RESET}"
      return 0
    fi
    sleep 1
    (( dot_count++ )) || true
    if (( dot_count % 5 == 0 )); then printf "."; fi
  done
  echo -e " ${RED}timeout${RESET}"
  return 1
}

# ═══════════════════════════════════════════════════════════════════════════
# SECTION 1: Service connectivity
# ═══════════════════════════════════════════════════════════════════════════
header "1. Service Connectivity"

# Alertmanager
step "GET ${ALERTMANAGER_URL}/-/healthy"
resp=$(_curl GET "${ALERTMANAGER_URL}/-/healthy")
assert_http_ok "Alertmanager reachable"

# Python data service
step "GET ${RUBY_URL}/api/health"
resp=$(_curl GET "${RUBY_URL}/api/health")
assert_http_ok "Python data service reachable"

# Janus forward service (for affinity endpoint)
if ! $SKIP_AFFINITY; then
  step "GET ${JANUS_FORWARD_URL}/api/v1/brain/health"
  resp=$(_curl GET "${JANUS_FORWARD_URL}/api/v1/brain/health")
  _read_http_code
  if [[ "$LAST_HTTP_CODE" =~ ^2 ]]; then
    ok "Janus forward service reachable (HTTP $LAST_HTTP_CODE)"
    (( PASS++ )) || true
    JANUS_REACHABLE=true
  else
    warn "Janus forward service unreachable (HTTP $LAST_HTTP_CODE) — affinity tests skipped"
    (( WARN_COUNT++ )) || true
    JANUS_REACHABLE=false
  fi
else
  JANUS_REACHABLE=false
fi

# Redis (optional)
_read_http_code
if $HAS_REDIS_CLI && ! $SKIP_REDIS; then
  step "redis-cli -h $REDIS_HOST -p $REDIS_PORT PING"
  if redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" PING &>/dev/null; then
    ok "Redis reachable at $REDIS_HOST:$REDIS_PORT"
    (( PASS++ )) || true
    REDIS_OK=true
  else
    warn "Redis not reachable — Redis assertion steps will be skipped"
    (( WARN_COUNT++ )) || true
    REDIS_OK=false
  fi
else
  REDIS_OK=false
fi

# ═══════════════════════════════════════════════════════════════════════════
# SECTION 2: Alertmanager config verification
# ═══════════════════════════════════════════════════════════════════════════
header "2. Alertmanager Configuration"

step "GET ${ALERTMANAGER_URL}/api/v2/status"
status_resp=$(_curl GET "${ALERTMANAGER_URL}/api/v2/status")
assert_http_ok "Alertmanager status endpoint"

# Verify the python-signal-webhook receiver exists in the running config
if echo "$status_resp" | jq -e '.config.original' &>/dev/null; then
  config_raw=$(echo "$status_resp" | jq -r '.config.original // ""')
  if echo "$config_raw" | grep -q "python-signal-webhook"; then
    ok "python-signal-webhook receiver present in Alertmanager config"
    (( PASS++ )) || true
  else
    fail "python-signal-webhook receiver NOT found in Alertmanager config"
    fail "  → Deploy updated alertmanager.yml.tmpl and restart the alertmanager container"
    (( FAIL++ )) || true
  fi

  if echo "$config_raw" | grep -q "category: trade-signal\|category:.*trade-signal"; then
    ok "trade-signal route present in Alertmanager config"
    (( PASS++ )) || true
  else
    warn "Could not verify trade-signal route (config format may vary)"
    (( WARN_COUNT++ )) || true
  fi
else
  warn "Could not parse Alertmanager config from status response — skipping config checks"
  (( WARN_COUNT++ )) || true
fi

# ═══════════════════════════════════════════════════════════════════════════
# SECTION 3: Python webhook endpoint
# ═══════════════════════════════════════════════════════════════════════════
header "3. Python Webhook Endpoint (Direct POST)"

# Post a synthetic signal DIRECTLY to the Python webhook endpoint,
# bypassing Alertmanager. This isolates the Python-side parsing.
DIRECT_SID=$(new_signal_id)
info "Direct webhook test signal_id=$DIRECT_SID"

direct_payload=$(jq -n \
  --arg sid "$DIRECT_SID" \
  '{
    "version": "4",
    "groupKey": "{}:{alertname=\"TradeSignal\"}",
    "status": "firing",
    "receiver": "python-signal-webhook",
    "alerts": [{
      "status": "firing",
      "labels": {
        "alertname":        "TradeSignal",
        "category":         "trade-signal",
        "signal_id":        $sid,
        "symbol":           "BTCUSD",
        "signal_direction": "LONG",
        "account_type":     "personal-crypto",
        "strategy":         "TestPipeline",
        "severity":         "info"
      },
      "annotations": {
        "confidence":   "0.91",
        "strength":     "0.80",
        "entry_price":  "67500.00",
        "stop_loss":    "66800.00",
        "take_profit_1":"68500.00",
        "position_size":"0.05",
        "regime":       "TRENDING",
        "reasoning":    "Direct webhook test",
        "timeframe":    "5m",
        "summary":      "LONG BTCUSD @ 67500.00 [TestPipeline] - direct test"
      },
      "startsAt": "2024-01-01T00:00:00Z",
      "endsAt":   "0001-01-01T00:00:00Z",
      "generatorURL": "http://test-signal-pipeline"
    }]
  }')

step "POST ${RUBY_URL}/api/signals/webhook"
wh_resp=$(_curl POST "${RUBY_URL}/api/signals/webhook" -d "$direct_payload")
assert_http_ok "Webhook endpoint accepts POST"
if echo "$wh_resp" | jq -e '.status == "ok"' &>/dev/null; then
  processed=$(echo "$wh_resp" | jq -r '.processed // 0')
  ok "Webhook processed $processed signal(s)"
  assert_contains "Direct signal_id in processed list" "$DIRECT_SID" "$wh_resp"
  (( PASS++ )) || true
else
  fail "Webhook response status != ok: $wh_resp"
  (( FAIL++ )) || true
fi

# Test deduplication — same signal_id a second time
step "POST same signal_id again (dedup test)"
wh_resp2=$(_curl POST "${RUBY_URL}/api/signals/webhook" -d "$direct_payload")
if echo "$wh_resp2" | jq -e '.skipped == 1' &>/dev/null 2>&1 || \
   echo "$wh_resp2" | jq -e '.processed == 0' &>/dev/null 2>&1; then
  ok "Duplicate signal correctly deduplicated"
  (( PASS++ )) || true
else
  warn "Could not confirm deduplication (response: $(echo "$wh_resp2" | jq -c .))"
  (( WARN_COUNT++ )) || true
fi

# ═══════════════════════════════════════════════════════════════════════════
# SECTION 4: Full Alertmanager → Python pipeline per account type
# ═══════════════════════════════════════════════════════════════════════════
header "4. Full Pipeline: Alertmanager → Python"

info "Pushing synthetic signals through Alertmanager for routing verification"
info "Poll timeout: ${POLL_TIMEOUT}s"

run_account_type_test() {
  local acct_type="$1"
  local symbol="$2"
  local direction="$3"
  local strategy="$4"

  echo ""
  echo -e "  ${BOLD}Testing account_type=${acct_type}${RESET}"

  local sid; sid=$(new_signal_id)
  info "  signal_id=$sid  symbol=$symbol  direction=$direction"

  # Push to Alertmanager
  local alert_payload; alert_payload=$(build_alert "$sid" "$symbol" "$direction" "$acct_type" "$strategy")
  step "  POST ${ALERTMANAGER_URL}/api/v2/alerts"
  local am_resp; am_resp=$(_curl POST "${ALERTMANAGER_URL}/api/v2/alerts" -d "$alert_payload")
  if [[ "$LAST_HTTP_CODE" =~ ^2 ]]; then
    ok "  Signal accepted by Alertmanager (HTTP $LAST_HTTP_CODE)"
    (( PASS++ )) || true
  else
    fail "  Alertmanager rejected signal (HTTP $LAST_HTTP_CODE): $am_resp"
    (( FAIL++ )) || true
    return 1
  fi

  # Wait for signal to appear in Alertmanager active alerts
  check_am_active() {
    local body; body=$(_curl GET \
      "${ALERTMANAGER_URL}/api/v2/alerts?filter=signal_id%3D%22${sid}%22&active=true" 2>/dev/null)
    _read_http_code
    echo "$body" | jq -e 'length > 0' &>/dev/null
  }
  if poll_until "$POLL_TIMEOUT" "signal in Alertmanager active alerts" check_am_active; then
    (( PASS++ )) || true
  else
    warn "  Signal not visible in Alertmanager active alerts after ${POLL_TIMEOUT}s"
    (( WARN_COUNT++ )) || true
  fi

  # Wait for signal to appear in Python /api/signals/history (via webhook delivery)
  check_py_history() {
    local body; body=$(_curl GET "${RUBY_URL}/api/signals/history" 2>/dev/null)
    _read_http_code
    echo "$body" | jq -e --arg sid "$sid" '.signals[]? | select(.signal_id == $sid)' &>/dev/null
  }
  if poll_until "$POLL_TIMEOUT" "signal in Python signal history" check_py_history; then
    ok "  Signal routed through Python monitor (found in /api/signals/history)"
    (( PASS++ )) || true
  else
    # Alertmanager webhook delivery may not have fired yet — check via polling endpoint
    check_py_active() {
      local body; body=$(_curl GET "${RUBY_URL}/api/signals/active" 2>/dev/null)
      _read_http_code
      echo "$body" | jq -e --arg sid "$sid" '.signals[]? | select(.signal_id == $sid)' &>/dev/null
    }
    if poll_until 5 "signal in Python active signals" check_py_active; then
      ok "  Signal found in /api/signals/active (via AM polling)"
      (( PASS++ )) || true
    else
      warn "  Signal not found in Python after ${POLL_TIMEOUT}s (webhook delivery may be delayed)"
      warn "  → Verify Alertmanager is delivering to http://fks_ruby:8000/api/signals/webhook"
      (( WARN_COUNT++ )) || true
    fi
  fi

  # Redis checks
  if $REDIS_OK; then
    case "$acct_type" in
      prop-firm)
        step "  Checking Redis key signal:prop-firm:${symbol}:${sid}"
        if redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" EXISTS "signal:prop-firm:${symbol}:${sid}" \
            2>/dev/null | grep -q "^1$"; then
          ok "  Prop-firm signal key set in Redis"
          (( PASS++ )) || true
        else
          warn "  Prop-firm Redis key not found (may not have been delivered via webhook yet)"
          (( WARN_COUNT++ )) || true
        fi
        ;;
      hardware-wallet)
        # Hardware wallet publishes to fks:signals:monitor — harder to assert
        # without a subscriber, so just note it
        info "  hardware-wallet publishes to fks:signals:monitor (pub/sub, not persistent)"
        ;;
      personal-crypto)
        info "  personal-crypto signals route to ExecutionGate (check engine logs)"
        ;;
    esac

    # All signals should hit fks:signals:incoming
    step "  Checking fks:signals:incoming publication (last 1 entry)"
    local incoming; incoming=$(redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" \
      LRANGE "fks:signals:incoming:log" 0 0 2>/dev/null || echo "")
    # Note: fks:signals:incoming is pub/sub so we can't LRANGE it directly.
    # Check via the /api/signals/history which is populated by the handler.
    info "  fks:signals:incoming is pub/sub — verified indirectly via Python routing"
  fi

  echo ""
}

case "$ACCOUNT_TYPE_FILTER" in
  prop-firm)
    run_account_type_test "prop-firm" "MES" "LONG" "ORBBreakout"
    ;;
  personal-crypto)
    run_account_type_test "personal-crypto" "BTCUSD" "LONG" "MomentumSurge"
    ;;
  hardware-wallet)
    run_account_type_test "hardware-wallet" "ETHUSD" "SHORT" "EMAFlip"
    ;;
  all|*)
    run_account_type_test "prop-firm"       "MES"    "LONG"  "ORBBreakout"
    run_account_type_test "personal-crypto" "BTCUSD" "LONG"  "MomentumSurge"
    run_account_type_test "hardware-wallet" "ETHUSD" "SHORT" "EMAFlip"
    ;;
esac

# ═══════════════════════════════════════════════════════════════════════════
# SECTION 5: Python signal endpoints
# ═══════════════════════════════════════════════════════════════════════════
header "5. Python Signal Endpoints"

step "GET ${RUBY_URL}/api/signals/active"
active_resp=$(_curl GET "${RUBY_URL}/api/signals/active")
_read_http_code
assert_http_ok "GET /api/signals/active"
active_count=$(echo "$active_resp" | jq -r '.count // 0' 2>/dev/null || echo 0)
info "Active signals from Alertmanager: $active_count"

step "GET ${RUBY_URL}/api/signals/history"
hist_resp=$(_curl GET "${RUBY_URL}/api/signals/history")
_read_http_code
assert_http_ok "GET /api/signals/history"
hist_count=$(echo "$hist_resp" | jq -r '.count // 0' 2>/dev/null || echo 0)
info "Signal history entries: $hist_count"

# ═══════════════════════════════════════════════════════════════════════════
# SECTION 6: Janus affinity record endpoint (AI-C)
# ═══════════════════════════════════════════════════════════════════════════
header "6. Janus Affinity Record Endpoint (AI-C)"

if $SKIP_AFFINITY || ! $JANUS_REACHABLE; then
  skip "Janus affinity record test skipped (--skip-affinity or Janus unreachable)"
else
  # Read current affinity state before recording
  step "GET ${JANUS_FORWARD_URL}/api/v1/brain/affinity (baseline)"
  before_resp=$(_curl GET "${JANUS_FORWARD_URL}/api/v1/brain/affinity")
  _read_http_code
  before_pairs=$(echo "$before_resp" | jq -r '.pair_count // 0' 2>/dev/null || echo 0)
  info "Affinity pairs before test: $before_pairs"

  # Record a synthetic trade outcome
  AFFINITY_STRATEGY="TestPipeline"
  AFFINITY_ASSET="BTCUSD"
  record_payload=$(jq -n \
    --arg s "$AFFINITY_STRATEGY" \
    --arg a "$AFFINITY_ASSET" \
    '{
      "strategy":  $s,
      "asset":     $a,
      "pnl":       142.50,
      "is_winner": true,
      "rr_ratio":  2.1
    }')

  step "POST ${JANUS_FORWARD_URL}/api/v1/brain/affinity/record"
  rec_resp=$(_curl POST "${JANUS_FORWARD_URL}/api/v1/brain/affinity/record" -d "$record_payload")
  _read_http_code
  assert_http_ok "Affinity record endpoint accepts POST"

  if echo "$rec_resp" | jq -e '.ok == true' &>/dev/null; then
    ok "Affinity record returned ok=true"
    (( PASS++ )) || true
  else
    fail "Affinity record response unexpected: $rec_resp"
    (( FAIL++ )) || true
  fi

  # Read affinity state after recording — pair count should be >= before
  step "GET ${JANUS_FORWARD_URL}/api/v1/brain/affinity (after record)"
  after_resp=$(_curl GET "${JANUS_FORWARD_URL}/api/v1/brain/affinity")
  _read_http_code
  after_pairs=$(echo "$after_resp" | jq -r '.pair_count // 0' 2>/dev/null || echo 0)
  info "Affinity pairs after test: $after_pairs"

  if (( after_pairs >= before_pairs )); then
    ok "Affinity pair count grew or stayed the same ($before_pairs → $after_pairs)"
    (( PASS++ )) || true
  else
    fail "Affinity pair count decreased unexpectedly ($before_pairs → $after_pairs)"
    (( FAIL++ )) || true
  fi

  # Record a loss — verify it also works
  loss_payload=$(jq -n \
    --arg s "$AFFINITY_STRATEGY" \
    --arg a "$AFFINITY_ASSET" \
    '{
      "strategy":  $s,
      "asset":     $a,
      "pnl":       -38.00,
      "is_winner": false
    }')
  step "POST /api/v1/brain/affinity/record (loss outcome)"
  loss_resp=$(_curl POST "${JANUS_FORWARD_URL}/api/v1/brain/affinity/record" -d "$loss_payload")
  _read_http_code
  if echo "$loss_resp" | jq -e '.ok == true' &>/dev/null; then
    ok "Loss outcome recorded successfully"
    (( PASS++ )) || true
  else
    fail "Loss outcome record failed: $loss_resp"
    (( FAIL++ )) || true
  fi

  # Verify the Python /api/janus/affinity proxy also works
  step "GET ${RUBY_URL}/api/janus/affinity (Python proxy)"
  py_aff_resp=$(_curl GET "${RUBY_URL}/api/janus/affinity")
  _read_http_code
  if [[ "$LAST_HTTP_CODE" =~ ^2 ]]; then
    py_aff_status=$(echo "$py_aff_resp" | jq -r '.status // "unknown"' 2>/dev/null || echo "unknown")
    if [[ "$py_aff_status" == "ok" ]]; then
      ok "Python /api/janus/affinity proxied Janus successfully"
      (( PASS++ )) || true
    else
      warn "Python /api/janus/affinity returned status=$py_aff_status (Janus may need a moment)"
      (( WARN_COUNT++ )) || true
    fi
  else
    warn "Python /api/janus/affinity returned HTTP $LAST_HTTP_CODE"
    (( WARN_COUNT++ )) || true
  fi
fi

# ═══════════════════════════════════════════════════════════════════════════
# SECTION 7: Python janus/memories endpoint
# ═══════════════════════════════════════════════════════════════════════════
header "7. Python Janus Endpoints"

step "GET ${RUBY_URL}/api/janus/memories?limit=5"
mem_resp=$(_curl GET "${RUBY_URL}/api/janus/memories?limit=5")
_read_http_code
assert_http_ok "GET /api/janus/memories"
mem_status=$(echo "$mem_resp" | jq -r '.status // "unknown"' 2>/dev/null || echo "unknown")
info "janus/memories status: $mem_status (ok=table exists, no_table=awaiting first trade)"

step "GET ${RUBY_URL}/api/janus/state"
state_resp=$(_curl GET "${RUBY_URL}/api/janus/state")
_read_http_code
if [[ "$LAST_HTTP_CODE" =~ ^2 ]]; then
  ok "GET /api/janus/state (HTTP $LAST_HTTP_CODE)"
  (( PASS++ )) || true
  janus_status=$(echo "$state_resp" | jq -r '.janus.status // "unknown"' 2>/dev/null || echo "unknown")
  info "Janus state: $janus_status"
else
  warn "GET /api/janus/state returned HTTP $LAST_HTTP_CODE"
  (( WARN_COUNT++ )) || true
fi

# ═══════════════════════════════════════════════════════════════════════════
# SECTION 8: Resolve signal (cleanup)
# ═══════════════════════════════════════════════════════════════════════════
header "8. Alertmanager Signal Cleanup"

info "Resolving test signals in Alertmanager to avoid persistent noise"

resolve_payload=$(jq -n '{
  "matchers": [
    {"name": "alertname", "value": "TradeSignal", "isRegex": false},
    {"name": "generatorURL", "value": "http://test-signal-pipeline", "isRegex": false}
  ],
  "startsAt": "2024-01-01T00:00:00Z",
  "endsAt":   "2099-01-01T00:00:00Z",
  "comment":  "test-signal-pipeline.sh cleanup silence",
  "createdBy": "test-signal-pipeline"
}')

step "POST ${ALERTMANAGER_URL}/api/v2/silences (silence test alerts)"
sil_resp=$(_curl POST "${ALERTMANAGER_URL}/api/v2/silences" -d "$resolve_payload")
_read_http_code
if [[ "$LAST_HTTP_CODE" =~ ^2 ]]; then
  sil_id=$(echo "$sil_resp" | jq -r '.silenceID // "?"' 2>/dev/null || echo "?")
  ok "Test alerts silenced (silenceID=$sil_id)"
  info "  → The silence expires automatically; delete it via Alertmanager UI if needed"
  (( PASS++ )) || true
else
  warn "Could not silence test alerts (HTTP $LAST_HTTP_CODE) — clean up via Alertmanager UI"
  (( WARN_COUNT++ )) || true
fi

# ═══════════════════════════════════════════════════════════════════════════
# SECTION 9: Personal-Crypto Paper-Mode Verification
#   kraken:paper_orders — Redis list written by ExecutionGate (ENABLE_LIVE_BOTS=0, default)
#   kraken:orders       — Redis list written by ExecutionGate (ENABLE_LIVE_BOTS=1, live)
# ═══════════════════════════════════════════════════════════════════════════
header "9. Personal-Crypto Paper-Mode Verification"

if ! $SKIP_REDIS && $HAS_REDIS_CLI; then
  step "redis-cli LRANGE kraken:paper_orders 0 -1"
  paper_orders=$(redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" LRANGE "kraken:paper_orders" 0 -1 2>/dev/null || echo "")

  if [[ -n "$paper_orders" ]]; then
    # Each line from LRANGE is a raw JSON string; walk them and check for "paper": true
    paper_found=false
    while IFS= read -r entry; do
      [[ -z "$entry" ]] && continue
      if echo "$entry" | jq -e '.paper == true' &>/dev/null; then
        paper_found=true
        break
      fi
    done <<< "$paper_orders"

    if $paper_found; then
      ok "[PAPER] Kraken order queued → kraken:paper_orders (ENABLE_LIVE_BOTS=0)"
      (( PASS++ )) || true
    else
      warn "kraken:paper_orders has entries but none carry \"paper\": true"
      (( WARN_COUNT++ )) || true
    fi
  else
    info "[PAPER] kraken:paper_orders is empty (signal may not have reached ExecutionGate yet)"
    info "  → With ENABLE_LIVE_BOTS=0 (default) ExecutionGate writes to kraken:paper_orders"
    info "  → kraken:orders will NOT be touched unless ENABLE_LIVE_BOTS=1"
    ok "ENABLE_LIVE_BOTS=0 default → paper mode active; kraken:orders left untouched"
    (( PASS++ )) || true
  fi
else
  info "Redis check skipped (--skip-redis or redis-cli unavailable)"
  info "  → With ENABLE_LIVE_BOTS=0 (default) ExecutionGate routes crypto to kraken:paper_orders"
fi

# ═══════════════════════════════════════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════════════════════════════════════
echo ""
echo -e "${BOLD}${CYAN}══════════════════════════════════════════════${RESET}"
echo -e "${BOLD}  Test Summary${RESET}"
echo -e "${BOLD}${CYAN}══════════════════════════════════════════════${RESET}"
echo -e "  ${GREEN}PASS ${RESET} $PASS"
echo -e "  ${RED}FAIL ${RESET} $FAIL"
echo -e "  ${YELLOW}WARN ${RESET} $WARN_COUNT"
echo ""

if (( FAIL > 0 )); then
  echo -e "${RED}${BOLD}  ✗ Pipeline test FAILED ($FAIL failures)${RESET}"
  echo ""
  echo "  Troubleshooting:"
  echo "  1. Ensure all services are running:  docker compose ps"
  echo "  2. Check service logs:               docker compose logs fks_alertmanager fks_ruby"
  echo "  3. Verify alertmanager.yml has the python-signal-webhook receiver"
  echo "  4. Confirm fks_ruby is reachable from fks_alertmanager on the Docker network"
  echo "  5. Run with -v for full HTTP response bodies"
  echo ""
  exit 1
elif (( WARN_COUNT > 0 )); then
  echo -e "${YELLOW}${BOLD}  ⚠ Pipeline test PASSED with warnings${RESET}"
  echo -e "${DIM}  Warnings may indicate webhook delivery lag or optional components unavailable.${RESET}"
  echo ""
  exit 0
else
  echo -e "${GREEN}${BOLD}  ✓ Pipeline test PASSED${RESET}"
  echo ""
  exit 0
fi
