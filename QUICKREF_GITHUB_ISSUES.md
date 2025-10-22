# Quick Start: Import GitHub Issues

## 1. Install & Authenticate GitHub CLI

```bash
# Install (Ubuntu/WSL)
sudo apt install gh

# Authenticate
gh auth login
```

## 2. Run Import Script

```bash
# Make executable (if needed)
chmod +x scripts/import_github_issues.sh

# Run import
./scripts/import_github_issues.sh
```

## 3. Verify Import

```bash
# List all issues
gh issue list --limit 50

# View Phase 1 issues
gh issue list --milestone "Phase 1: Immediate Fixes"
```

## 4. Start Working

```bash
# View issue details
gh issue view 1

# Assign to yourself and create branch
gh issue edit 1 --add-assignee @me
gh issue develop 1 --checkout

# Close when done
gh issue close 1 --comment "Completed all verification items"
```

## What Gets Created

- **7 Milestones**: One for each development phase
- **19 Issues**: Complete with hour-by-hour breakdowns
- **Labels**: impact, urgency, effort, phase

## Issue Breakdown by Phase

- **Phase 1** (3 issues): Security, Import Fixes, Code Cleanup
- **Phase 2** (4 issues): Celery, RAG, Web UI, Backtesting
- **Phase 3** (2 issues): Testing, CI/CD
- **Phase 4** (2 issues): Documentation
- **Phase 5** (2 issues): Local Dev, Production
- **Phase 6** (3 issues): Performance, Maintenance, Code Quality
- **Phase 7** (3 issues): WebSocket, Exchanges, Advanced Features

**Total**: ~120 hours across 14-22 weeks

---

**Full Guide**: `docs/GITHUB_ISSUES_IMPORT.md`
