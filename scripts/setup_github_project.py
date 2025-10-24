#!/usr/bin/env python3
"""
Setup GitHub Project board with automated Kanban columns.
Requires: gh CLI tool installed and authenticated
"""

import json
import subprocess
import sys
from typing import Dict, List


class GitHubProjectSetup:
    """Configure GitHub Projects for FKS Trading Platform."""
    
    def __init__(self, owner: str, repo: str):
        self.owner = owner
        self.repo = repo
        self.project_name = "FKS Trading Platform"
        
    def check_gh_cli(self) -> bool:
        """Check if GitHub CLI is installed and authenticated."""
        try:
            result = subprocess.run(
                ["gh", "auth", "status"],
                capture_output=True,
                text=True
            )
            return result.returncode == 0
        except FileNotFoundError:
            print("❌ GitHub CLI (gh) not found. Install from: https://cli.github.com/")
            return False
    
    def create_labels(self):
        """Create standard labels for prioritization."""
        labels = [
            {"name": "🔴 critical", "color": "d73a4a", "description": "Blocks development or deployment"},
            {"name": "🟡 high", "color": "fbca04", "description": "Important, but not blocking"},
            {"name": "🟢 medium", "color": "0e8a16", "description": "Normal priority"},
            {"name": "⚪ low", "color": "d4c5f9", "description": "Nice to have"},
            {"name": "✨ feature", "color": "a2eeef", "description": "New feature or enhancement"},
            {"name": "🐛 bug", "color": "d73a4a", "description": "Something isn't working"},
            {"name": "🧹 tech-debt", "color": "e99695", "description": "Technical debt or refactoring"},
            {"name": "📚 documentation", "color": "0075ca", "description": "Documentation updates"},
            {"name": "🧪 tests", "color": "5319e7", "description": "Testing related"},
            {"name": "🔒 security", "color": "b60205", "description": "Security issue"},
            {"name": "⏸️ blocked", "color": "ffffff", "description": "Blocked by dependencies"},
            {"name": "effort:low", "color": "c5def5", "description": "< 1 day"},
            {"name": "effort:medium", "color": "bfd4f2", "description": "1-3 days"},
            {"name": "effort:high", "color": "7057ff", "description": "> 3 days"},
            {"name": "phase:1-immediate", "color": "d73a4a", "description": "Phase 1: Immediate Fixes"},
            {"name": "phase:2-core", "color": "fbca04", "description": "Phase 2: Core Development"},
            {"name": "phase:3-testing", "color": "0e8a16", "description": "Phase 3: Testing & QA"},
            {"name": "phase:4-docs", "color": "0075ca", "description": "Phase 4: Documentation"},
            {"name": "phase:5-deploy", "color": "1d76db", "description": "Phase 5: Deployment"},
            {"name": "phase:6-optimize", "color": "5319e7", "description": "Phase 6: Optimization"},
            {"name": "phase:7-future", "color": "d4c5f9", "description": "Phase 7: Future Features"},
            {"name": "⚙️ automation", "color": "0052cc", "description": "CI/CD automation"},
            {"name": "🚀 deployment", "color": "1d76db", "description": "Deployment related"},
            {"name": "⚡ performance", "color": "5319e7", "description": "Performance optimization"},
        ]
        
        print("📝 Creating labels...")
        for label in labels:
            cmd = [
                "gh", "label", "create",
                label["name"],
                "--color", label["color"],
                "--description", label["description"],
                "--repo", f"{self.owner}/{self.repo}",
                "--force"  # Update if exists
            ]
            subprocess.run(cmd, capture_output=True)
        print("✅ Labels created")
    
    def create_initial_issues(self):
        """Create initial issues from PROJECT_STATUS.md priorities."""
        issues = [
            {
                "title": "[CRITICAL] Fix Import Errors - Unblock 20 Failing Tests",
                "body": """## Problem
20 tests failing due to legacy microservices imports (`config`, `shared_python`).

## Impact
- Cannot validate code changes
- Blocks deployment readiness
- Prevents CI/CD pipeline from working

## Solution
1. Create `src/framework/config/constants.py` with trading constants
2. Update imports in affected files:
   - `src/core/database/models.py`
   - `src/trading/backtest/engine.py`
   - `src/trading/signals/generator.py`
   - `src/data/adapters/base.py`
3. Run test suite to verify: `pytest tests/ -v`

## Success Criteria
- [ ] All 34 tests passing
- [ ] No legacy imports remain
- [ ] Coverage report generated

## Effort
Medium (2-3 days)

## References
- See PROJECT_STATUS.md section "Fix Plan: Import Errors"
""",
                "labels": ["🔴 critical", "🐛 bug", "🧪 tests", "effort:medium"]
            },
            {
                "title": "[CRITICAL] Security Hardening - Production-Ready Secrets",
                "body": """## Problem
`.env` file contains placeholder passwords and API keys in plain text.

## Security Risks
- POSTGRES_PASSWORD: `CHANGE_THIS_SECURE_PASSWORD_123!`
- PGADMIN_PASSWORD: `CHANGE_THIS_ADMIN_PASSWORD_456!`
- REDIS_PASSWORD: Empty
- Exposed ports (5432, 6379) without restrictions

## Solution
1. Generate secure secrets (see PROJECT_STATUS.md)
2. Update `.env` (DO NOT COMMIT)
3. Create `.env.example` template
4. Add secrets management docs
5. Update docker-compose.yml for Redis auth

## Success Criteria
- [ ] All secrets generated and stored securely
- [ ] `.env` in `.gitignore`
- [ ] Documentation updated
- [ ] Docker services use auth

## Effort
Low (1 day)

## References
- PROJECT_STATUS.md section "Fix Plan: Security"
- docs/SECURITY_SETUP.md
""",
                "labels": ["🔴 critical", "🔒 security", "effort:low"]
            },
            {
                "title": "[FEATURE] Implement market_data_sync Celery Task",
                "body": """## Feature
Implement `sync_market_data_task` to fetch OHLCV data from Binance.

## Background
All Celery tasks in `src/trading/tasks.py` are currently stubs. This is the foundation task - must be done first.

## Requirements
- Fetch OHLCV data for configured symbols (BTC, ETH, BNB, etc.)
- Store in TimescaleDB hypertable
- Handle rate limiting and errors
- Log progress and metrics

## Acceptance Criteria
- [ ] Task fetches data for all symbols
- [ ] Data stored correctly in DB
- [ ] Unit tests pass
- [ ] Integration test with Binance API
- [ ] Error handling for API failures
- [ ] Rate limiting respected

## Effort
Medium (6-8 hours)

## Dependencies
- Requires #1 (import errors fixed)

## References
- `src/trading/tasks.py`
- Binance API docs
""",
                "labels": ["✨ feature", "🟡 high", "effort:medium"]
            },
            {
                "title": "[DEBT] Remove Legacy Duplicate Files",
                "body": """## Technical Debt
6+ duplicate files exist from microservices migration:

- `trading/backtest/engine.py` vs `legacy_engine.py`
- `trading/signals/generator.py` vs `legacy_generator.py`
- Others in various modules

## Why This Matters
- Causes confusion about which version to use
- Increases maintenance burden
- Risk of editing wrong file

## Solution
1. Identify all legacy files
2. Verify migration complete
3. Remove legacy versions
4. Update any remaining imports

## Effort
Low (<1 day)

## Priority
Medium (P2) - Not blocking, but causes confusion
""",
                "labels": ["🧹 tech-debt", "🟢 medium", "effort:low"]
            },
        ]
        
        print("📋 Creating initial issues...")
        for issue in issues:
            cmd = [
                "gh", "issue", "create",
                "--title", issue["title"],
                "--body", issue["body"],
                "--repo", f"{self.owner}/{self.repo}",
            ]
            for label in issue["labels"]:
                cmd.extend(["--label", label])
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                print(f"  ✅ Created: {issue['title']}")
            else:
                print(f"  ❌ Failed: {issue['title']}")
                print(f"     {result.stderr}")
        
        print("✅ Initial issues created")
    
    def setup_project_board(self):
        """Create GitHub Project with Kanban columns."""
        print("🎯 Setting up Project board...")
        print("   Note: GitHub Projects v2 requires web UI for initial setup")
        print("   Visit: https://github.com/nuniesmith/fks/projects/new")
        print("\n   Recommended columns:")
        print("   1. 📥 Backlog")
        print("   2. 🎯 To-Do (This Week)")
        print("   3. 🚧 In Progress")
        print("   4. 🔍 Review")
        print("   5. ✅ Done")
        print("\n   After creating, issues will auto-populate based on labels.")
    
    def run(self):
        """Run full setup."""
        if not self.check_gh_cli():
            sys.exit(1)
        
        print(f"\n🚀 Setting up GitHub Project for {self.owner}/{self.repo}\n")
        
        self.create_labels()
        self.create_initial_issues()
        self.setup_project_board()
        
        print("\n✅ Setup complete!")
        print(f"\nNext steps:")
        print(f"1. Visit https://github.com/{self.owner}/{self.repo}/issues")
        print(f"2. Create Project board at https://github.com/{self.owner}/{self.repo}/projects/new")
        print(f"3. Run weekly: python scripts/analyze_project.py --summary")
        print(f"4. Review PROJECT_STATUS.md for priorities")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Setup GitHub Project board")
    parser.add_argument("--owner", default="nuniesmith", help="GitHub owner")
    parser.add_argument("--repo", default="fks", help="Repository name")
    args = parser.parse_args()
    
    setup = GitHubProjectSetup(args.owner, args.repo)
    setup.run()
