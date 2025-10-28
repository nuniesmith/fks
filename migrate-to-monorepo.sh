#!/bin/bash
# FKS Monorepo Migration Script
# Converts multi-repo structure to clean monorepo

set -e

echo "=== FKS Monorepo Migration ==="
echo ""
echo "This will:"
echo "  1. Rename repo/ → services/"
echo "  2. Remove git submodule configs (if any)"
echo "  3. Update docker-compose.yml paths"
echo "  4. Update Makefile commands"
echo ""
read -p "Continue? [y/N] " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 1
fi

echo ""
echo "=== Step 1: Rename repo/ → services/ ==="
if [ -d "repo" ]; then
    echo "Moving repo/ to services/..."
    mv repo services
    echo "✓ Renamed"
else
    echo "⚠ repo/ directory not found (may already be renamed)"
fi

echo ""
echo "=== Step 2: Remove Git Submodules ==="
if [ -f ".gitmodules" ]; then
    echo "Removing .gitmodules..."
    rm -f .gitmodules
    echo "✓ Removed .gitmodules"
else
    echo "✓ No .gitmodules file"
fi

# Remove submodule configs from .git/config
echo "Cleaning submodule references from .git/config..."
for module in api app ai data execution ninja web; do
    git config --file .git/config --remove-section "submodule.repo/$module" 2>/dev/null || true
done
echo "✓ Cleaned git config"

# Remove .git directories in services (if submodules)
if [ -d "services" ]; then
    echo "Removing submodule .git directories..."
    find services -name ".git" -type d -exec rm -rf {} + 2>/dev/null || true
    find services -name ".git" -type f -delete 2>/dev/null || true
    echo "✓ Cleaned service directories"
fi

echo ""
echo "=== Step 3: Update docker-compose.yml ==="
if [ -f "docker-compose.yml" ]; then
    echo "Updating paths from repo/ to services/..."
    sed -i.bak 's|context: \./repo/|context: ./services/|g' docker-compose.yml
    sed -i.bak 's|volumes:.*\./repo/|volumes:\n      - ./services/|g' docker-compose.yml
    echo "✓ Updated docker-compose.yml (backup: docker-compose.yml.bak)"
else
    echo "⚠ docker-compose.yml not found"
fi

if [ -f "docker-compose.gpu.yml" ]; then
    echo "Updating GPU compose file..."
    sed -i.bak 's|context: \./repo/|context: ./services/|g' docker-compose.gpu.yml
    sed -i.bak 's|volumes:.*\./repo/|volumes:\n      - ./services/|g' docker-compose.gpu.yml
    echo "✓ Updated docker-compose.gpu.yml"
fi

echo ""
echo "=== Step 4: Update Makefile ==="
if [ -f "Makefile" ]; then
    echo "Updating Makefile commands..."
    sed -i.bak 's|repo/|services/|g' Makefile
    echo "✓ Updated Makefile (backup: Makefile.bak)"
fi

echo ""
echo "=== Step 5: Update Documentation ==="
echo "Updating references in docs..."
find docs -name "*.md" -type f -exec sed -i.bak 's|repo/|services/|g' {} \; 2>/dev/null || true
find . -name "README.md" -maxdepth 1 -exec sed -i.bak 's|repo/|services/|g' {} \; 2>/dev/null || true
echo "✓ Updated documentation"

echo ""
echo "=== Step 6: Git Staging ==="
echo "Staging changes..."
git add -A 2>/dev/null || echo "⚠ Not in git repository or changes already staged"

echo ""
echo "=== Migration Complete! ==="
echo ""
echo "Next steps:"
echo "  1. Review changes: git status"
echo "  2. Test services: make up"
echo "  3. View logs: make logs"
echo "  4. Commit: git commit -m 'refactor: Migrate to monorepo architecture'"
echo ""
echo "Access points after starting:"
echo "  - FKS Main: http://localhost:8000"
echo "  - Health Dashboard: http://localhost:8000/health/dashboard/"
echo "  - Grafana: http://localhost:3000"
echo ""
echo "Backup files created (can delete if everything works):"
echo "  - docker-compose.yml.bak"
echo "  - docker-compose.gpu.yml.bak"
echo "  - Makefile.bak"
echo "  - docs/*.md.bak"
echo ""
