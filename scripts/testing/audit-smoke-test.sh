#!/usr/bin/env bash
# ==============================================================================
# FKS Audit Service Smoke Test
# ==============================================================================
# Validates the audit service's health, static analysis endpoints, and runtime
# inspection endpoints (JANUS/CNS integration).
#
# Usage:
#   ./scripts/testing/audit-smoke-test.sh                # defaults to localhost:8082
#   ./scripts/testing/audit-smoke-test.sh localhost:8080  # custom host:port
#   AUDIT_URL=http://audit:8080 ./scripts/testing/audit-smoke-test.sh
#
# Exit codes:
#   0 - All tests passed
#   1 - One or more tests failed
# ==============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
AUDIT_HOST="${1:-${AUDIT_HOST:-localhost:8082}}"
AUDIT_URL="${AUDIT_URL:-http://${AUDIT_HOST}}"
TIMEOUT="${SMOKE_TEST_TIMEOUT:-10}"
VERBOSE="${VERBOSE:-false}"

# Test counters
PASSED=0
FAILED=0
SKIPPED=0
TOTAL=0

# Runtime mode detection (set after health check)
RUNTIME_ENABLED=false

# Colors (disabled if not a terminal)
if [ -t 1 ]; then
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[1;33m'
    BLUE='\033[0;34m'
    CYAN='\033[0;36m'
    BOLD='\033[1m'
    DIM='\033[2m'
    NC='\033[0m'
else
    RED='' GREEN='' YELLOW='' BLUE='' CYAN='' BOLD='' DIM='' NC=''
fi

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

log_header() {
    echo ""
    echo -e "${BOLD}${BLUE}══════════════════════════════════════════════════${NC}"
    echo -e "${BOLD}${BLUE}  $1${NC}"
    echo -e "${BOLD}${BLUE}══════════════════════════════════════════════════${NC}"
}

log_section() {
    echo ""
    echo -e "${CYAN}── $1 ──${NC}"
}

log_pass() {
    PASSED=$((PASSED + 1))
    TOTAL=$((TOTAL + 1))
    echo -e "  ${GREEN}✓${NC} $1"
}

log_fail() {
    FAILED=$((FAILED + 1))
    TOTAL=$((TOTAL + 1))
    echo -e "  ${RED}✗${NC} $1"
    if [ -n "${2:-}" ]; then
        echo -e "    ${DIM}${2}${NC}"
    fi
}

log_skip() {
    SKIPPED=$((SKIPPED + 1))
    TOTAL=$((TOTAL + 1))
    echo -e "  ${YELLOW}⊘${NC} $1 ${DIM}(skipped)${NC}"
}

log_info() {
    echo -e "  ${DIM}ℹ $1${NC}"
}

# Make an HTTP request and capture status code + body
# Usage: http_get <path> [expected_status]
# Sets: HTTP_STATUS, HTTP_BODY
http_get() {
    local path="$1"
    local url="${AUDIT_URL}${path}"

    if [ "$VERBOSE" = "true" ]; then
        echo -e "    ${DIM}GET ${url}${NC}"
    fi

    local tmpfile
    tmpfile=$(mktemp)

    HTTP_STATUS=$(curl -s -o "$tmpfile" -w "%{http_code}" \
        --connect-timeout "$TIMEOUT" \
        --max-time "$TIMEOUT" \
        "$url" 2>/dev/null) || HTTP_STATUS="000"

    HTTP_BODY=$(cat "$tmpfile" 2>/dev/null || echo "")
    rm -f "$tmpfile"
}

# Make an HTTP POST request with JSON body
# Usage: http_post <path> <json_body>
# Sets: HTTP_STATUS, HTTP_BODY
http_post() {
    local path="$1"
    local body="$2"
    local url="${AUDIT_URL}${path}"

    if [ "$VERBOSE" = "true" ]; then
        echo -e "    ${DIM}POST ${url}${NC}"
    fi

    local tmpfile
    tmpfile=$(mktemp)

    HTTP_STATUS=$(curl -s -o "$tmpfile" -w "%{http_code}" \
        --connect-timeout "$TIMEOUT" \
        --max-time "$TIMEOUT" \
        -H "Content-Type: application/json" \
        -d "$body" \
        "$url" 2>/dev/null) || HTTP_STATUS="000"

    HTTP_BODY=$(cat "$tmpfile" 2>/dev/null || echo "")
    rm -f "$tmpfile"
}

# Check if a JSON field exists and optionally matches a value
# Usage: json_field <json> <field> [expected_value]
json_field() {
    local json="$1"
    local field="$2"
    local expected="${3:-}"

    local value
    value=$(echo "$json" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    keys = '$field'.split('.')
    v = data
    for k in keys:
        if isinstance(v, dict):
            v = v[k]
        else:
            print('__MISSING__')
            sys.exit(0)
    print(v)
except (json.JSONDecodeError, KeyError, TypeError, IndexError):
    print('__MISSING__')
" 2>/dev/null)

    if [ "$value" = "__MISSING__" ]; then
        return 1
    fi

    if [ -n "$expected" ]; then
        if [ "$value" = "$expected" ]; then
            return 0
        else
            return 1
        fi
    fi

    echo "$value"
    return 0
}

# Assert HTTP status code
# Usage: assert_status <test_name> <expected_status>
assert_status() {
    local test_name="$1"
    local expected="$2"

    if [ "$HTTP_STATUS" = "$expected" ]; then
        log_pass "$test_name (HTTP $HTTP_STATUS)"
    else
        log_fail "$test_name" "Expected HTTP $expected, got HTTP $HTTP_STATUS"
    fi
}

# Assert JSON field exists
# Usage: assert_json_field <test_name> <field> [expected_value]
assert_json_field() {
    local test_name="$1"
    local field="$2"
    local expected="${3:-}"

    if [ -n "$expected" ]; then
        if json_field "$HTTP_BODY" "$field" "$expected" > /dev/null 2>&1; then
            log_pass "$test_name ($field=$expected)"
        else
            local actual
            actual=$(json_field "$HTTP_BODY" "$field" 2>/dev/null || echo "<missing>")
            log_fail "$test_name" "Expected $field=$expected, got $field=$actual"
        fi
    else
        if json_field "$HTTP_BODY" "$field" > /dev/null 2>&1; then
            log_pass "$test_name ($field present)"
        else
            log_fail "$test_name" "Field '$field' missing from response"
        fi
    fi
}

# ---------------------------------------------------------------------------
# Pre-flight check
# ---------------------------------------------------------------------------

log_header "FKS Audit Service Smoke Test"

echo -e "  ${DIM}Target:  ${AUDIT_URL}${NC}"
echo -e "  ${DIM}Timeout: ${TIMEOUT}s per request${NC}"
echo -e "  ${DIM}Date:    $(date -u '+%Y-%m-%dT%H:%M:%SZ')${NC}"

# Check that curl is available
if ! command -v curl &> /dev/null; then
    echo -e "${RED}Error: curl is required but not installed${NC}"
    exit 1
fi

# Check that python3 is available (for JSON parsing)
if ! command -v python3 &> /dev/null; then
    echo -e "${YELLOW}Warning: python3 not available — JSON field assertions will be skipped${NC}"
fi

# ---------------------------------------------------------------------------
# 1. Health Check
# ---------------------------------------------------------------------------

log_section "1. Health Check"

http_get "/health"

if [ "$HTTP_STATUS" = "000" ]; then
    echo -e "${RED}Error: Cannot reach audit service at ${AUDIT_URL}${NC}"
    echo -e "${DIM}Is the service running? Try: cargo run --bin audit-server${NC}"
    exit 1
fi

assert_status "GET /health returns 200" "200"
assert_json_field "Health reports status" "status" "healthy"
assert_json_field "Health includes version" "version"
assert_json_field "Health includes runtime_inspection section" "runtime_inspection"
assert_json_field "Health includes runtime_inspection.enabled" "runtime_inspection.enabled"
assert_json_field "Health includes runtime_inspection.status" "runtime_inspection.status"

# Detect runtime mode
RUNTIME_STATUS=$(json_field "$HTTP_BODY" "runtime_inspection.enabled" 2>/dev/null || echo "")
if [ "$RUNTIME_STATUS" = "True" ] || [ "$RUNTIME_STATUS" = "true" ]; then
    RUNTIME_ENABLED=true
    log_info "Runtime inspection: ENABLED"
else
    RUNTIME_ENABLED=false
    log_info "Runtime inspection: DISABLED (runtime endpoint tests will verify 503 behavior)"
fi

# ---------------------------------------------------------------------------
# 2. Static Analysis Endpoints
# ---------------------------------------------------------------------------

log_section "2. Static Analysis Endpoints"

# POST /api/scan/tags — scan a path for audit tags
http_post "/api/scan/tags" '{"path": "/app"}'
if [ "$HTTP_STATUS" = "200" ]; then
    log_pass "POST /api/scan/tags accepts requests (HTTP $HTTP_STATUS)"
elif [ "$HTTP_STATUS" = "400" ] || [ "$HTTP_STATUS" = "404" ] || [ "$HTTP_STATUS" = "500" ]; then
    # Acceptable: the path might not exist in the container, but the endpoint is reachable
    log_pass "POST /api/scan/tags endpoint reachable (HTTP $HTTP_STATUS — path may not exist)"
else
    log_fail "POST /api/scan/tags" "Unexpected HTTP $HTTP_STATUS"
fi

# POST /api/scan/static — static analysis on a path
http_post "/api/scan/static" '{"path": "/app"}'
if [ "$HTTP_STATUS" = "200" ]; then
    log_pass "POST /api/scan/static accepts requests (HTTP $HTTP_STATUS)"
elif [ "$HTTP_STATUS" = "400" ] || [ "$HTTP_STATUS" = "404" ] || [ "$HTTP_STATUS" = "500" ]; then
    log_pass "POST /api/scan/static endpoint reachable (HTTP $HTTP_STATUS — path may not exist)"
else
    log_fail "POST /api/scan/static" "Unexpected HTTP $HTTP_STATUS"
fi

# GET /api/audit/:id — non-existent ID should return 404 or error, not 500
http_get "/api/audit/nonexistent-test-id"
if [ "$HTTP_STATUS" = "404" ] || [ "$HTTP_STATUS" = "400" ]; then
    log_pass "GET /api/audit/:id returns appropriate error for missing ID (HTTP $HTTP_STATUS)"
elif [ "$HTTP_STATUS" = "500" ]; then
    log_fail "GET /api/audit/:id returns 500 for missing ID" "Should return 404 or 400"
else
    log_pass "GET /api/audit/:id endpoint reachable (HTTP $HTTP_STATUS)"
fi

# ---------------------------------------------------------------------------
# 3. Runtime Inspection Endpoints
# ---------------------------------------------------------------------------

log_section "3. Runtime Inspection Endpoints"

# Define all runtime endpoints to test
RUNTIME_ENDPOINTS=(
    "/api/runtime/snapshot"
    "/api/runtime/connectivity"
    "/api/runtime/connections"
    "/api/runtime/cns/health"
    "/api/runtime/cns/brain"
    "/api/runtime/cns/brain/regions"
    "/api/runtime/cns/metrics"
    "/api/runtime/janus/summary"
    "/api/runtime/janus/services"
)

if [ "$RUNTIME_ENABLED" = "true" ]; then
    # Runtime is enabled — endpoints should return 200 or 502 (if upstream is down)
    for endpoint in "${RUNTIME_ENDPOINTS[@]}"; do
        http_get "$endpoint"
        if [ "$HTTP_STATUS" = "200" ]; then
            log_pass "GET $endpoint returns data (HTTP 200)"
        elif [ "$HTTP_STATUS" = "502" ]; then
            log_pass "GET $endpoint reachable, upstream down (HTTP 502)"
        elif [ "$HTTP_STATUS" = "500" ]; then
            log_pass "GET $endpoint reachable, internal error (HTTP 500)"
            log_info "This may indicate JANUS/CNS services are not yet healthy"
        else
            log_fail "GET $endpoint" "Unexpected HTTP $HTTP_STATUS"
        fi
    done

    # Test parameterized endpoints
    for service in "forward" "backward" "cns"; do
        http_get "/api/runtime/janus/service/$service"
        if [ "$HTTP_STATUS" = "200" ] || [ "$HTTP_STATUS" = "404" ] || [ "$HTTP_STATUS" = "502" ]; then
            log_pass "GET /api/runtime/janus/service/$service (HTTP $HTTP_STATUS)"
        else
            log_fail "GET /api/runtime/janus/service/$service" "Unexpected HTTP $HTTP_STATUS"
        fi
    done

    for service in "forward" "backward"; do
        http_get "/api/runtime/janus/inspect/$service"
        if [ "$HTTP_STATUS" = "200" ] || [ "$HTTP_STATUS" = "404" ] || [ "$HTTP_STATUS" = "502" ]; then
            log_pass "GET /api/runtime/janus/inspect/$service (HTTP $HTTP_STATUS)"
        else
            log_fail "GET /api/runtime/janus/inspect/$service" "Unexpected HTTP $HTTP_STATUS"
        fi
    done

    # Validate snapshot response structure (if we got 200)
    http_get "/api/runtime/snapshot"
    if [ "$HTTP_STATUS" = "200" ]; then
        log_section "3a. Snapshot Response Validation"
        assert_json_field "Snapshot has timestamp" "timestamp"
        assert_json_field "Snapshot has overall_status" "overall_status"
        assert_json_field "Snapshot has janus section" "janus"
        assert_json_field "Snapshot has alerts section" "alerts"
    fi

    # Validate connectivity response structure (if we got 200)
    http_get "/api/runtime/connectivity"
    if [ "$HTTP_STATUS" = "200" ]; then
        log_section "3b. Connectivity Response Validation"
        assert_json_field "Connectivity has cns_reachable" "cns_reachable"
        assert_json_field "Connectivity has janus_reachable" "janus_reachable"
        assert_json_field "Connectivity has total_latency_ms" "total_latency_ms"
    fi

    # Validate connections summary structure (if we got 200)
    http_get "/api/runtime/connections"
    if [ "$HTTP_STATUS" = "200" ]; then
        log_section "3c. Connections Summary Validation"
        assert_json_field "Connections has enabled" "enabled"
        assert_json_field "Connections has total_count" "total_count"
        assert_json_field "Connections has connected_count" "connected_count"
        assert_json_field "Connections has services" "services"
    fi

else
    # Runtime is disabled — all endpoints should return 503
    for endpoint in "${RUNTIME_ENDPOINTS[@]}"; do
        http_get "$endpoint"
        if [ "$HTTP_STATUS" = "503" ]; then
            log_pass "GET $endpoint correctly returns 503 (runtime disabled)"
        elif [ "$HTTP_STATUS" = "200" ]; then
            log_fail "GET $endpoint" "Returned 200 but runtime should be disabled"
        else
            log_fail "GET $endpoint" "Expected 503 (runtime disabled), got HTTP $HTTP_STATUS"
        fi
    done

    # Parameterized endpoints should also return 503
    http_get "/api/runtime/janus/service/forward"
    if [ "$HTTP_STATUS" = "503" ]; then
        log_pass "GET /api/runtime/janus/service/:name correctly returns 503"
    else
        log_fail "GET /api/runtime/janus/service/:name" "Expected 503, got HTTP $HTTP_STATUS"
    fi

    http_get "/api/runtime/janus/inspect/forward"
    if [ "$HTTP_STATUS" = "503" ]; then
        log_pass "GET /api/runtime/janus/inspect/:name correctly returns 503"
    else
        log_fail "GET /api/runtime/janus/inspect/:name" "Expected 503, got HTTP $HTTP_STATUS"
    fi
fi

# ---------------------------------------------------------------------------
# 4. Research & Visualization Endpoints
# ---------------------------------------------------------------------------

log_section "4. Research & Visualization Endpoints"

# POST /api/research/analyze — should accept or return meaningful error
http_post "/api/research/analyze" '{"content": "fn main() { println!(\"hello\"); }", "title": "smoke-test"}'
if [ "$HTTP_STATUS" = "200" ]; then
    log_pass "POST /api/research/analyze returns results (HTTP 200)"
elif [ "$HTTP_STATUS" = "400" ] || [ "$HTTP_STATUS" = "422" ] || [ "$HTTP_STATUS" = "500" ]; then
    log_pass "POST /api/research/analyze endpoint reachable (HTTP $HTTP_STATUS)"
else
    log_fail "POST /api/research/analyze" "Unexpected HTTP $HTTP_STATUS"
fi

# POST /api/visualize/neuromorphic
http_post "/api/visualize/neuromorphic" '{"path": "/app"}'
if [ "$HTTP_STATUS" = "200" ]; then
    log_pass "POST /api/visualize/neuromorphic returns results (HTTP 200)"
elif [ "$HTTP_STATUS" = "400" ] || [ "$HTTP_STATUS" = "404" ] || [ "$HTTP_STATUS" = "500" ]; then
    log_pass "POST /api/visualize/neuromorphic endpoint reachable (HTTP $HTTP_STATUS)"
else
    log_fail "POST /api/visualize/neuromorphic" "Unexpected HTTP $HTTP_STATUS"
fi

# ---------------------------------------------------------------------------
# 5. Security Checks
# ---------------------------------------------------------------------------

log_section "5. Security Checks"

# Verify CORS headers are present (should not be wildcard)
CORS_HEADERS=$(curl -s -I -X OPTIONS \
    --connect-timeout "$TIMEOUT" \
    --max-time "$TIMEOUT" \
    -H "Origin: http://evil-site.example.com" \
    -H "Access-Control-Request-Method: GET" \
    "${AUDIT_URL}/health" 2>/dev/null || echo "")

if echo "$CORS_HEADERS" | grep -qi "access-control-allow-origin: \*"; then
    log_fail "CORS not wildcard" "Access-Control-Allow-Origin is set to * (permissive)"
elif echo "$CORS_HEADERS" | grep -qi "access-control-allow-origin: http://evil-site.example.com"; then
    log_fail "CORS blocks unknown origins" "Allowed unknown origin http://evil-site.example.com"
else
    log_pass "CORS does not allow arbitrary origins"
fi

# Verify non-existent routes return 404, not 500
http_get "/api/nonexistent-endpoint-12345"
if [ "$HTTP_STATUS" = "404" ] || [ "$HTTP_STATUS" = "405" ]; then
    log_pass "Unknown routes return $HTTP_STATUS (not 500)"
elif [ "$HTTP_STATUS" = "500" ]; then
    log_fail "Unknown routes return 500" "Should return 404 or 405"
else
    log_pass "Unknown routes handled (HTTP $HTTP_STATUS)"
fi

# ---------------------------------------------------------------------------
# 6. Response Time Check
# ---------------------------------------------------------------------------

log_section "6. Response Time Check"

HEALTH_TIME=$(curl -s -o /dev/null -w "%{time_total}" \
    --connect-timeout "$TIMEOUT" \
    --max-time "$TIMEOUT" \
    "${AUDIT_URL}/health" 2>/dev/null || echo "0")

# Convert to milliseconds (bash doesn't do float comparison easily)
HEALTH_TIME_MS=$(echo "$HEALTH_TIME" | python3 -c "
import sys
try:
    t = float(sys.stdin.read().strip())
    print(int(t * 1000))
except:
    print(0)
" 2>/dev/null || echo "0")

if [ "$HEALTH_TIME_MS" -lt 500 ]; then
    log_pass "Health check response time: ${HEALTH_TIME_MS}ms (< 500ms)"
elif [ "$HEALTH_TIME_MS" -lt 2000 ]; then
    log_pass "Health check response time: ${HEALTH_TIME_MS}ms (< 2s, acceptable)"
    log_info "Consider investigating if consistently > 500ms"
else
    log_fail "Health check response time: ${HEALTH_TIME_MS}ms" "Expected < 2000ms"
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

log_header "Test Results"

echo -e "  ${GREEN}Passed:${NC}  $PASSED"
echo -e "  ${RED}Failed:${NC}  $FAILED"
echo -e "  ${YELLOW}Skipped:${NC} $SKIPPED"
echo -e "  ${BOLD}Total:${NC}   $TOTAL"
echo ""

if [ "$RUNTIME_ENABLED" = "true" ]; then
    echo -e "  ${DIM}Mode: Runtime inspection ENABLED${NC}"
else
    echo -e "  ${DIM}Mode: Static-only (runtime disabled)${NC}"
    echo -e "  ${DIM}To test with runtime: AUDIT_RUNTIME_ENABLED=true docker compose up audit${NC}"
fi

echo ""

if [ "$FAILED" -eq 0 ]; then
    echo -e "  ${GREEN}${BOLD}All tests passed!${NC} 🎉"
    echo ""
    exit 0
else
    echo -e "  ${RED}${BOLD}${FAILED} test(s) failed.${NC}"
    echo ""
    exit 1
fi
