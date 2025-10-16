#!/bin/bash

# Test script for Docker setup validation
# This script tests the build and basic functionality

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_header() {
    echo
    echo -e "${BLUE}================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}================================${NC}"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_info() {
    echo -e "${YELLOW}→${NC} $1"
}

# Test 1: Check if Docker is running
print_header "Test 1: Docker Service"
if docker info > /dev/null 2>&1; then
    print_success "Docker is running"
else
    print_error "Docker is not running"
    exit 1
fi

# Test 2: Check if docker-compose.yml exists
print_header "Test 2: Configuration Files"
if [ -f "docker-compose.yml" ]; then
    print_success "docker-compose.yml exists"
else
    print_error "docker-compose.yml not found"
    exit 1
fi

if [ -f "requirements.txt" ]; then
    print_success "requirements.txt exists"
else
    print_error "requirements.txt not found"
    exit 1
fi

if [ -f ".env" ]; then
    print_success ".env file exists"
else
    print_info ".env file not found, will use defaults"
fi

# Test 3: Validate docker-compose.yml
print_header "Test 3: Docker Compose Validation"
if docker compose config > /dev/null 2>&1; then
    print_success "docker-compose.yml is valid"
else
    print_error "docker-compose.yml has errors"
    exit 1
fi

# Test 4: Check key dependencies in requirements.txt
print_header "Test 4: Requirements Validation"
check_requirement() {
    if grep -q "$1" requirements.txt; then
        print_success "$1 is in requirements"
    else
        print_error "$1 not found in requirements"
    fi
}

check_requirement "Django"
check_requirement "celery"
check_requirement "redis"
check_requirement "psycopg2-binary"
check_requirement "chromadb"

# Test 5: Check redis version compatibility
print_header "Test 5: Redis Version Compatibility"
REDIS_VERSION=$(grep "^redis" requirements.txt | grep -v "django-redis" | grep -v "celery\[redis\]")
if echo "$REDIS_VERSION" | grep -q ">=5.0.0,<5.1.0"; then
    print_success "Redis version is compatible with celery (${REDIS_VERSION})"
else
    print_error "Redis version may be incompatible: ${REDIS_VERSION}"
    print_info "Expected: redis>=5.0.0,<5.1.0 for celery[redis]>=5.5.3 compatibility"
fi

# Test 6: Try building the image (this is the real test)
print_header "Test 6: Docker Build Test"
print_info "Building celery_worker image (this may take a few minutes)..."
print_info "Build started at: $(date)"

BUILD_LOG=$(mktemp)
if docker compose build celery_worker > "$BUILD_LOG" 2>&1; then
    print_success "Docker build completed successfully!"
    
    # Check build details
    print_info "Checking installed packages in built image..."
    if docker compose run --rm celery_worker pip list | grep -E "(celery|redis|Django)" > /dev/null 2>&1; then
        print_success "Core packages are installed"
    fi
    
    # Verify celery executable exists
    print_info "Verifying celery executable..."
    if docker compose run --rm celery_worker which celery > /dev/null 2>&1; then
        print_success "Celery executable found"
    else
        print_error "Celery executable not found in container"
    fi
else
    print_error "Docker build failed!"
    echo
    echo "Last 50 lines of build log:"
    tail -50 "$BUILD_LOG"
    rm "$BUILD_LOG"
    exit 1
fi
rm "$BUILD_LOG"

# Test 7: Verify Dockerfile uses uv
print_header "Test 7: Dockerfile Configuration"
if grep -q "uv pip install" docker/Dockerfile; then
    print_success "Dockerfile uses uv for faster installation"
else
    print_info "Dockerfile uses standard pip"
fi

# Test 8: Check services configuration
print_header "Test 8: Services Configuration"
SERVICES=$(docker compose config --services)
for service in web db redis celery_worker celery_beat flower; do
    if echo "$SERVICES" | grep -q "^${service}$"; then
        print_success "Service '$service' is configured"
    else
        print_error "Service '$service' is missing"
    fi
done

# Test 9: Check port mappings
print_header "Test 9: Port Mappings"
check_port() {
    if docker compose config | grep -q "$1:$2"; then
        print_success "Port $1 mapped correctly for $3"
    else
        print_info "Port $1 may not be mapped for $3"
    fi
}

check_port "8000" "8000" "Django"
check_port "5555" "5555" "Flower"
check_port "5432" "5432" "PostgreSQL"
check_port "5050" "80" "pgAdmin"

# Final Summary
print_header "Test Summary"
echo
echo -e "${GREEN}All critical tests passed!${NC}"
echo
echo "Next steps:"
echo "  1. Run: ./start.sh rebuild"
echo "  2. Wait for containers to start"
echo "  3. Access services:"
echo "     - Django:  http://localhost:8000"
echo "     - Flower:  http://localhost:5555"
echo "     - pgAdmin: http://localhost:5050"
echo
echo "For more commands, run: ./start.sh help"
echo
