#!/bin/bash
# ============================================================================
# FKS Trading System - Integration Test Startup Script
# ============================================================================
# This script builds and starts the FKS trading system with Forward → Execution
# integration enabled for testing.
#
# Usage:
#   ./start-integration-test.sh [mode]
#
# Modes:
#   simulated  - Simulated trading (default)
#   paper      - Paper trading with Bybit testnet
#   live       - Live trading (use with extreme caution!)
#
# Prerequisites:
#   - Docker and Docker Compose installed
#   - .env file configured (optional, will use defaults)
#   - Sufficient disk space (10GB+ recommended)
#
# ============================================================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Default configuration
MODE="${1:-simulated}"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ============================================================================
# Helper Functions
# ============================================================================

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_section() {
    echo ""
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${CYAN}  $1${NC}"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

check_prerequisites() {
    log_section "Checking Prerequisites"

    # Check Docker
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed. Please install Docker first."
        exit 1
    fi
    log_success "Docker found: $(docker --version)"

    # Check Docker Compose
    if ! command -v docker compose &> /dev/null && ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose is not installed. Please install Docker Compose first."
        exit 1
    fi
    log_success "Docker Compose found"

    # Check disk space
    AVAILABLE_SPACE=$(df -BG "$PROJECT_DIR" | awk 'NR==2 {print $4}' | sed 's/G//')
    if [ "$AVAILABLE_SPACE" -lt 10 ]; then
        log_warning "Low disk space: ${AVAILABLE_SPACE}GB available (10GB+ recommended)"
        read -p "Continue anyway? (y/n) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    else
        log_success "Disk space OK: ${AVAILABLE_SPACE}GB available"
    fi

    # Check .env file
    if [ -f "$PROJECT_DIR/.env" ]; then
        log_success ".env file found"
    else
        log_warning ".env file not found, using defaults"
    fi
}

validate_mode() {
    log_section "Validating Trading Mode"

    case "$MODE" in
        simulated)
            log_info "Mode: SIMULATED - No real trading, everything simulated"
            export EXECUTION_MODE=simulated
            export ENABLE_EXECUTION=true
            ;;
        paper)
            log_info "Mode: PAPER - Bybit testnet trading"
            export EXECUTION_MODE=paper
            export ENABLE_EXECUTION=true

            # Check for Bybit credentials
            if [ -z "$BYBIT_API_KEY" ] || [ -z "$BYBIT_API_SECRET" ]; then
                log_error "BYBIT_API_KEY and BYBIT_API_SECRET must be set for paper trading"
                log_info "Get testnet API keys from: https://testnet.bybit.com/app/user/api-management"
                exit 1
            fi
            log_success "Bybit testnet credentials found"
            ;;
        live)
            log_warning "Mode: LIVE TRADING - REAL MONEY AT RISK!"
            echo ""
            log_error "┌────────────────────────────────────────────────────────┐"
            log_error "│  WARNING: YOU ARE ABOUT TO START LIVE TRADING!        │"
            log_error "│  REAL MONEY WILL BE USED. LOSSES CAN OCCUR.           │"
            log_error "└────────────────────────────────────────────────────────┘"
            echo ""
            read -p "Type 'I UNDERSTAND THE RISKS' to continue: " CONFIRMATION
            if [ "$CONFIRMATION" != "I UNDERSTAND THE RISKS" ]; then
                log_info "Live trading cancelled"
                exit 1
            fi
            export EXECUTION_MODE=live
            export ENABLE_EXECUTION=true
            ;;
        *)
            log_error "Invalid mode: $MODE"
            log_info "Valid modes: simulated, paper, live"
            exit 1
            ;;
    esac
}

stop_existing_services() {
    log_section "Stopping Existing Services"

    cd "$PROJECT_DIR"

    if docker compose ps | grep -q "Up"; then
        log_info "Stopping running services..."
        docker compose down
        log_success "Services stopped"
    else
        log_info "No running services found"
    fi
}

build_services() {
    log_section "Building Services"

    cd "$PROJECT_DIR"

    log_info "Building forward service..."
    docker compose build forward
    log_success "Forward service built"

    log_info "Building execution service..."
    docker compose build execution
    log_success "Execution service built"

    log_info "Building data service..."
    docker compose build data
    log_success "Data service built"
}

start_infrastructure() {
    log_section "Starting Infrastructure Services"

    cd "$PROJECT_DIR"

    log_info "Starting Redis, QuestDB, PostgreSQL..."
    docker compose up -d redis questdb postgres

    log_info "Waiting for infrastructure to be healthy (30s)..."
    sleep 30

    # Check health
    if docker compose ps redis questdb postgres | grep -q "unhealthy"; then
        log_error "Some infrastructure services are unhealthy"
        docker compose ps redis questdb postgres
        exit 1
    fi

    log_success "Infrastructure services are healthy"
}

start_execution_service() {
    log_section "Starting Execution Service"

    cd "$PROJECT_DIR"

    # Execution is embedded inside Janus (ENABLE_EXECUTION=true, localhost:50052 internal).
    # No separate execution container to start — it runs as part of fks_janus.
    log_info "Execution is embedded inside Janus — verifying via Janus container..."

    if docker ps -q -f name=fks_janus 2>/dev/null | grep -q .; then
        EXEC_ENABLED=$(docker exec fks_janus printenv ENABLE_EXECUTION 2>/dev/null || echo "")
        if [ "$EXEC_ENABLED" = "true" ]; then
            log_success "Execution enabled inside Janus (ENABLE_EXECUTION=true)"
        else
            log_warning "Execution may not be enabled in Janus (ENABLE_EXECUTION=${EXEC_ENABLED:-unset})"
        fi
    else
        log_error "Janus container not running — execution is unavailable"
        log_info "Checking logs..."
        docker compose logs --tail=50 janus
        exit 1
    fi
}

start_forward_service() {
    log_section "Starting Forward Service"

    cd "$PROJECT_DIR"

    log_info "Starting forward service..."
    docker compose up -d forward

    log_info "Waiting for forward service to be ready (30s)..."
    sleep 30

    # Check logs for execution client connection (execution is embedded in janus)
    if docker compose logs forward | grep -q "Execution client connected"; then
        log_success "Forward service connected to execution (via Janus)"
    else
        log_warning "Forward service may not be connected to execution (embedded in Janus)"
        log_info "Check logs: docker compose logs forward"
    fi
}

start_data_service() {
    log_section "Starting Data Service"

    cd "$PROJECT_DIR"

    log_info "Starting data service (market data ingestion)..."
    docker compose up -d data

    log_info "Waiting for data service to start (15s)..."
    sleep 15

    log_success "Data service started"
}

start_monitoring() {
    log_section "Starting Monitoring Stack"

    cd "$PROJECT_DIR"

    log_info "Starting Prometheus, Grafana..."
    docker compose up -d prometheus grafana

    log_info "Waiting for monitoring to be ready (15s)..."
    sleep 15

    log_success "Monitoring stack started"
}

display_status() {
    log_section "Service Status"

    cd "$PROJECT_DIR"
    docker compose ps
}

display_endpoints() {
    log_section "Service Endpoints"

    echo ""
    echo -e "${GREEN}Core Services:${NC}"
    echo -e "  Janus (REST):                http://localhost:7000"
    echo -e "  Janus (Health):              http://localhost:8080/health"
    echo -e "  Execution (embedded in Janus, internal gRPC): localhost:50052"
    echo ""
    echo -e "${GREEN}Data & Storage:${NC}"
    echo -e "  QuestDB (Console):           http://localhost:9000"
    echo -e "  Redis:                       localhost:6379"
    echo ""
    echo -e "${GREEN}Monitoring:${NC}"
    echo -e "  Grafana:                     http://localhost:3000 (admin/admin)"
    echo -e "  Prometheus:                  http://localhost:9090"
    echo ""
}

display_next_steps() {
    log_section "Next Steps"

    echo ""
    echo -e "${CYAN}1. Monitor Logs:${NC}"
    echo -e "   docker compose logs -f janus"
    echo ""
    echo -e "${CYAN}2. Check Health:${NC}"
    echo -e "   curl http://localhost:8080/api/v1/health"
    echo -e "   curl http://localhost:7000/health"
    echo ""
    echo -e "${CYAN}3. Generate Test Signal:${NC}"
    echo -e "   curl -X POST http://localhost:8080/api/v1/signals/generate \\"
    echo -e "     -H 'Content-Type: application/json' \\"
    echo -e "     -d '{\"symbol\":\"BTCUSD\",\"timeframe\":\"15m\",\"analysis\":{\"rsi\":65},\"current_price\":50000}'"
    echo ""
    echo -e "${CYAN}4. View Data in QuestDB:${NC}"
    echo -e "   Open http://localhost:9000"
    echo -e "   Query: SELECT * FROM signals ORDER BY timestamp DESC LIMIT 10;"
    echo ""
    echo -e "${CYAN}5. Monitor in Grafana:${NC}"
    echo -e "   Open http://localhost:3000"
    echo -e "   Login: admin/admin"
    echo ""
    echo -e "${CYAN}6. View Documentation:${NC}"
    echo -e "   cat FORWARD_EXECUTION_INTEGRATION.md"
    echo -e "   cat NEXT_STEPS_CHECKLIST.md"
    echo ""
}

display_test_info() {
    log_section "Test Information"

    echo ""
    echo -e "${YELLOW}Testing Mode: ${NC}${GREEN}$MODE${NC}"
    echo ""

    if [ "$MODE" = "simulated" ]; then
        echo -e "${CYAN}Simulated Mode Configuration:${NC}"
        echo -e "  Initial Balance:     \$100,000"
        echo -e "  Slippage:            5 bps (0.05%)"
        echo -e "  Trading Fee:         10 bps (0.10%)"
        echo -e "  Fill Delay:          100ms"
        echo -e "  Max Position Size:   \$10,000"
        echo -e "  Max Exposure:        \$50,000"
    elif [ "$MODE" = "paper" ]; then
        echo -e "${CYAN}Paper Trading Configuration:${NC}"
        echo -e "  Exchange:            Bybit Testnet"
        echo -e "  Real Market Data:    Yes"
        echo -e "  Real Order Book:     Yes"
        echo -e "  Real Money:          No (testnet only)"
    elif [ "$MODE" = "live" ]; then
        echo -e "${RED}LIVE TRADING - REAL MONEY AT RISK${NC}"
        echo -e "  Exchange:            Bybit Live"
        echo -e "  Real Money:          YES"
        echo -e "  Risk Management:     ENABLED"
    fi

    echo ""
    echo -e "${CYAN}Monitoring Duration:${NC}"
    echo -e "  Recommended:         48 hours minimum"
    echo -e "  Check frequency:     Every 6 hours"
    echo ""
}

# ============================================================================
# Main Execution
# ============================================================================

main() {
    log_section "FKS Trading System - Integration Test Startup"

    echo -e "${CYAN}Starting FKS Trading System with Forward → Execution integration${NC}"
    echo -e "${CYAN}Mode: ${GREEN}$MODE${NC}"
    echo ""

    # Run all steps
    check_prerequisites
    validate_mode
    stop_existing_services
    build_services
    start_infrastructure
    start_execution_service
    start_forward_service
    start_data_service
    start_monitoring

    # Display results
    display_status
    display_endpoints
    display_test_info
    display_next_steps

    log_success "✅ FKS Trading System is running!"
    log_info "Press Ctrl+C to view logs (they will continue in background)"

    # Follow logs
    cd "$PROJECT_DIR"
    docker compose logs -f forward execution data
}

# Run main function
main
