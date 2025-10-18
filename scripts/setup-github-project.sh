#!/bin/bash

# GitHub Project Setup Script for FKS
# This script helps configure GitHub Project integration

set -e

echo "🚀 FKS GitHub Project Setup"
echo "================================"
echo

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if gh CLI is installed
if ! command -v gh &> /dev/null; then
    echo -e "${RED}✗ GitHub CLI (gh) is not installed${NC}"
    echo "  Install from: https://cli.github.com/"
    exit 1
fi

echo -e "${GREEN}✓ GitHub CLI found${NC}"

# Check if logged in
if ! gh auth status &> /dev/null; then
    echo -e "${YELLOW}! Not logged in to GitHub${NC}"
    echo "  Running: gh auth login"
    gh auth login
fi

echo -e "${GREEN}✓ Authenticated with GitHub${NC}"
echo

# Get user info
GITHUB_USER=$(gh api user --jq '.login')
echo "Logged in as: $GITHUB_USER"
echo

# Prompt for project name
read -p "Enter project name (default: FKS Development): " PROJECT_NAME
PROJECT_NAME=${PROJECT_NAME:-"FKS Development"}

# Prompt for project type
echo
echo "Select project type:"
echo "  1) Board (Kanban-style)"
echo "  2) Table (Spreadsheet-style)"
echo "  3) Roadmap (Timeline view)"
read -p "Choice (1-3, default: 1): " PROJECT_TYPE
PROJECT_TYPE=${PROJECT_TYPE:-1}

case $PROJECT_TYPE in
    1) TEMPLATE="Board" ;;
    2) TEMPLATE="Table" ;;
    3) TEMPLATE="Roadmap" ;;
    *) TEMPLATE="Board" ;;
esac

echo
echo "Creating project: '$PROJECT_NAME' with template: $TEMPLATE"

# Create project
echo "Running: gh project create --owner $GITHUB_USER --title \"$PROJECT_NAME\""

# Note: gh project create doesn't exist yet, so we'll provide instructions
echo
echo -e "${YELLOW}! GitHub CLI doesn't support project creation yet${NC}"
echo
echo "Please create the project manually:"
echo "1. Go to: https://github.com/$GITHUB_USER?tab=projects"
echo "2. Click 'New project'"
echo "3. Choose '$TEMPLATE' template"
echo "4. Name it: '$PROJECT_NAME'"
echo "5. Click 'Create project'"
echo
read -p "Press Enter when you've created the project..."

# Get project number
echo
echo "Find your project number from the URL:"
echo "  https://github.com/users/$GITHUB_USER/projects/NUMBER"
echo
read -p "Enter your project number: " PROJECT_NUMBER

if [ -z "$PROJECT_NUMBER" ]; then
    echo -e "${RED}✗ Project number is required${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Project number: $PROJECT_NUMBER${NC}"

# Update workflow file
WORKFLOW_FILE=".github/workflows/sync-to-project.yml"

if [ ! -f "$WORKFLOW_FILE" ]; then
    echo -e "${RED}✗ Workflow file not found: $WORKFLOW_FILE${NC}"
    echo "  Make sure you're in the FKS repository root"
    exit 1
fi

echo
echo "Updating workflow file with project number..."

# Backup original
cp "$WORKFLOW_FILE" "$WORKFLOW_FILE.bak"

# Update project number
sed -i "s/PROJECT_NUMBER: [0-9]*/PROJECT_NUMBER: $PROJECT_NUMBER/" "$WORKFLOW_FILE"

echo -e "${GREEN}✓ Updated $WORKFLOW_FILE${NC}"
echo "  (Backup saved as $WORKFLOW_FILE.bak)"

# Link repository to project
echo
echo "Linking repository to project..."
read -p "Repository name (default: fks): " REPO_NAME
REPO_NAME=${REPO_NAME:-fks}

echo
echo "To link the repository to your project:"
echo "1. Go to: https://github.com/$GITHUB_USER/$REPO_NAME"
echo "2. Click 'Projects' tab"
echo "3. Click 'Link a project'"
echo "4. Select '$PROJECT_NAME'"
echo
read -p "Press Enter when you've linked the repository..."

# Test the setup
echo
echo "Testing the setup..."
echo
read -p "Create a test issue? (y/n): " CREATE_TEST

if [ "$CREATE_TEST" = "y" ]; then
    echo "Creating test issue..."
    gh issue create \
        --repo "$GITHUB_USER/$REPO_NAME" \
        --title "Test: Project integration" \
        --body "This is a test issue to verify project integration. It should automatically appear in the project board." \
        --label "documentation"
    
    echo
    echo -e "${GREEN}✓ Test issue created${NC}"
    echo
    echo "Check your project board in a few seconds:"
    echo "  https://github.com/users/$GITHUB_USER/projects/$PROJECT_NUMBER"
fi

# Summary
echo
echo "================================"
echo "✅ Setup Complete!"
echo "================================"
echo
echo "Project URL: https://github.com/users/$GITHUB_USER/projects/$PROJECT_NUMBER"
echo "Repository: https://github.com/$GITHUB_USER/$REPO_NAME"
echo
echo "Next steps:"
echo "1. Commit the updated workflow file:"
echo "   git add $WORKFLOW_FILE"
echo "   git commit -m 'Configure GitHub Project integration'"
echo "   git push"
echo
echo "2. Configure project automations:"
echo "   - Open project → ⚙️ → Workflows"
echo "   - Enable 'Auto-add to project'"
echo "   - Enable 'Item closed'"
echo
echo "3. Bulk sync existing issues:"
echo "   - Go to Actions tab"
echo "   - Run 'Sync Issues and PRs to Project'"
echo "   - Check 'Sync all existing open issues/PRs'"
echo
echo "4. Read the docs:"
echo "   docs/GITHUB_PROJECT_INTEGRATION.md"
echo
echo "🎉 Happy project management!"
