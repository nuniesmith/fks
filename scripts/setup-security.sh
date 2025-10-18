#!/bin/bash
# Security Setup Helper Script
# Generates secure passwords and helps configure .env file

set -e

echo "================================================"
echo "FKS Trading Platform - Security Setup Helper"
echo "================================================"
echo ""

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if .env exists
if [ -f .env ]; then
    echo -e "${YELLOW}⚠️  Warning: .env file already exists!${NC}"
    read -p "Do you want to regenerate passwords? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Exiting without changes."
        exit 0
    fi
    echo ""
fi

echo "Generating secure passwords..."
echo ""

# Generate passwords
POSTGRES_PASSWORD=$(openssl rand -base64 32 | tr -d '\n')
PGADMIN_PASSWORD=$(openssl rand -base64 24 | tr -d '\n')
REDIS_PASSWORD=$(openssl rand -base64 32 | tr -d '\n')
GRAFANA_PASSWORD=$(openssl rand -base64 24 | tr -d '\n')

# Generate Django secret key (requires Python)
if command -v python3 &> /dev/null; then
    DJANGO_SECRET_KEY=$(python3 -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())")
else
    echo -e "${YELLOW}⚠️  Python3 not found. Using openssl for Django secret key.${NC}"
    DJANGO_SECRET_KEY=$(openssl rand -base64 50 | tr -d '\n')
fi

echo "✅ Generated secure passwords"
echo ""

# Display generated passwords
echo "================================================"
echo "Generated Credentials (SAVE THESE SECURELY!):"
echo "================================================"
echo ""
echo "PostgreSQL Password:"
echo "  $POSTGRES_PASSWORD"
echo ""
echo "PgAdmin Password:"
echo "  $PGADMIN_PASSWORD"
echo ""
echo "Redis Password:"
echo "  $REDIS_PASSWORD"
echo ""
echo "Grafana Password:"
echo "  $GRAFANA_PASSWORD"
echo ""
echo "Django Secret Key:"
echo "  $DJANGO_SECRET_KEY"
echo ""
echo "================================================"
echo ""

# Ask if user wants to save to .env
read -p "Save these to .env file? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    # Copy .env.example to .env if it doesn't exist
    if [ ! -f .env ]; then
        cp .env.example .env
        echo "✅ Created .env from .env.example"
    fi
    
    # Update .env with generated passwords
    # Use | as delimiter since passwords may contain /
    sed -i "s|POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=$POSTGRES_PASSWORD|g" .env
    sed -i "s|PGADMIN_PASSWORD=.*|PGADMIN_PASSWORD=$PGADMIN_PASSWORD|g" .env
    sed -i "s|REDIS_PASSWORD=.*|REDIS_PASSWORD=$REDIS_PASSWORD|g" .env
    sed -i "s|GRAFANA_PASSWORD=.*|GRAFANA_PASSWORD=$GRAFANA_PASSWORD|g" .env
    sed -i "s|DJANGO_SECRET_KEY=.*|DJANGO_SECRET_KEY=$DJANGO_SECRET_KEY|g" .env
    
    echo "✅ Updated .env with generated passwords"
    echo ""
    
    # Set PostgreSQL SSL to on
    if grep -q "POSTGRES_SSL_ENABLED=" .env; then
        sed -i "s|POSTGRES_SSL_ENABLED=.*|POSTGRES_SSL_ENABLED=on|g" .env
    else
        echo "POSTGRES_SSL_ENABLED=on" >> .env
    fi
    
    if grep -q "POSTGRES_HOST_AUTH_METHOD=" .env; then
        sed -i "s|POSTGRES_HOST_AUTH_METHOD=.*|POSTGRES_HOST_AUTH_METHOD=scram-sha-256|g" .env
    else
        echo "POSTGRES_HOST_AUTH_METHOD=scram-sha-256" >> .env
    fi
    
    echo "✅ Enabled PostgreSQL SSL and secure authentication"
    echo ""
else
    echo -e "${YELLOW}⚠️  Passwords NOT saved to .env. Please save them securely!${NC}"
    echo ""
fi

# Check if .env is in git
echo "================================================"
echo "Security Verification"
echo "================================================"
echo ""

if git rev-parse --is-inside-work-tree > /dev/null 2>&1; then
    # Check if .env is tracked by git
    if git ls-files --error-unmatch .env > /dev/null 2>&1; then
        echo -e "${RED}❌ ERROR: .env is tracked by git!${NC}"
        echo "   Run: git rm --cached .env"
        echo "   Then: git commit -m 'Remove .env from git'"
        echo ""
    else
        echo "✅ .env is NOT tracked by git (good!)"
    fi
    
    # Check if .env is in .gitignore
    if grep -q "^\.env$" .gitignore 2>/dev/null; then
        echo "✅ .env is in .gitignore (good!)"
    else
        echo -e "${YELLOW}⚠️  .env not found in .gitignore${NC}"
        echo "   Add it with: echo '.env' >> .gitignore"
    fi
else
    echo "Not a git repository. Skipping git checks."
fi

echo ""
echo "================================================"
echo "Next Steps:"
echo "================================================"
echo ""
echo "1. Review your .env file and add any missing values:"
echo "   - DISCORD_WEBHOOK_URL (optional)"
echo "   - BINANCE_API_KEY (optional)"
echo "   - OPENAI_API_KEY (optional)"
echo ""
echo "2. Start the services:"
echo "   make up"
echo ""
echo "3. Verify services are running with authentication:"
echo "   docker-compose ps"
echo ""
echo "4. Test the application:"
echo "   Open http://localhost:8000"
echo ""
echo "5. Run security audit (when in deployment environment):"
echo "   pip-audit -r requirements.txt"
echo ""
echo "================================================"
echo "⚠️  IMPORTANT SECURITY REMINDERS:"
echo "================================================"
echo ""
echo "✓ NEVER commit .env to git"
echo "✓ Save passwords in a secure password manager"
echo "✓ Rotate secrets every 90 days"
echo "✓ Use different passwords for each service"
echo "✓ Enable 2FA on external services (Discord, etc.)"
echo ""
echo "================================================"
