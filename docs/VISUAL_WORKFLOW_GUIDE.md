# FKS Project Management - Visual Workflow Guide

## 📊 System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Developer Workflow                          │
└─────────────────────────────────────────────────────────────────┘
                                ↓
        ┌───────────────────────┴───────────────────────┐
        │                                                │
        ↓                                                ↓
┌─────────────┐                                  ┌─────────────┐
│   Morning   │                                  │  End of Day │
│  Check-in   │                                  │   Update    │
│  (5-10 min) │                                  │   (5 min)   │
└─────────────┘                                  └─────────────┘
        ↓                                                ↓
   [Read PROJECT_STATUS.md]                      [Update issues]
   [Check GitHub board]                          [Move cards]
   [Pick 1-3 tasks]                              [Note blockers]
        ↓                                                ↓
        └────────────────┬───────────────────────────────┘
                         ↓
                  ┌─────────────┐
                  │   Weekly    │
                  │   Review    │
                  │ (15-30 min) │
                  └─────────────┘
                         ↓
                  [Run analyzer]
                  [Fill template]
                  [Reprioritize]
```

## 🔄 GitHub Actions Automation Flow

```
┌──────────────┐
│ Code Change  │ (Push to main/develop)
└──────────────┘
       ↓
┌──────────────────────────────────────────────┐
│     GitHub Actions Workflow Triggered         │
│  (project-health-check.yml)                  │
└──────────────────────────────────────────────┘
       ↓
   ┌───┴───┬────────┬────────┬─────────┐
   ↓       ↓        ↓        ↓         ↓
[Tests] [Lint] [Security] [Type] [Analyze]
   ↓       ↓        ↓        ↓         ↓
   └───┬───┴────────┴────────┴─────────┘
       ↓
┌──────────────────────────┐
│  Update Status Script    │
│  (update_status.py)      │
└──────────────────────────┘
       ↓
┌──────────────────────────┐
│  PROJECT_STATUS.md       │
│  Updated with metrics    │
└──────────────────────────┘
       ↓
┌──────────────────────────┐
│  PR Comment Posted       │
│  (if PR triggered)       │
└──────────────────────────┘
```

## 🎯 Prioritization Decision Tree

```
                    New Task
                       ↓
            ┌──────────┴──────────┐
            │ Blocks other work?  │
            └──────────┬──────────┘
                  Yes  ↓  No
                       ↓
            ┌──────────┴──────────┐
            │ Security/Data risk? │
            └──────────┬──────────┘
                  Yes  ↓  No
                       ↓
            ┌──────────┴──────────┐
            │ Enables revenue?    │
            └──────────┬──────────┘
                  Yes  ↓  No
                       ↓
            ┌──────────┴──────────┐
            │ High impact + Low   │
            │ effort?             │
            └──────────┬──────────┘
                  Yes  ↓  No
                       ↓
    ┌─────────────────┼─────────────────┐
    ↓                 ↓                 ↓
  🔴 P0            🟡 P1             🟢 P2/P3
 Critical          High             Medium/Low
 (Do Now)      (This Week)          (Backlog)
    ↓                 ↓                 ↓
effort:low      effort:medium      effort:high
    ↓                 ↓                 ↓
[Start Today]  [Schedule]         [Plan & Break]
```

## 📋 Issue Lifecycle

```
┌──────────────┐
│ Issue Created│ (Via template or auto)
└──────────────┘
       ↓
       ├─ Label: 🔴 critical / 🟡 high / 🟢 medium / ⚪ low
       ├─ Label: ✨ feature / 🐛 bug / 🧹 tech-debt
       └─ Label: effort:low / medium / high
       ↓
┌──────────────────┐
│ 📥 Backlog       │ (Auto-added by Project board)
└──────────────────┘
       ↓ (During planning)
┌──────────────────┐
│ 🎯 To-Do         │ (Selected for current week)
└──────────────────┘
       ↓ (When work starts)
┌──────────────────┐
│ 🚧 In Progress   │ (Max 3 at a time)
└──────────────────┘
       ↓ (PR created)
┌──────────────────┐
│ 🔍 Review        │ (CI checks run)
└──────────────────┘
       ↓ (PR merged with "Closes #X")
┌──────────────────┐
│ ✅ Done          │ (Auto-closed)
└──────────────────┘
```

## 📊 Weekly Review Process

```
┌─────────────────────────────────────────┐
│           Friday EOD / Monday AM        │
└─────────────────────────────────────────┘
                    ↓
        ┌───────────┴───────────┐
        │  Copy Review Template │
        └───────────┬───────────┘
                    ↓
        ┌───────────┴───────────┐
        │  Run Analyzer Script  │
        │  (analyze_project.py) │
        └───────────┬───────────┘
                    ↓
        ┌───────────┴───────────┐
        │  Fill Template Sections│
        │  - Metrics            │
        │  - Completed tasks    │
        │  - Blockers           │
        │  - Decisions          │
        │  - Learnings          │
        └───────────┬───────────┘
                    ↓
        ┌───────────┴───────────┐
        │  Analyze Trends       │
        │  - Test pass rate ↑/↓ │
        │  - Velocity ↑/↓       │
        │  - Tech debt ↑/↓      │
        └───────────┬───────────┘
                    ↓
        ┌───────────┴───────────┐
        │  Reprioritize         │
        │  - Bump urgent items  │
        │  - Push down low-pri  │
        │  - Update board       │
        └───────────┬───────────┘
                    ↓
        ┌───────────┴───────────┐
        │  Set Next Week Goals  │
        │  (Top 3-5 priorities) │
        └───────────┬───────────┘
                    ↓
        ┌───────────┴───────────┐
        │  Commit Review to Git │
        └───────────────────────┘
```

## 🔧 Daily Task Workflow

```
Morning
   ↓
[Check PROJECT_STATUS.md]
   ↓
[Pick P0/P1 task from board]
   ↓
[Move to "In Progress"]
   ↓
[Create branch: feature/issue-123]
   ↓
   │
Work Loop ─────────────────┐
   │                       │
   ↓                       │
[Make changes]             │
   ↓                       │
[Run tests: pytest]        │
   ↓                       │
[Tests fail?] ─Yes→ Fix ───┘
   ↓ No
[Commit with issue ref]
   │ (e.g., "Fix #123: ...")
   ↓
[Update issue comment]
   │ (Progress, next steps)
   ↓
[More work?] ─Yes→ Continue loop
   ↓ No
[Push branch]
   ↓
[Create PR]
   ↓
[CI checks run]
   ↓
[Checks pass?] ─No→ Fix & push
   ↓ Yes
[Merge PR]
   ↓
[Issue auto-closes]
   ↓
[Card moves to "Done"]
   ↓
End of Day
```

## 📈 Metrics Dashboard (Weekly Trend)

```
Test Pass Rate (Target: 100%)
Week 1:  ████████░░░░░░░░░░░░  41% (14/34)
Week 2:  ████████████░░░░░░░░  59% (20/34) ↑
Week 3:  ████████████████░░░░  79% (27/34) ↑
Week 4:  ████████████████████ 100% (34/34) ✓

Technical Debt (Target: 0)
Legacy Imports:  ████████████████████░░░░  20 files
                 ████████████░░░░░░░░░░░░  12 files ↓
                 ████░░░░░░░░░░░░░░░░░░░░   4 files ↓
                 ░░░░░░░░░░░░░░░░░░░░░░░░   0 files ✓

Issues Closed per Week (Velocity)
Week 1:  ████████  8 issues
Week 2:  ██████    6 issues
Week 3:  ██████████ 10 issues ↑
Week 4:  ████████  8 issues
```

## 🎯 Priority Label Guide

```
┌─────────────────────────────────────────────────────┐
│                  Priority Labels                    │
├─────────────────────────────────────────────────────┤
│ 🔴 Critical  │ Blocks work, security, data loss    │
│              │ Action: Drop everything, fix now    │
├─────────────────────────────────────────────────────┤
│ 🟡 High      │ Core feature, high business value   │
│              │ Action: Schedule this week          │
├─────────────────────────────────────────────────────┤
│ 🟢 Medium    │ Improvement, moderate value         │
│              │ Action: Next sprint or backlog      │
├─────────────────────────────────────────────────────┤
│ ⚪ Low       │ Nice-to-have, low priority          │
│              │ Action: Backlog, do if time permits │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│                   Effort Labels                     │
├─────────────────────────────────────────────────────┤
│ effort:low    │ < 1 day    │ Quick wins          │
│ effort:medium │ 1-3 days   │ Normal tasks        │
│ effort:high   │ > 3 days   │ Break into subtasks │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│                   Type Labels                       │
├─────────────────────────────────────────────────────┤
│ ✨ feature    │ New functionality or enhancement   │
│ 🐛 bug        │ Something not working correctly    │
│ 🧹 tech-debt  │ Refactoring, cleanup, optimization │
│ 🔒 security   │ Security vulnerability or hardening│
│ 🧪 tests      │ Testing related (unit, integration)│
│ 📚 documentation │ Docs, comments, README updates  │
└─────────────────────────────────────────────────────┘
```

## 🔄 Reprioritization Workflow

```
                    Weekly Review
                          ↓
            ┌─────────────┴─────────────┐
            │  Run Analyzer Script      │
            │  (analyze_project.py)     │
            └─────────────┬─────────────┘
                          ↓
            ┌─────────────┴─────────────┐
            │  Review Metrics           │
            │  - New issues detected?   │
            │  - Tests failing?         │
            │  - Security vulns?        │
            └─────────────┬─────────────┘
                          ↓
            ┌─────────────┴─────────────┐
            │  Identify Changes         │
            │  - What's now blocking?   │
            │  - What's less urgent?    │
            └─────────────┬─────────────┘
                          ↓
        ┌─────────────────┼─────────────────┐
        ↓                 ↓                 ↓
   [Bump Up]          [Bump Down]      [Keep Same]
   New blocker        Lower impact      On track
        ↓                 ↓                 ↓
   Update label      Update label      No change
   🟢 → 🔴           🟡 → 🟢            ✓
        ↓                 ↓                 ↓
   Move to         Move to            Stay in
   "To-Do"         "Backlog"          current column
        ↓                 ↓                 ↓
        └─────────────────┼─────────────────┘
                          ↓
            ┌─────────────┴─────────────┐
            │  Update PROJECT_STATUS.md │
            │  with new priorities      │
            └─────────────┬─────────────┘
                          ↓
            ┌─────────────┴─────────────┐
            │  Document in Weekly Review│
            │  (Decisions + Rationale)  │
            └───────────────────────────┘
```

## 🎬 Quick Reference Commands

```bash
# Daily
make up                              # Start services
make logs                            # View logs
pytest tests/ -v                     # Run tests
make lint                            # Check code quality

# Weekly
python scripts/analyze_project.py --summary   # Project health
git add docs/reviews/$(date).md               # Commit review
git push                                      # Trigger Actions

# Setup (One-time)
gh auth login                        # Authenticate
python scripts/setup_github_project.py        # Create issues/labels
# Then manually create Project board on GitHub
```

## 📚 File Location Quick Reference

```
fks/
├── PROJECT_STATUS.md              ← Main dashboard (daily check)
├── PROJECT_MANAGEMENT_SUMMARY.md  ← System overview (read once)
├── SETUP_CHECKLIST.md             ← Setup guide (one-time)
├── .github/
│   ├── README.md                  ← Full documentation (reference)
│   ├── WEEKLY_REVIEW_TEMPLATE.md  ← Copy for reviews
│   ├── workflows/
│   │   └── project-health-check.yml  ← GitHub Actions
│   ├── scripts/
│   │   └── update_status.py       ← Auto-update status
│   └── ISSUE_TEMPLATE/
│       ├── critical-bug.yml       ← Bug template
│       ├── feature.yml            ← Feature template
│       └── technical-debt.yml     ← Debt template
├── scripts/
│   ├── analyze_project.py         ← Metrics generator
│   └── setup_github_project.py    ← One-time setup
└── docs/
    └── reviews/                   ← Weekly review history
        ├── 2025-10-17.md
        ├── 2025-10-24.md
        └── ...
```

---

**Visual Guide Version**: 1.0  
**Last Updated**: 2025-10-17  
**For**: FKS Trading Platform Project Management System
