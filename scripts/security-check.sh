#!/bin/bash
# security-check.sh - Check for common security issues in FKS deployment

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=========================================="
echo "FKS Security Check"
echo -e "==========================================${NC}\n"

ISSUES_FOUND=0

# Check 1: .env file should not be committed
echo -e "${BLUE}[1/8]${NC} Checking if .env is in .gitignore..."
if grep -q "^\.env$" .gitignore; then
    echo -e "${GREEN}✓${NC} .env is properly gitignored"
else
    echo -e "${RED}✗${NC} .env is NOT in .gitignore"
    ISSUES_FOUND=$((ISSUES_FOUND + 1))
fi

# Check 2: Check for weak passwords in .env
echo -e "${BLUE}[2/8]${NC} Checking for weak passwords..."
if [ -f .env ]; then
    if grep -E "(PASSWORD=postgres|PASSWORD=admin|PASSWORD=password|PASSWORD=123)" .env > /dev/null; then
        echo -e "${RED}✗${NC} Weak passwords detected in .env"
        echo -e "  ${YELLOW}Please use strong passwords (min 16 characters)${NC}"
        ISSUES_FOUND=$((ISSUES_FOUND + 1))
    else
        echo -e "${GREEN}✓${NC} No obvious weak passwords found"
    fi
else
    echo -e "${YELLOW}!${NC} .env file not found (may need to create from .env.example)"
fi

# Check 3: Check for exposed secrets
echo -e "${BLUE}[3/8]${NC} Checking for exposed API keys/tokens..."
if [ -f .env ]; then
    if grep -E "(WEBHOOK_URL=https://|CLAIM_TOKEN=.{20,})" .env > /dev/null; then
        echo -e "${YELLOW}!${NC} API keys/webhooks found in .env"
        echo -e "  ${YELLOW}Ensure .env is never committed to git${NC}"
    else
        echo -e "${GREEN}✓${NC} No exposed tokens detected"
    fi
fi

# Check 4: Check Docker port exposure
echo -e "${BLUE}[4/8]${NC} Checking Docker port configuration..."
if grep -q "5432:5432" docker-compose.yml; then
    echo -e "${YELLOW}!${NC} PostgreSQL port exposed to host (5432)"
    echo -e "  ${YELLOW}Consider removing in production${NC}"
fi
if grep -q "6379:6379" docker-compose.yml; then
    echo -e "${YELLOW}!${NC} Redis port exposed to host (6379)"
    echo -e "  ${YELLOW}Consider removing in production${NC}"
fi

# Check 5: Check for HTTPS configuration
echo -e "${BLUE}[5/8]${NC} Checking SSL/HTTPS configuration..."
if [ -d nginx/ssl ]; then
    if [ -f nginx/ssl/*.crt ] || [ -f nginx/ssl/*.pem ]; then
        echo -e "${GREEN}✓${NC} SSL certificates found"
    else
        echo -e "${YELLOW}!${NC} No SSL certificates found"
        echo -e "  ${YELLOW}Run: make setup-ssl or use Let's Encrypt${NC}"
    fi
else
    echo -e "${YELLOW}!${NC} nginx/ssl directory not found"
fi

# Check 6: Check Django SECRET_KEY
echo -e "${BLUE}[6/8]${NC} Checking Django SECRET_KEY..."
if [ -f .env ]; then
    if grep -q "SECRET_KEY=django-insecure" .env; then
        echo -e "${RED}✗${NC} Using default/insecure Django SECRET_KEY"
        echo -e "  ${YELLOW}Generate new key: python -c \"from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())\"${NC}"
        ISSUES_FOUND=$((ISSUES_FOUND + 1))
    else
        echo -e "${GREEN}✓${NC} Custom Django SECRET_KEY configured"
    fi
fi

# Check 7: Check Docker image security
echo -e "${BLUE}[7/8]${NC} Checking Docker image configuration..."
if grep -q "python:3.13-slim" docker/Dockerfile; then
    echo -e "${GREEN}✓${NC} Using minimal Python image"
else
    echo -e "${YELLOW}!${NC} Consider using slim/alpine images"
fi

# Check 8: Check for .dockerignore
echo -e "${BLUE}[8/8]${NC} Checking for .dockerignore..."
if [ -f .dockerignore ]; then
    echo -e "${GREEN}✓${NC} .dockerignore exists"
else
    echo -e "${YELLOW}!${NC} .dockerignore not found"
    echo -e "  ${YELLOW}Create one to speed up builds and reduce image size${NC}"
fi

echo ""
echo -e "${BLUE}==========================================${NC}"
if [ $ISSUES_FOUND -eq 0 ]; then
    echo -e "${GREEN}✓ No critical security issues found!${NC}"
else
    echo -e "${RED}✗ Found $ISSUES_FOUND critical security issue(s)${NC}"
    echo -e "${YELLOW}Please address the issues above before deploying to production${NC}"
    exit 1
fi
echo -e "${BLUE}==========================================${NC}"
