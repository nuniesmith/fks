# GitHub Project Setup Script for FKS (PowerShell)
# This script helps configure GitHub Project integration

$ErrorActionPreference = "Stop"

Write-Host "🚀 FKS GitHub Project Setup" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan
Write-Host ""

# Check if gh CLI is installed
if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    Write-Host "✗ GitHub CLI (gh) is not installed" -ForegroundColor Red
    Write-Host "  Install from: https://cli.github.com/" -ForegroundColor Yellow
    exit 1
}

Write-Host "✓ GitHub CLI found" -ForegroundColor Green

# Check if logged in
try {
    gh auth status 2>&1 | Out-Null
    Write-Host "✓ Authenticated with GitHub" -ForegroundColor Green
} catch {
    Write-Host "! Not logged in to GitHub" -ForegroundColor Yellow
    Write-Host "  Running: gh auth login" -ForegroundColor Yellow
    gh auth login
}

Write-Host ""

# Get user info
$GITHUB_USER = gh api user --jq '.login'
Write-Host "Logged in as: $GITHUB_USER" -ForegroundColor Cyan
Write-Host ""

# Prompt for project name
$PROJECT_NAME = Read-Host "Enter project name (default: FKS Development)"
if ([string]::IsNullOrWhiteSpace($PROJECT_NAME)) {
    $PROJECT_NAME = "FKS Development"
}

# Prompt for project type
Write-Host ""
Write-Host "Select project type:" -ForegroundColor Cyan
Write-Host "  1) Board (Kanban-style)"
Write-Host "  2) Table (Spreadsheet-style)"
Write-Host "  3) Roadmap (Timeline view)"
$PROJECT_TYPE = Read-Host "Choice (1-3, default: 1)"
if ([string]::IsNullOrWhiteSpace($PROJECT_TYPE)) {
    $PROJECT_TYPE = "1"
}

$TEMPLATE = switch ($PROJECT_TYPE) {
    "1" { "Board" }
    "2" { "Table" }
    "3" { "Roadmap" }
    default { "Board" }
}

Write-Host ""
Write-Host "Creating project: '$PROJECT_NAME' with template: $TEMPLATE" -ForegroundColor Cyan

# Provide instructions for manual creation
Write-Host ""
Write-Host "! GitHub CLI doesn't support project creation yet" -ForegroundColor Yellow
Write-Host ""
Write-Host "Please create the project manually:" -ForegroundColor Yellow
Write-Host "1. Go to: https://github.com/$GITHUB_USER?tab=projects"
Write-Host "2. Click 'New project'"
Write-Host "3. Choose '$TEMPLATE' template"
Write-Host "4. Name it: '$PROJECT_NAME'"
Write-Host "5. Click 'Create project'"
Write-Host ""
Read-Host "Press Enter when you've created the project"

# Get project number
Write-Host ""
Write-Host "Find your project number from the URL:" -ForegroundColor Cyan
Write-Host "  https://github.com/users/$GITHUB_USER/projects/NUMBER" -ForegroundColor Yellow
Write-Host ""
$PROJECT_NUMBER = Read-Host "Enter your project number"

if ([string]::IsNullOrWhiteSpace($PROJECT_NUMBER)) {
    Write-Host "✗ Project number is required" -ForegroundColor Red
    exit 1
}

Write-Host "✓ Project number: $PROJECT_NUMBER" -ForegroundColor Green

# Update workflow file
$WORKFLOW_FILE = ".github\workflows\sync-to-project.yml"

if (-not (Test-Path $WORKFLOW_FILE)) {
    Write-Host "✗ Workflow file not found: $WORKFLOW_FILE" -ForegroundColor Red
    Write-Host "  Make sure you're in the FKS repository root" -ForegroundColor Yellow
    exit 1
}

Write-Host ""
Write-Host "Updating workflow file with project number..." -ForegroundColor Cyan

# Backup original
Copy-Item $WORKFLOW_FILE "$WORKFLOW_FILE.bak" -Force

# Update project number
$content = Get-Content $WORKFLOW_FILE -Raw
$content = $content -replace 'PROJECT_NUMBER:\s*\d+', "PROJECT_NUMBER: $PROJECT_NUMBER"
Set-Content -Path $WORKFLOW_FILE -Value $content

Write-Host "✓ Updated $WORKFLOW_FILE" -ForegroundColor Green
Write-Host "  (Backup saved as $WORKFLOW_FILE.bak)" -ForegroundColor Gray

# Link repository to project
Write-Host ""
Write-Host "Linking repository to project..." -ForegroundColor Cyan
$REPO_NAME = Read-Host "Repository name (default: fks)"
if ([string]::IsNullOrWhiteSpace($REPO_NAME)) {
    $REPO_NAME = "fks"
}

Write-Host ""
Write-Host "To link the repository to your project:" -ForegroundColor Yellow
Write-Host "1. Go to: https://github.com/$GITHUB_USER/$REPO_NAME"
Write-Host "2. Click 'Projects' tab"
Write-Host "3. Click 'Link a project'"
Write-Host "4. Select '$PROJECT_NAME'"
Write-Host ""
Read-Host "Press Enter when you've linked the repository"

# Test the setup
Write-Host ""
Write-Host "Testing the setup..." -ForegroundColor Cyan
Write-Host ""
$CREATE_TEST = Read-Host "Create a test issue? (y/n)"

if ($CREATE_TEST -eq "y") {
    Write-Host "Creating test issue..." -ForegroundColor Cyan
    gh issue create `
        --repo "$GITHUB_USER/$REPO_NAME" `
        --title "Test: Project integration" `
        --body "This is a test issue to verify project integration. It should automatically appear in the project board." `
        --label "documentation"
    
    Write-Host ""
    Write-Host "✓ Test issue created" -ForegroundColor Green
    Write-Host ""
    Write-Host "Check your project board in a few seconds:" -ForegroundColor Cyan
    Write-Host "  https://github.com/users/$GITHUB_USER/projects/$PROJECT_NUMBER" -ForegroundColor Yellow
}

# Summary
Write-Host ""
Write-Host "================================" -ForegroundColor Cyan
Write-Host "✅ Setup Complete!" -ForegroundColor Green
Write-Host "================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Project URL: https://github.com/users/$GITHUB_USER/projects/$PROJECT_NUMBER" -ForegroundColor Yellow
Write-Host "Repository: https://github.com/$GITHUB_USER/$REPO_NAME" -ForegroundColor Yellow
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "1. Commit the updated workflow file:"
Write-Host "   git add $WORKFLOW_FILE"
Write-Host "   git commit -m 'Configure GitHub Project integration'"
Write-Host "   git push"
Write-Host ""
Write-Host "2. Configure project automations:"
Write-Host "   - Open project → ⚙️ → Workflows"
Write-Host "   - Enable 'Auto-add to project'"
Write-Host "   - Enable 'Item closed'"
Write-Host ""
Write-Host "3. Bulk sync existing issues:"
Write-Host "   - Go to Actions tab"
Write-Host "   - Run 'Sync Issues and PRs to Project'"
Write-Host "   - Check 'Sync all existing open issues/PRs'"
Write-Host ""
Write-Host "4. Read the docs:"
Write-Host "   docs\GITHUB_PROJECT_INTEGRATION.md"
Write-Host ""
Write-Host "🎉 Happy project management!" -ForegroundColor Green
