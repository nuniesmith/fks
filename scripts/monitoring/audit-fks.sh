#!/bin/bash
set -euo pipefail

# FKS Codebase Audit Script
# Convenient wrapper for common audit operations

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# API endpoint
AUDIT_API="http://localhost:8080"

info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

success() {
    echo -e "${GREEN}[✓]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[⚠]${NC} $1"
}

error() {
    echo -e "${RED}[✗]${NC} $1"
    exit 1
}

section() {
    echo ""
    echo -e "${CYAN}═══════════════════════════════════════════════${NC}"
    echo -e "${CYAN}  $1${NC}"
    echo -e "${CYAN}═══════════════════════════════════════════════${NC}"
    echo ""
}

# Ensure service is running
ensure_service() {
    info "Checking if audit service is running..."

    if ! docker compose ps audit | grep -q "Up\|running"; then
        info "Starting audit service..."
        docker compose up -d audit

        # Wait for health check
        info "Waiting for service to be ready..."
        local max_wait=60
        local waited=0
        while [ $waited -lt $max_wait ]; do
            if curl -sf "$AUDIT_API/health" > /dev/null 2>&1; then
                success "Audit service is ready!"
                return 0
            fi
            sleep 2
            waited=$((waited + 2))
        done
        error "Audit service failed to start within ${max_wait}s"
    else
        success "Audit service is running"
    fi
}

# Create reports directory
ensure_reports_dir() {
    mkdir -p docs/audit/tasks
    success "Reports directory ready: docs/audit/"
}

# Scan for audit tags
scan_tags() {
    local path=${1:-/app/src}
    section "Scanning for Audit Tags"

    info "Scanning: $path"
    local output="docs/audit/tags-$(date +%Y%m%d-%H%M%S).json"

    if curl -sf -X POST "$AUDIT_API/api/scan/tags" \
        -H "Content-Type: application/json" \
        -d "{\"path\": \"$path\"}" \
        -o "$output"; then
        success "Tag scan complete: $output"

        # Show summary
        if command -v jq &> /dev/null; then
            echo ""
            info "Summary:"
            jq -r '.tags | group_by(.type) | map({type: .[0].type, count: length}) | .[] | "  \(.type): \(.count)"' "$output"
        fi
        return 0
    else
        error "Tag scan failed"
    fi
}

# Static analysis
static_analysis() {
    local path=${1:-/app/src}
    local focus=${2:-security}

    section "Static Analysis"

    info "Analyzing: $path"
    info "Focus: $focus"
    local output="docs/audit/static-$focus-$(date +%Y%m%d-%H%M%S).json"

    if curl -sf -X POST "$AUDIT_API/api/scan/static" \
        -H "Content-Type: application/json" \
        -d "{\"path\": \"$path\", \"focus\": [\"$focus\"]}" \
        -o "$output"; then
        success "Static analysis complete: $output"

        # Show summary
        if command -v jq &> /dev/null; then
            echo ""
            info "Issues found:"
            jq -r '.issues | group_by(.severity) | map({severity: .[0].severity, count: length}) | .[] | "  \(.severity): \(.count)"' "$output" 2>/dev/null || echo "  No issues found"
        fi
        return 0
    else
        error "Static analysis failed"
    fi
}

# Full audit with LLM
full_audit() {
    local path=${1:-/app/src/janus}
    local enable_llm=${2:-true}

    section "Full Audit"

    info "Auditing: $path"
    info "LLM enabled: $enable_llm"
    local output="docs/audit/audit-$(basename $path)-$(date +%Y%m%d-%H%M%S).json"

    if curl -sf -X POST "$AUDIT_API/api/audit" \
        -H "Content-Type: application/json" \
        -d "{\"path\": \"$path\", \"enable_llm\": $enable_llm, \"include_tests\": false}" \
        -o "$output"; then
        success "Audit complete: $output"

        # Show summary
        if command -v jq &> /dev/null; then
            echo ""
            info "Summary:"
            jq -r '.summary | to_entries | .[] | "  \(.key): \(.value)"' "$output" 2>/dev/null || echo "  Check JSON file for details"
        fi
        return 0
    else
        error "Audit failed"
    fi
}

# Security-focused scan
security_scan() {
    section "Security Scan"

    info "Scanning all source code for security issues..."
    local output="docs/audit/security-$(date +%Y%m%d-%H%M%S).json"

    if curl -sf -X POST "$AUDIT_API/api/scan/static" \
        -H "Content-Type: application/json" \
        -d '{"path": "/app/src", "focus": ["security"], "include_tests": false}' \
        -o "$output"; then
        success "Security scan complete: $output"

        # Highlight critical issues
        if command -v jq &> /dev/null; then
            local critical=$(jq '[.issues[] | select(.severity=="Critical")] | length' "$output" 2>/dev/null || echo 0)
            local high=$(jq '[.issues[] | select(.severity=="High")] | length' "$output" 2>/dev/null || echo 0)

            echo ""
            if [ "$critical" -gt 0 ]; then
                warn "Critical issues: $critical"
            fi
            if [ "$high" -gt 0 ]; then
                warn "High severity issues: $high"
            fi
            if [ "$critical" -eq 0 ] && [ "$high" -eq 0 ]; then
                success "No critical or high severity issues found!"
            fi
        fi
        return 0
    else
        error "Security scan failed"
    fi
}

# Audit specific service
audit_service() {
    local service=$1

    section "Service Audit: $service"

    local service_path="/app/src/janus/services/$service"
    info "Auditing service: $service"
    local output="docs/audit/service-$service-$(date +%Y%m%d-%H%M%S).json"

    if curl -sf -X POST "$AUDIT_API/api/audit" \
        -H "Content-Type: application/json" \
        -d "{\"path\": \"$service_path\", \"enable_llm\": true, \"focus\": [\"security\", \"performance\"], \"include_tests\": false}" \
        -o "$output"; then
        success "Service audit complete: $output"
        return 0
    else
        error "Service audit failed"
    fi
}

# Complete codebase audit
complete_audit() {
    section "Complete FKS Codebase Audit"

    ensure_service
    ensure_reports_dir

    # 1. Tag scan
    info "Step 1/4: Scanning for audit tags..."
    scan_tags "/app/src"

    # 2. Security scan
    info "Step 2/4: Security analysis..."
    security_scan

    # 3. Audit each service
    info "Step 3/4: Per-service audits..."
    for service in forward gateway backward; do
        if [ -d "src/janus/services/$service" ]; then
            audit_service "$service"
        fi
    done

    # 4. Monitor audit
    info "Step 4/4: Monitor service audit..."
    if [ -d "src/monitor" ]; then
        full_audit "/app/src/monitor" "true"
    fi

    section "Audit Complete!"
    success "All reports saved to docs/audit/"
    info "View reports:"
    echo "  ls -lh docs/audit/"
    echo "  cat docs/audit/tags-*.json | jq ."
}

# Show usage
usage() {
    cat << EOF

FKS Codebase Audit Script

Usage: $0 <command> [options]

Commands:
  all               Run complete audit (tags, security, services)
  tags [path]       Scan for audit tags (default: /app/src)
  static [path]     Run static analysis (default: /app/src)
  security          Security-focused scan of all code
  service <name>    Audit specific service (forward, gateway, backward)
  full [path]       Full audit with LLM (default: /app/src/janus)
  health            Check audit service health
  start             Start audit service
  logs              Show audit service logs
  reports           List all audit reports
  help              Show this help message

Examples:
  $0 all                    # Complete audit
  $0 tags                   # Scan all tags
  $0 static /app/src/janus  # Static analysis of Janus
  $0 security               # Security scan
  $0 service forward        # Audit Forward service
  $0 full /app/src/monitor  # Full audit of Monitor

Environment Variables:
  AUDIT_API         Audit service URL (default: http://localhost:8080)

EOF
}

# Main command dispatcher
main() {
    local command=${1:-help}

    case $command in
        all|complete)
            ensure_service
            ensure_reports_dir
            complete_audit
            ;;

        tags)
            ensure_service
            ensure_reports_dir
            scan_tags "${2:-/app/src}"
            ;;

        static|analyze)
            ensure_service
            ensure_reports_dir
            static_analysis "${2:-/app/src}" "${3:-security}"
            ;;

        security|sec)
            ensure_service
            ensure_reports_dir
            security_scan
            ;;

        service|svc)
            if [ -z "${2:-}" ]; then
                error "Service name required. Use: forward, gateway, or backward"
            fi
            ensure_service
            ensure_reports_dir
            audit_service "$2"
            ;;

        full|audit)
            ensure_service
            ensure_reports_dir
            full_audit "${2:-/app/src/janus}" "${3:-true}"
            ;;

        health|status)
            if curl -sf "$AUDIT_API/health" | jq .; then
                success "Audit service is healthy"
            else
                error "Audit service is not responding"
            fi
            ;;

        start|up)
            ensure_service
            ;;

        logs)
            docker compose logs -f audit
            ;;

        reports|list)
            echo ""
            info "Audit Reports:"
            ls -lh docs/audit/ 2>/dev/null || echo "  No reports found"
            echo ""
            ;;

        help|--help|-h)
            usage
            ;;

        *)
            error "Unknown command: $command"
            usage
            exit 1
            ;;
    esac
}

# Print banner
echo ""
echo "╔═══════════════════════════════════════════════╗"
echo "║         FKS Codebase Audit Tool               ║"
echo "║         Automated Code Analysis               ║"
echo "╚═══════════════════════════════════════════════╝"
echo ""

main "$@"
