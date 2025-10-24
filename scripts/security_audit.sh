#!/bin/bash
# Security audit script for FKS Trading Platform
# Run this script regularly to check for security vulnerabilities

set -e

echo "╔═══════════════════════════════════════════════════════════╗"
echo "║         FKS Trading Platform - Security Audit             ║"
echo "╔═══════════════════════════════════════════════════════════╗"
echo ""

# Check if running in Docker or local
if [ -f /.dockerenv ]; then
    echo "✓ Running in Docker container"
    IN_DOCKER=true
else
    echo "⚠ Running on host system"
    IN_DOCKER=false
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "1. Checking Python package vulnerabilities with pip-audit"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if command -v pip-audit &> /dev/null; then
    pip-audit --desc --format=json > /tmp/pip-audit-results.json 2>&1 || true
    
    # Check if vulnerabilities found
    if [ -s /tmp/pip-audit-results.json ]; then
        echo "⚠ VULNERABILITIES FOUND!"
        pip-audit --desc
    else
        echo "✓ No known vulnerabilities found"
    fi
else
    echo "⚠ pip-audit not installed. Installing..."
    pip install pip-audit
    echo "✓ pip-audit installed. Re-run this script."
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "2. Checking .env file for insecure passwords"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ -f .env ]; then
    if grep -q "CHANGE_ME\|CHANGE_THIS\|django-insecure" .env; then
        echo "⚠ WARNING: Found placeholder passwords in .env file!"
        grep "CHANGE_ME\|CHANGE_THIS\|django-insecure" .env
    else
        echo "✓ No placeholder passwords found"
    fi
    
    # Check for weak passwords (less than 20 characters)
    echo ""
    echo "Checking password lengths..."
    while IFS= read -r line; do
        if [[ $line =~ _PASSWORD=(.+) ]]; then
            password="${BASH_REMATCH[1]}"
            if [ ${#password} -lt 20 ]; then
                echo "⚠ WARNING: Short password detected: ${line%%=*}"
            fi
        fi
    done < .env
else
    echo "⚠ .env file not found"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "3. Checking Django security settings"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ -f src/web/django/settings.py ]; then
    echo "Checking django-axes configuration..."
    if grep -q "AXES_FAILURE_LIMIT" src/web/django/settings.py; then
        echo "✓ django-axes is configured"
    else
        echo "⚠ django-axes not configured"
    fi
    
    echo "Checking django-ratelimit configuration..."
    if grep -q "RATELIMIT_ENABLE" src/web/django/settings.py; then
        echo "✓ django-ratelimit is configured"
    else
        echo "⚠ django-ratelimit not configured"
    fi
    
    echo "Checking DEBUG setting..."
    if grep -q 'DEBUG = False' src/web/django/settings.py; then
        echo "✓ DEBUG is set to False"
    else
        echo "⚠ WARNING: DEBUG may be enabled"
    fi
else
    echo "⚠ Django settings file not found"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "4. Checking database SSL configuration"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ -f .env ]; then
    if grep -q "POSTGRES_SSL_ENABLED=on" .env; then
        echo "✓ PostgreSQL SSL is enabled"
    else
        echo "⚠ WARNING: PostgreSQL SSL may not be enabled"
    fi
else
    echo "⚠ .env file not found"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "5. Summary"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

echo ""
echo "Security audit complete!"
echo ""
echo "Next steps:"
echo "  1. Review any warnings above"
echo "  2. Update insecure passwords with: openssl rand -base64 32"
echo "  3. Enable SSL for production deployments"
echo "  4. Re-run this audit after making changes"
echo ""
