#!/bin/bash
# Weekly project health update script
# Run this weekly or after major changes

set -e

echo "🔄 Starting weekly project health update..."

# Change to project root
cd "$(dirname "$0")/.."

# Run analysis
echo "📊 Running project analysis..."
python3 scripts/analyze_project.py --summary

# Update dashboard
echo "📈 Updating health dashboard..."
python3 scripts/update_dashboard.py

# Optional: Commit changes
if [[ "$1" == "--commit" ]]; then
    echo "💾 Committing dashboard update..."
    git add docs/PROJECT_HEALTH_DASHBOARD.md metrics.json
    git commit -m "chore: update project health dashboard [weekly]"
fi

echo "✅ Weekly update complete!"
echo "📋 Check docs/PROJECT_HEALTH_DASHBOARD.md for current status"