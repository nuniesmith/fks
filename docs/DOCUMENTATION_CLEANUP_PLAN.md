# Documentation Cleanup & Reorganization Plan

**Date**: October 28, 2025  
**Current Status**: 120 documentation files (needs reduction to ~20-25 essential docs)  
**Goal**: Streamline documentation for AI agent implementation and maintenance

---

## 📊 Current State Analysis

### Statistics
- **Total docs**: 120 files
- **Root-level docs**: 95 files
- **Estimated to keep**: 22-25 core files
- **To archive/delete**: ~95 files (80% reduction)

---

## 🗂️ Reorganization Strategy

### 1. ✅ KEEP & UPDATE (Core Documentation - 15 files)

#### Strategic Planning
- ✅ **AI_STRATEGY_INTEGRATION.md** (35K) - Primary AI implementation roadmap
- ✅ **CRYPTO_REGIME_BACKTESTING.md** (27K) - Regime detection research
- ✅ **TRANSFORMER_TIME_SERIES_ANALYSIS.md** (32K) - ML forecasting guide
- ✅ **PHASE_PLAN_SUMMARY.md** (5.9K) - Overall development roadmap

#### Architecture & System Design
- ✅ **ARCHITECTURE.md** (42K) - Main system architecture
- ✅ **MONOREPO_ARCHITECTURE.md** (16K) - Repository structure
- ⚠️ **MULTI_REPO_ARCHITECTURE.md** - MERGE into MONOREPO_ARCHITECTURE.md (keep monorepo as primary)

#### Operations & Optimization
- ✅ **OPTIMIZATION_GUIDE.md** (9.8K) - Strategy optimization with Optuna
- ✅ **RAG_SETUP_GUIDE.md** (12K) - RAG system configuration
- ✅ **PROJECT_HEALTH_DASHBOARD.md** (7.4K) - Current system status

#### Quick References
- ✅ **README.md** - Main documentation index
- ✅ **QUICKSTART.md** (6.7K) - Fast setup guide
- ⚠️ **OPTIMIZATION_QUICKREF.md** - MERGE into OPTIMIZATION_GUIDE.md
- ⚠️ **RAG_QUICKREF.md** - MERGE into RAG_SETUP_GUIDE.md

#### Phase Documentation (Consolidate into 1 file)
- ⚠️ **CREATE**: PHASE_STATUS.md (consolidates all phase progress)
  - Current phase: System Operational (15/16 services)
  - Next phase: AI Enhancement (12-phase plan)
  - Completed phases summary
  - Active priorities

---

### 2. 🗄️ ARCHIVE (Historical Reference - Move to docs/archive/)

#### Completed Implementation Records
- PHASE_1.1_COMPLETE.md - Security hardening (Oct 23, 2025)
- PHASE_1.2_PROGRESS.md - Import migration (Oct 23, 2025)
- PHASE_2.1_COMPLETE.md - Market data sync (Oct 23, 2025)
- PHASE_2.1_DISCOVERY.md - Task discovery (Oct 23, 2025)
- PHASE_2.2_COMPLETE.md - Signal generation (Oct 23, 2025)
- PHASE_3_BASELINE_TESTS.md - Test environment (Oct 23, 2025)
- RAG_INTEGRATION_COMPLETE.md - RAG implementation (Oct 22, 2025)
- RAG_IMPLEMENTATION_SUMMARY.md - RAG summary (Oct 18, 2025)
- MULTI_REPO_IMPLEMENTATION_COMPLETE.md - Multi-repo setup (Oct 23, 2025)
- MIGRATION_COMPLETE.md - System migration (Oct 2025)
- IMPORT_COMPLETE_SUMMARY.md - Import fixes (Oct 2025)
- IMPORT_FIX_SUMMARY.md - Import resolution (Oct 2025)
- IMPORT_MIGRATION_COMPLETE.md - Import migration (Oct 2025)

#### GitHub Issues/Project Management (Outdated)
- AI_ISSUES_SUMMARY.md - Superseded by GitHub Issues
- AI_PROJECT_SUMMARY.md - Superseded by GitHub Projects
- CREATE_AI_ISSUES.md - One-time setup complete
- CURRENT_ISSUES_STATUS.md - Stale (Oct 2025)
- GITHUB_ISSUES_CREATED.md - Historical record
- GITHUB_ISSUES_IMPORT.md - One-time setup
- GITHUB_ISSUES_SUMMARY.md - Superseded by GitHub UI
- GITHUB_ISSUES_TEMPLATES.md - Superseded by .github/ISSUE_TEMPLATE/
- GITHUB_PROJECT_INTEGRATION.md - Setup complete
- ISSUE_6_COMPLETE.md - Specific issue completion
- ISSUE_6_PROGRESS.md - Specific issue progress
- PROJECT_INTEGRATION_SUMMARY.md - Setup complete

#### Old Summaries/Guides
- IMPLEMENTATION_SUMMARY.md (33K) - Outdated overview
- IMPLEMENTATION_SUMMARY_OLD.md (13K) - Very outdated
- PROJECT_HEALTH_DASHBOARD_OLD.md (1.5K) - Superseded by current version
- IMPLEMENTATION_OVERVIEW.md - General overview (merge into ARCHITECTURE.md)

---

### 3. 🗑️ DELETE (Obsolete/Redundant)

#### Duplicate Quick References
- QUICKREF_DYNAMIC_WORKFLOWS.md - Covered in .github/workflows/
- QUICKREF_GITHUB_ISSUES.md - Use GitHub Issues directly
- QUICKREF_MERMAID_NOTIFICATIONS.md - Feature-specific, low priority
- QUICKREF_MULTI_REPO.md - Monorepo is primary architecture
- QUICK_START_GUIDE.md - Duplicate of QUICKSTART.md

#### Python 3.13 Migration (Resolved)
- PYTHON313_COMPATIBILITY.md - Issue resolved
- PYTHON313_ISSUE_SOLUTION.md - Issue resolved
- PYTHON313_VENV_SETUP.md - Migrated to 3.12
- WSL_CRASH_RECOVERY.md - Specific troubleshooting (low value)

#### Obsolete Setup Guides
- GITHUB_CLI_SETUP.md - Standard tool, use official docs
- SATELLITE_REPO_SETUP.md - Not using satellite repos (monorepo approach)
- SETUP_CHECKLIST.md - Outdated checklist
- VENV_SETUP.md - Covered in QUICKSTART.md

#### Obsolete Security Docs (After Phase 1.1 complete)
- SECURITY_NOTICE.md - .env exposure resolved
- SECURITY_AUDIT.md - Audit complete, findings in ARCHITECTURE.md
- SECURITY_SETUP.md - Setup complete

#### Specific Implementation Guides (Covered in Main Docs)
- IMPORT_GUIDE.md - Migration complete
- RAG_PHASE1.md - Covered in RAG_SETUP_GUIDE.md
- RAG_TASKS_IMPLEMENTATION.md - Covered in AI_STRATEGY_INTEGRATION.md
- WEB_UI_IMPLEMENTATION.md - Implementation complete
- TEST_COVERAGE_SUMMARY.md - Covered in PHASE_STATUS.md
- CELERY_TASKS.md - Covered in ARCHITECTURE.md
- CELERY_TASKS_SUMMARY.md - Duplicate of CELERY_TASKS.md
- TASK_WORKFLOW.md - Covered in ARCHITECTURE.md

#### Outdated Planning Docs
- ARCHITECTURE_DECISION_NOW_VS_LATER.md - Decisions made
- ARCHITECTURE_REFACTORING_PLAN.md - Refactoring complete
- SERVICE_CLEANUP_PLAN.md - Cleanup complete
- DEMO_PLAN.md - Specific demo, low ongoing value
- DYNAMIC_WORKFLOWS.md - Covered in .github/workflows/

#### Specific How-Tos (Low Traffic)
- VISUAL_WORKFLOW_GUIDE.md - Low utility
- WORKFLOW_VISUAL_GUIDE.md - Duplicate of above
- VSCODE_SETTINGS_GUIDE.md - Covered in .vscode/settings.json comments

#### Project Management (Superseded by GitHub Projects)
- PROJECT_MANAGEMENT_SUMMARY.md - Use GitHub Projects
- PROJECT_STATUS.md - Outdated (Oct 20, 2025)
- PROJECT_ISSUES.md - Use GitHub Issues
- PROJECT_STRENGTHS.md - Motivational, not operational

---

## 📝 New Documentation to Create

### 1. PHASE_STATUS.md (Replaces all phase completion docs)
**Content**:
- ✅ Completed Phases Summary (Phases 1-3)
- 🚧 Current Phase: System Operational (15/16 services)
- 🎯 Next Phase: AI Enhancement (12-phase roadmap from copilot-instructions.md)
- 📊 Key Metrics: 69/69 passing tests, 15/16 services healthy, 93.75% operational
- ⏭️ Immediate Next Steps: Begin Phase 1 - Data Preparation for ASMBTR

### 2. ARCHITECTURE_UPDATE.md (One-time update task)
**Action**: Update ARCHITECTURE.md with:
- Current service status (15/16 operational)
- Disabled services notes (fks_execution Rust issue, fks_web_ui architecture review)
- Service health dashboard info (http://localhost:8000/health/dashboard/)
- Monitoring stack details (Prometheus, Grafana, flower)

### 3. QUICKREF.md (Consolidate all quickrefs)
**Content**:
- Quick commands (make up, make logs, docker-compose ps)
- Service ports (8001-8006, 3000, 5050, 5555, 9090)
- Health check URLs
- Common troubleshooting
- Test commands

---

## 🔄 Update Tasks for Existing Docs

### AI_STRATEGY_INTEGRATION.md
- ✅ Already up-to-date with 5-phase plan
- ⚠️ Add reference to new 12-phase plan in copilot-instructions.md
- ⚠️ Update status from "Planning Phase" to "Implementation Ready"

### ARCHITECTURE.md
- ⚠️ Add current service status (15/16 operational)
- ⚠️ Document disabled services with troubleshooting notes
- ⚠️ Add health dashboard section
- ⚠️ Update Celery tasks section with implemented tasks

### MONOREPO_ARCHITECTURE.md
- ⚠️ Merge MULTI_REPO_ARCHITECTURE.md content
- ⚠️ Clarify monorepo is primary (multi-repo is optional future)
- ⚠️ Update service directory structure

### PROJECT_HEALTH_DASHBOARD.md
- ⚠️ Update with current metrics (Oct 28, 2025)
- ⚠️ 15/16 services operational (93.75%)
- ⚠️ 69 passing tests
- ⚠️ AI Enhancement Plan as next priority

### README.md (docs/)
- ⚠️ Update index with new structure
- ⚠️ Remove links to archived/deleted docs
- ⚠️ Add AI Enhancement Plan section
- ⚠️ Update quick start references

---

## 📂 Final Documentation Structure (22 files)

```
docs/
├── README.md                              # Main index
├── QUICKSTART.md                          # Fast setup
├── QUICKREF.md                            # Command reference (NEW - consolidates quickrefs)
│
├── Architecture/
│   ├── ARCHITECTURE.md                    # Main system architecture (UPDATED)
│   ├── MONOREPO_ARCHITECTURE.md          # Repository structure (UPDATED - merges multi-repo)
│   └── AI_ARCHITECTURE.md                # AI system design
│
├── Planning/
│   ├── AI_STRATEGY_INTEGRATION.md        # 5-phase AI plan (UPDATED)
│   ├── CRYPTO_REGIME_BACKTESTING.md      # Regime detection research
│   ├── TRANSFORMER_TIME_SERIES_ANALYSIS.md # ML forecasting
│   ├── PHASE_PLAN_SUMMARY.md             # Overall roadmap
│   ├── PHASE_STATUS.md                   # Current progress (NEW)
│   └── AI_CHECKLIST.md                   # Implementation checklist
│
├── Operations/
│   ├── OPTIMIZATION_GUIDE.md             # Strategy optimization (includes quickref)
│   ├── RAG_SETUP_GUIDE.md                # RAG configuration (includes quickref)
│   └── PROJECT_HEALTH_DASHBOARD.md       # System status (UPDATED)
│
├── Phase_Plans/
│   ├── PHASE_1_IMMEDIATE_FIXES.md        # Week 1-4 plan
│   ├── PHASE_2_CORE_DEVELOPMENT.md       # Week 5-10 plan
│   ├── PHASE_3_TESTING_QA.md             # Week 7-12 plan
│   ├── PHASE_4_DOCUMENTATION.md          # Week 7-8 plan
│   ├── PHASE_5_DEPLOYMENT.md             # Week 9-14 plan
│   ├── PHASE_6_OPTIMIZATION.md           # Ongoing plan
│   └── PHASE_7_FUTURE_FEATURES.md        # Week 15+ plan
│
└── archive/ (95 archived files)
    └── [All completed, obsolete, and historical docs]
```

---

## 🚀 Execution Plan

### Step 1: Immediate Actions (30 minutes)
1. ✅ Create docs/archive/ directory
2. ✅ Move 95 files to archive/ (see lists above)
3. ✅ Create PHASE_STATUS.md (consolidate phase progress)
4. ✅ Create QUICKREF.md (consolidate all quickrefs)
5. ✅ Delete obsolete files (see DELETE list)

### Step 2: Updates (1 hour)
6. ⚠️ Update ARCHITECTURE.md with current status
7. ⚠️ Update MONOREPO_ARCHITECTURE.md (merge multi-repo)
8. ⚠️ Update PROJECT_HEALTH_DASHBOARD.md (current metrics)
9. ⚠️ Update AI_STRATEGY_INTEGRATION.md (reference 12-phase plan)
10. ⚠️ Update docs/README.md (new index)

### Step 3: Validation (15 minutes)
11. ✅ Verify all links in README.md work
12. ✅ Ensure copilot-instructions.md references are correct
13. ✅ Test documentation navigation flow
14. ✅ Commit changes with descriptive message

---

## 📋 Success Criteria

- ✅ Documentation reduced from 120 to ~22 files (82% reduction)
- ✅ All active docs updated with current status (Oct 28, 2025)
- ✅ Clear navigation from README.md to all docs
- ✅ Historical docs preserved in archive/
- ✅ No broken links or references
- ✅ AI Enhancement Plan clearly documented
- ✅ Current system status (15/16 services) documented

---

**Next**: Execute Step 1 to create archive and move files
