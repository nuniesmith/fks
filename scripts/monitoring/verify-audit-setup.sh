#!/bin/bash
set -euo pipefail

# Audit Service Setup Verification Script
# Verifies that the audit service is properly integrated into FKS

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

CHECKS_PASSED=0
CHECKS_FAILED=0

info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

success() {
    echo -e "${GREEN}[✓]${NC} $1"
    ((CHECKS_PASSED++))
}

warn() {
    echo -e "${YELLOW}[⚠]${NC} $1"
}

error() {
    echo -e "${RED}[✗]${NC} $1"
    ((CHECKS_FAILED++))
}

check_file() {
    local file=$1
    local description=$2

    if [ -f "$PROJECT_ROOT/$file" ]; then
        success "$description exists: $file"
        return 0
    else
        error "$description missing: $file"
        return 1
    fi
}

check_directory() {
    local dir=$1
    local description=$2

    if [ -d "$PROJECT_ROOT/$dir" ]; then
        success "$description exists: $dir"
        return 0
    else
        warn "$description missing: $dir (will be created on first run)"
        return 1
    fi
}

check_service_in_compose() {
    local compose_file=$1
    local service_name=$2

    if grep -q "^[[:space:]]*${service_name}:" "$PROJECT_ROOT/$compose_file"; then
        success "Service '$service_name' found in $compose_file"
        return 0
    else
        error "Service '$service_name' not found in $compose_file"
        return 1
    fi
}

check_env_var() {
    local compose_file=$1
    local var_name=$2

    if grep -q "$var_name" "$PROJECT_ROOT/$compose_file"; then
        success "Environment variable '$var_name' configured in $compose_file"
        return 0
    else
        warn "Environment variable '$var_name' not found in $compose_file"
        return 1
    fi
}

echo ""
echo "╔════════════════════════════════════════════════════╗"
echo "║   Audit Service Integration Verification          ║"
echo "║   Checking FKS setup for audit service             ║"
echo "╚════════════════════════════════════════════════════╝"
echo ""

# ============================================================================
# 1. Source Files
# ============================================================================
info "Step 1: Checking audit service source files..."
echo ""

check_file "src/audit/Cargo.toml" "Cargo manifest"
check_file "src/audit/README.md" "README documentation"
check_file "src/audit/run.sh" "Helper script"
check_file "src/audit/.env.example" "Environment template"
check_file "src/audit/src/lib.rs" "Library root"
check_file "src/audit/src/server.rs" "Server implementation"
check_file "src/audit/src/bin/server.rs" "Server binary"
check_file "src/audit/src/bin/cli.rs" "CLI binary"
check_file "src/audit/src/scanner.rs" "Static scanner"
check_file "src/audit/src/tags.rs" "Tag scanner"
check_file "src/audit/src/llm.rs" "LLM client"
check_file "src/audit/src/git.rs" "Git manager"
check_file "src/audit/src/tasks.rs" "Task generator"

echo ""

# ============================================================================
# 2. Documentation
# ============================================================================
info "Step 2: Checking documentation..."
echo ""

check_file "docs/AUDIT_SETUP.md" "Setup guide"
check_file "src/audit/QUICK_START.md" "Quick reference"

echo ""

# ============================================================================
# 3. Docker Configuration
# ============================================================================
info "Step 3: Checking Docker Compose configuration..."
echo ""

check_file "docker-compose.yml" "Base compose file"
check_file "docker-compose.prod.yml" "Production compose file"

if [ -f "$PROJECT_ROOT/docker-compose.yml" ]; then
    check_service_in_compose "docker-compose.yml" "audit"
    check_env_var "docker-compose.yml" "AUDIT_HOST"
    check_env_var "docker-compose.yml" "AUDIT_PORT"
    check_env_var "docker-compose.yml" "XAI_API_KEY"
    check_env_var "docker-compose.yml" "LLM_ENABLED"
fi

if [ -f "$PROJECT_ROOT/docker-compose.prod.yml" ]; then
    check_service_in_compose "docker-compose.prod.yml" "audit"
fi

echo ""

# ============================================================================
# 4. Data Directories
# ============================================================================
info "Step 4: Checking data directories..."
echo ""

check_directory "data/audit" "Audit data root"
check_directory "data/audit/workspace" "Workspace directory"
check_directory "data/audit/reports" "Reports directory"
check_directory "data/audit/tasks" "Tasks directory"

echo ""

# ============================================================================
# 5. Environment Configuration
# ============================================================================
info "Step 5: Checking environment configuration..."
echo ""

if [ -f "$PROJECT_ROOT/.env" ]; then
    success ".env file exists"

    # Check for audit-related variables
    if grep -q "AUDIT_LLM_ENABLED" "$PROJECT_ROOT/.env"; then
        success "AUDIT_LLM_ENABLED configured in .env"
    else
        warn "AUDIT_LLM_ENABLED not found in .env (optional)"
    fi

    if grep -q "XAI_API_KEY" "$PROJECT_ROOT/.env"; then
        success "XAI_API_KEY configured in .env"

        # Check if it's the placeholder
        if grep -q "XAI_API_KEY=$" "$PROJECT_ROOT/.env" || grep -q "XAI_API_KEY=\"\"" "$PROJECT_ROOT/.env"; then
            warn "XAI_API_KEY is empty (LLM features will be disabled)"
        fi
    else
        warn "XAI_API_KEY not found in .env (LLM features will be disabled)"
    fi
else
    warn ".env file not found (optional for Docker Compose)"
fi

echo ""

# ============================================================================
# 6. Build Tools
# ============================================================================
info "Step 6: Checking build tools..."
echo ""

if command -v docker &> /dev/null; then
    DOCKER_VERSION=$(docker --version | awk '{print $3}' | sed 's/,//')
    success "Docker installed: $DOCKER_VERSION"
else
    error "Docker not found (required for containerized deployment)"
fi

if command -v docker-compose &> /dev/null || docker compose version &> /dev/null 2>&1; then
    if docker compose version &> /dev/null 2>&1; then
        COMPOSE_VERSION=$(docker compose version --short)
        success "Docker Compose installed: $COMPOSE_VERSION"
    else
        COMPOSE_VERSION=$(docker-compose --version | awk '{print $3}' | sed 's/,//')
        success "Docker Compose (standalone) installed: $COMPOSE_VERSION"
    fi
else
    error "Docker Compose not found (required for containerized deployment)"
fi

if command -v cargo &> /dev/null; then
    CARGO_VERSION=$(cargo --version | awk '{print $2}')
    success "Rust/Cargo installed: $CARGO_VERSION"
else
    warn "Rust/Cargo not found (required for local development only)"
fi

echo ""

# ============================================================================
# 7. Network Configuration
# ============================================================================
info "Step 7: Checking network configuration..."
echo ""

# Check if port 8080 is available
if command -v netstat &> /dev/null; then
    if netstat -tuln 2>/dev/null | grep -q ":8080 "; then
        warn "Port 8080 is already in use (may conflict with audit service)"
    else
        success "Port 8080 is available"
    fi
elif command -v ss &> /dev/null; then
    if ss -tuln 2>/dev/null | grep -q ":8080 "; then
        warn "Port 8080 is already in use (may conflict with audit service)"
    else
        success "Port 8080 is available"
    fi
else
    warn "Cannot check port availability (netstat/ss not found)"
fi

# Check if fks-network exists (if Docker is running)
if command -v docker &> /dev/null; then
    if docker network ls 2>/dev/null | grep -q "fks-network\|fks_br"; then
        success "FKS Docker network exists"
    else
        warn "FKS Docker network not found (will be created on first run)"
    fi
fi

echo ""

# ============================================================================
# 8. Service Connectivity (if running)
# ============================================================================
info "Step 8: Checking if audit service is running..."
echo ""

if command -v curl &> /dev/null; then
    if curl -sf http://localhost:8080/health > /dev/null 2>&1; then
        success "Audit service is running and healthy"

        # Get service info
        HEALTH_RESPONSE=$(curl -s http://localhost:8080/health)
        echo "     Response: $HEALTH_RESPONSE"
    else
        info "Audit service is not running (this is OK)"
    fi
elif command -v wget &> /dev/null; then
    if wget -q --spider http://localhost:8080/health 2>/dev/null; then
        success "Audit service is running and healthy"
    else
        info "Audit service is not running (this is OK)"
    fi
else
    warn "Cannot check service health (curl/wget not found)"
fi

echo ""

# ============================================================================
# 9. Dockerfile Check
# ============================================================================
info "Step 9: Checking Dockerfile configuration..."
echo ""

if [ -f "$PROJECT_ROOT/docker/Dockerfile" ]; then
    success "Main Dockerfile exists"

    # Check if rust target exists
    if grep -q "^FROM.*AS rust" "$PROJECT_ROOT/docker/Dockerfile"; then
        success "Rust build target defined in Dockerfile"
    else
        error "Rust build target not found in Dockerfile"
    fi
else
    error "docker/Dockerfile not found"
fi

echo ""

# ============================================================================
# Summary
# ============================================================================
echo ""
echo "╔════════════════════════════════════════════════════╗"
echo "║                  Verification Summary              ║"
echo "╚════════════════════════════════════════════════════╝"
echo ""

TOTAL_CHECKS=$((CHECKS_PASSED + CHECKS_FAILED))
SUCCESS_RATE=0

if [ $TOTAL_CHECKS -gt 0 ]; then
    SUCCESS_RATE=$((CHECKS_PASSED * 100 / TOTAL_CHECKS))
fi

echo -e "Total Checks:    $TOTAL_CHECKS"
echo -e "${GREEN}Passed:          $CHECKS_PASSED${NC}"
echo -e "${RED}Failed:          $CHECKS_FAILED${NC}"
echo -e "Success Rate:    $SUCCESS_RATE%"
echo ""

# ============================================================================
# Recommendations
# ============================================================================
if [ $CHECKS_FAILED -gt 0 ]; then
    echo "╔════════════════════════════════════════════════════╗"
    echo "║                 Recommendations                    ║"
    echo "╚════════════════════════════════════════════════════╝"
    echo ""

    if [ ! -d "$PROJECT_ROOT/data/audit/workspace" ]; then
        info "Create data directories:"
        echo "  mkdir -p data/audit/{workspace,reports,tasks}"
        echo ""
    fi

    if ! grep -q "XAI_API_KEY" "$PROJECT_ROOT/.env" 2>/dev/null; then
        info "Configure environment variables in .env:"
        echo "  AUDIT_LLM_ENABLED=false"
        echo "  XAI_API_KEY=your-api-key-here"
        echo ""
    fi

    if ! command -v docker &> /dev/null; then
        info "Install Docker:"
        echo "  https://docs.docker.com/get-docker/"
        echo ""
    fi
fi

# ============================================================================
# Next Steps
# ============================================================================
echo "╔════════════════════════════════════════════════════╗"
echo "║                    Next Steps                      ║"
echo "╚════════════════════════════════════════════════════╝"
echo ""

if [ $CHECKS_FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ Setup looks good!${NC}"
    echo ""
    echo "To start the audit service:"
    echo ""
    echo "  # Development (build from source)"
    echo "  docker compose up audit"
    echo ""
    echo "  # Production (pre-built image)"
    echo "  docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d audit"
    echo ""
    echo "  # View logs"
    echo "  docker compose logs -f audit"
    echo ""
    echo "  # Test the service"
    echo "  curl http://localhost:8080/health"
    echo ""
else
    echo -e "${YELLOW}⚠ Some checks failed. Review the issues above.${NC}"
    echo ""
    echo "For detailed setup instructions, see:"
    echo "  - docs/AUDIT_SETUP.md"
    echo "  - src/audit/README.md"
    echo "  - src/audit/QUICK_START.md"
    echo ""
fi

echo "╔════════════════════════════════════════════════════╗"
echo "║                   Documentation                    ║"
echo "╚════════════════════════════════════════════════════╝"
echo ""
echo "  Full Guide:      docs/AUDIT_SETUP.md"
echo "  Quick Start:     src/audit/QUICK_START.md"
echo "  Service README:  src/audit/README.md"
echo "  Helper Script:   src/audit/run.sh"
echo ""

# Exit with appropriate code
if [ $CHECKS_FAILED -gt 0 ]; then
    exit 1
else
    exit 0
fi
