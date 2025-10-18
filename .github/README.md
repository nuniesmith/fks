# FKS Trading Platform - Project Management System

## Overview

This directory contains the **dynamic project management and prioritization system** for FKS Trading Platform. It ensures you're always working on the highest-impact tasks through automated health checks, prioritization frameworks, and weekly reviews.

## 🎯 Core Philosophy

**Decision Rule**: Before starting any task, ask:
1. Does this unblock revenue/user value? (e.g., trading signals, RAG intelligence)
2. Does this reduce risk? (e.g., security, data loss)
3. Is this blocking other tasks?
4. What's the effort vs. impact ratio?

If a task doesn't meet these criteria, backlog it.

## 📁 System Components

### 1. PROJECT_STATUS.md
**The single source of truth** for project health and priorities.

- **Updated**: Automatically by GitHub Actions, manually during reviews
- **Contents**:
  - Current sprint goals (weekly)
  - Health metrics (tests, coverage, debt)
  - Critical issues with fix plans
  - Detailed task breakdowns
  - Decision framework

**When to use**: Daily check-in, before starting work, during planning

### 2. GitHub Actions (.github/workflows/)

#### CI/CD Pipeline
**Complete automation for build, test, lint, and deploy**

Three main workflows:
- **`ci-cd.yml`**: Full CI/CD pipeline (runs on every push/PR)
- **`weekly-health-check.yml`**: Automated weekly analysis with auto-commit
- **`project-health-check.yml`**: Quick health check for PRs

**Documentation**:
- 📚 [Workflows README](workflows/README.md) - Detailed workflow documentation
- 🚀 [Quick Start Guide](CI_CD_QUICKSTART.md) - Get started in 5 minutes
- 🔐 [Secrets Setup](SECRETS_SETUP.md) - Configure GitHub secrets
- 🛡️ [Branch Protection](BRANCH_PROTECTION.md) - Protect main/develop branches

**Key Features**:
- ✅ Test failures block PR merge
- ✅ Coverage reports posted to PRs
- ✅ Security scanning (pip-audit, bandit)
- ✅ Auto-commit PROJECT_STATUS.md updates
- ✅ Discord notifications
- ✅ Docker image builds
- ✅ Auto-deploy to staging/production

**Artifacts**: Download from Actions tab for detailed reports

### 3. GitHub Issues Templates

#### Critical Bug (.github/ISSUE_TEMPLATE/critical-bug.yml)
Use for: Test failures, security vulnerabilities, build errors
Labels: 🔴 critical, bug

#### Feature Implementation (.github/ISSUE_TEMPLATE/feature.yml)
Use for: New features, completing stubs (e.g., Celery tasks)
Labels: ✨ feature, enhancement

#### Technical Debt (.github/ISSUE_TEMPLATE/technical-debt.yml)
Use for: Code cleanup, refactoring, legacy removal
Labels: 🧹 tech-debt, refactoring

### 4. Scripts (scripts/)

#### `analyze_project.py`
**Purpose**: Generate comprehensive project metrics

```bash
# Full analysis with JSON output
python scripts/analyze_project.py --output metrics.json

# With human-readable summary
python scripts/analyze_project.py --summary

# Quick stats only
python scripts/analyze_project.py
```

**Output**:
- File statistics (total, by type, empty/small files)
- Code quality metrics (functions, classes, lines)
- Test status (pass rate, coverage)
- Import analysis (legacy imports, framework usage)
- Technical debt markers (TODO, FIXME, HACK)
- Git status (branch, uncommitted changes)

**Recommended**: Run weekly or after major changes

#### `setup_github_project.py`
**Purpose**: Initialize GitHub Project board and labels

```bash
# First time setup
python scripts/setup_github_project.py

# Custom owner/repo
python scripts/setup_github_project.py --owner yourname --repo yourrepo
```

**What it does**:
1. Creates standardized labels (🔴 critical, ✨ feature, etc.)
2. Creates initial issues from PROJECT_STATUS.md priorities
3. Provides instructions for Project board setup

**Run once**, then manage issues through GitHub UI

### 5. Weekly Review Template (.github/WEEKLY_REVIEW_TEMPLATE.md)

**Purpose**: Structured weekly review process

**Process**:
1. Copy template to new file: `docs/reviews/2025-10-17.md`
2. Fill in metrics (use `analyze_project.py --summary`)
3. List completed tasks, blockers, decisions
4. Set next week priorities
5. Identify learnings and process improvements
6. Commit to repo for historical record

**Time**: 15-30 minutes, Friday EOD or Monday morning

## 🚀 Getting Started

### Initial Setup (One-Time)

1. **Install GitHub CLI** (for project setup):
   ```bash
   # Windows (PowerShell)
   winget install GitHub.cli
   
   # Authenticate
   gh auth login
   ```

2. **Setup GitHub Project**:
   ```bash
   python scripts/setup_github_project.py
   ```
   
   This creates:
   - ✅ Standard labels
   - ✅ Initial issues from PROJECT_STATUS.md
   - ⏳ Instructions for Project board (manual step)

3. **Create Project Board** (Manual):
   - Visit: https://github.com/nuniesmith/fks/projects/new
   - Select: "Board" template
   - Create columns:
     - 📥 Backlog
     - 🎯 To-Do (This Week)
     - 🚧 In Progress
     - 🔍 Review
     - ✅ Done
   - Add automation: Auto-move issues based on status

4. **Configure CI/CD Pipeline**:
   ```bash
   # Enable GitHub Actions (if not already enabled)
   # Go to: Settings → Actions → General → Allow all actions
   
   # Configure secrets (minimum: Discord webhook)
   gh secret set DISCORD_WEBHOOK -b "YOUR_WEBHOOK_URL"
   
   # Optional: Full setup for Docker and deployment
   # See: .github/SECRETS_SETUP.md for complete guide
   ```
   
   **Quick Start**: [CI/CD Quick Start Guide](CI_CD_QUICKSTART.md) (5 minutes)

5. **Set Up Branch Protection**:
   ```bash
   # Recommended: Protect main and develop branches
   # Requires: test, lint, security checks to pass
   # See: .github/BRANCH_PROTECTION.md for setup guide
   ```

6. **Set Up Weekly Review Reminder**:
   - Option A: Calendar reminder (Friday 4 PM)
   - Option B: GitHub Action (already scheduled for Mondays)

### Daily Workflow

#### Morning (5-10 minutes)
1. **Check PROJECT_STATUS.md**:
   - What's in "Priority 1: Critical Blockers"?
   - Any new issues from health check?

2. **Review GitHub Project Board**:
   - Move yesterday's work to "Done"
   - Pick 1-3 tasks from "To-Do" for today
   - Move selected tasks to "In Progress"

3. **Check Dependencies**:
   - Are any tasks blocked?
   - Update blockers in issue comments

#### During Work
1. **Update issue as you work**:
   ```markdown
   **Progress Update**:
   - [x] Step 1 complete (2 hours)
   - [ ] Step 2 in progress
   - [ ] Step 3 blocked - waiting on #42
   ```

2. **Run tests frequently**:
   ```bash
   # After any code change
   pytest tests/ -v
   
   # Before committing
   make lint
   pytest tests/ --cov=src
   ```

3. **Commit with issue references**:
   ```bash
   git commit -m "Fix import errors in trading module

   - Update imports to use framework.config.constants
   - Remove legacy config module references
   - Add unit tests for signal generator
   
   Closes #1"
   ```

#### End of Day (5 minutes)
1. **Update issue status**:
   - Comment with today's progress
   - Update checkboxes in issue body

2. **Move cards on board**:
   - Completed → "Done"
   - In progress → Stay in "In Progress"
   - Blocked → Note blocker in comments

### Weekly Review (15-30 minutes)

**Friday EOD or Monday morning**

1. **Copy template**:
   ```bash
   mkdir -p docs/reviews
   cp .github/WEEKLY_REVIEW_TEMPLATE.md docs/reviews/2025-10-17.md
   ```

2. **Run analyzer**:
   ```bash
   python scripts/analyze_project.py --summary > analyzer_output.txt
   ```

3. **Fill in template**:
   - Paste analyzer output in "Health Dashboard Summary"
   - List completed tasks (check GitHub "Done" column)
   - Document blockers and resolutions
   - Record decisions made
   - Set next week priorities (top 3-5 from backlog)

4. **Reprioritize**:
   - Review analyzer output for new issues
   - Bump up urgent items (security, blockers)
   - Push down lower-impact items
   - Update PROJECT_STATUS.md if major changes

5. **Commit review**:
   ```bash
   git add docs/reviews/2025-10-17.md
   git commit -m "Weekly review for Oct 17, 2025"
   git push
   ```

## 📊 Prioritization Framework

### Labels for Prioritization

**Impact** (Label colors):
- 🔴 **Critical** (Red): Blocks development/deployment
- 🟡 **High** (Yellow): Core feature, high value
- 🟢 **Medium** (Green): Improvement, moderate value
- ⚪ **Low** (Purple): Nice to have

**Effort** (Labels):
- `effort:low` - < 1 day
- `effort:medium` - 1-3 days
- `effort:high` - > 3 days

**Priority Matrix**:
```
High Impact + High Urgency + Low Effort = DO FIRST
High Impact + Low Urgency + Medium Effort = Schedule this week
Low Impact + Low Urgency + High Effort = BACKLOG
```

### Reprioritization Triggers

**Bump to P0 (Critical) if**:
- Blocks other work
- Security vulnerability
- Data loss risk
- All tests failing

**Bump to P1 (High) if**:
- Core feature for revenue
- Many users affected
- Technical debt causing bugs

**Bump down if**:
- Lower impact than initially thought
- Dependencies not ready
- Scope creep detected

## 🔄 Automation Features

### What Gets Auto-Updated

1. **PROJECT_STATUS.md**:
   - Test pass rate
   - Coverage percentage
   - Security vulnerability count
   - Last updated date

2. **GitHub Issues**:
   - Auto-close when PR merged with "Closes #X"
   - Auto-label based on file paths changed
   - Auto-comment with test results on PRs

3. **Project Board**:
   - New issues → Backlog
   - Issues assigned → To-Do
   - PR opened → Review
   - PR merged → Done

### Manual Updates Needed

1. **Sprint goals** in PROJECT_STATUS.md
2. **Task descriptions** in issues
3. **Weekly review** completion
4. **Reprioritization** based on learnings

## 🎯 Success Metrics

Track these weekly in reviews:

### Code Quality
- **Test Pass Rate**: 41% → 100% (target)
- **Coverage**: Track trend, aim for 80%+
- **Legacy Imports**: 20+ files → 0 files

### Velocity
- **Issues Closed/Week**: Track trend
- **Commit Frequency**: Daily commits ideal
- **Blocker Time**: Minimize days blocked

### Process
- **Weekly Review Completion**: 100%
- **Reprioritization Frequency**: Weekly minimum
- **Decision Documentation**: All major decisions recorded

## 🆘 Troubleshooting

### "GitHub Actions failing"
1. Check logs in Actions tab
2. Common causes:
   - Test failures (fix tests first)
   - Missing dependencies (update requirements.txt)
   - Timeout (increase in workflow YAML)

### "Analyzer script errors"
1. Ensure Python 3.11+:
   ```bash
   python --version
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run with verbose:
   ```bash
   python scripts/analyze_project.py --summary
   ```

### "Too many issues in backlog"
1. **Filter ruthlessly**: Archive low-priority items
2. **Combine related**: Merge similar issues
3. **Set milestones**: Group by release goals
4. **Use labels**: Filter by label on project board

### "Stuck on a task > 2 hours"
1. **Break it down**: Create subtasks in issue
2. **Ask for help**: Comment with specific question
3. **Timebox it**: Set 4-hour max, then reassess
4. **Deprioritize**: If blocked, move on

## 📚 Additional Resources

- [GitHub Projects Docs](https://docs.github.com/en/issues/planning-and-tracking-with-projects)
- [GitHub Actions Docs](https://docs.github.com/en/actions)
- [PROJECT_STATUS.md](../PROJECT_STATUS.md) - Current priorities
- [ARCHITECTURE.md](../docs/ARCHITECTURE.md) - System design
- [copilot-instructions.md](copilot-instructions.md) - AI coding guide

## 🤝 Contributing

For solo development, this system is your "second brain". For team growth:

1. **Onboarding**: Share PROJECT_STATUS.md and this README
2. **Rituals**: Weekly reviews, daily standups (async via issues)
3. **Documentation**: Keep decisions in issues/reviews
4. **Automation**: Extend GitHub Actions as needed

---

**Maintained by**: @nuniesmith  
**Last updated**: 2025-10-17  
**Questions?**: Open an issue with label `📚 documentation`
