# FKS Platform Documentation

**Version**: 2.0.0  
**Last Updated**: October 28, 2025  
**Active Documentation**: 22 core files (82% reduction from 120 files)  
**Current Phase**: AI Enhancement (12-phase plan, 12-16 weeks)

---

## 🚀 Quick Start

**New to FKS?** Start here:

1. **[../QUICKSTART.md](../QUICKSTART.md)** - Get running in 5 minutes
2. **[ARCHITECTURE.md](ARCHITECTURE.md)** - Understand the 8-service microservices architecture
3. **[PHASE_STATUS.md](PHASE_STATUS.md)** - Current development status and roadmap

**For AI Agents**:
- **[../.github/copilot-instructions.md](../.github/copilot-instructions.md)** - Complete project context and 12-phase AI enhancement plan

---

## 📚 Documentation Index

### 🎯 Strategic Planning (6 files)
Core roadmaps and AI strategy documents

- **[AI_STRATEGY_INTEGRATION.md](AI_STRATEGY_INTEGRATION.md)** - Original 5-phase AI plan (LLM strategies, regime detection)
- **[CRYPTO_REGIME_BACKTESTING.md](CRYPTO_REGIME_BACKTESTING.md)** - 13-week regime detection research plan
- **[TRANSFORMER_TIME_SERIES_ANALYSIS.md](TRANSFORMER_TIME_SERIES_ANALYSIS.md)** - ML forecasting implementation guide
- **[PHASE_PLAN_SUMMARY.md](PHASE_PLAN_SUMMARY.md)** - Overall development roadmap
- **[PHASE_STATUS.md](PHASE_STATUS.md)** ⭐ - **Current progress tracker** (Phases 1-3 complete, AI Enhancement next)
- **[AI_CHECKLIST.md](AI_CHECKLIST.md)** - AI implementation checklist

### 🏗️ Architecture & System Design (3 files)
System structure and design decisions

- **[ARCHITECTURE.md](ARCHITECTURE.md)** - 8-service microservices architecture (fks_main, fks_api, fks_app, fks_data, fks_ai, fks_execution, fks_ninja, fks_web)
- **[MONOREPO_ARCHITECTURE.md](MONOREPO_ARCHITECTURE.md)** - Monorepo structure with services/ directory
- **[AI_ARCHITECTURE.md](AI_ARCHITECTURE.md)** - AI system design (RAG, LLM, multi-agent)

### ⚙️ Operations & Optimization (3 files)
Running, monitoring, and optimizing the system

- **[PROJECT_HEALTH_DASHBOARD.md](PROJECT_HEALTH_DASHBOARD.md)** - Current system status (15/16 services, 69 tests passing)
- **[OPTIMIZATION_GUIDE.md](OPTIMIZATION_GUIDE.md)** - Strategy optimization with Optuna
- **[RAG_SETUP_GUIDE.md](RAG_SETUP_GUIDE.md)** - RAG system configuration (ChromaDB, pgvector, embeddings)

### 📋 Phase Plans (7 files)
Detailed plans for each development phase

- **[PHASE_1_IMMEDIATE_FIXES.md](PHASE_1_IMMEDIATE_FIXES.md)** - Weeks 1-4: Security, imports, cleanup ✅ COMPLETE
- **[PHASE_2_CORE_DEVELOPMENT.md](PHASE_2_CORE_DEVELOPMENT.md)** - Weeks 5-10: Celery tasks, RAG, Web UI ✅ COMPLETE
- **[PHASE_3_TESTING_QA.md](PHASE_3_TESTING_QA.md)** - Weeks 7-12: Test expansion, CI/CD ✅ COMPLETE
- **[PHASE_4_DOCUMENTATION.md](PHASE_4_DOCUMENTATION.md)** - Weeks 7-8: Documentation updates
- **[PHASE_5_DEPLOYMENT.md](PHASE_5_DEPLOYMENT.md)** - Weeks 9-14: Production deployment
- **[PHASE_6_OPTIMIZATION.md](PHASE_6_OPTIMIZATION.md)** - Ongoing: Performance optimization
- **[PHASE_7_FUTURE_FEATURES.md](PHASE_7_FUTURE_FEATURES.md)** - Week 15+: Advanced features

### 📖 Quick References (3 files)
Fast lookups and command references

- **[../QUICKSTART.md](../QUICKSTART.md)** - Quick setup guide
- **[../QUICKREF.md](../QUICKREF.md)** - Commands, ports, troubleshooting
- **[DOCUMENTATION_CLEANUP_PLAN.md](DOCUMENTATION_CLEANUP_PLAN.md)** - This cleanup plan (Oct 28, 2025)

### �️ Archived Documentation (95 files)
Historical completion reports and legacy docs

Located in `archive/` - Preserved for reference but not actively maintained:
- **archive/completed-phases/** - Phase 1-3 completion reports (PHASE_*.md)
- **archive/github-issues/** - Historical GitHub Issues documentation
- **archive/summaries/** - Old implementation summaries
- **archive/setup-guides/** - Deprecated setup guides (Python 3.13, security audits)

---

## 🎯 Common Tasks

### Setup & Run Locally
```bash
# Standard stack (8 services)
make up
make logs

# GPU stack (adds Ollama LLM + fks_ai)
make gpu-up
make logs
```
See: [../QUICKSTART.md](../QUICKSTART.md)

### Run Tests
```bash
# Run all passing tests
docker-compose exec web pytest tests/unit/test_security.py \
  tests/unit/test_trading/test_signals.py \
  tests/unit/test_trading/test_strategies.py -v

# Test specific module
docker-compose exec web pytest tests/unit/test_trading/test_signals.py -v
```
See: [PHASE_3_TESTING_QA.md](PHASE_3_TESTING_QA.md)

### Check System Health
```bash
# View health dashboard
open http://localhost:8000/health/dashboard/

# Check service status
docker-compose ps

# View metrics
open http://localhost:9090  # Prometheus
open http://localhost:3000  # Grafana (admin/admin)
```
See: [PROJECT_HEALTH_DASHBOARD.md](PROJECT_HEALTH_DASHBOARD.md)

### Begin AI Enhancement Phase 1
```bash
# Verify fks_data service
docker-compose ps fks_data

# Start data preparation
# Location: services/data/src/collectors/forex_collector.py
# Target: EUR/USD tick data streaming, Δ scanner operational
```
See: [PHASE_STATUS.md](PHASE_STATUS.md) → "Immediate Next Steps"

---

## 📊 Documentation Cleanup Summary (Oct 28, 2025)

**Before**: 120 files (significant duplication and outdated content)  
**After**: 22 core files (organized by purpose)  
**Reduction**: 82% (98 files archived/deleted)

### What Was Archived
- ✅ 27 completion reports (*_COMPLETE.md, *_PROGRESS.md) → `archive/completed-phases/`
- ✅ 16 GitHub Issues docs → `archive/github-issues/`
- ✅ 27 old summaries and guides → `archive/summaries/`
- ✅ 25 deprecated setup guides → `archive/setup-guides/`

### What Was Consolidated
- ✅ 8 QUICKREF_*.md files → Single `../QUICKREF.md`
- ✅ 16 PHASE substatus files → Master `PHASE_STATUS.md`

### What Remains
- ✅ 6 Strategic Planning docs (AI roadmaps)
- ✅ 3 Architecture docs (system design)
- ✅ 3 Operations docs (health, optimization, RAG)
- ✅ 7 Phase Plans (development phases)
- ✅ 3 Quick References (QUICKSTART, QUICKREF, cleanup plan)

---

## 🆘 Need Help?

### Navigation
- **Quick commands**: [../QUICKREF.md](../QUICKREF.md) - All commands in one place
- **Current status**: [PHASE_STATUS.md](PHASE_STATUS.md) - What's done, what's next
- **System health**: http://localhost:8000/health/dashboard/
- **Architecture**: [ARCHITECTURE.md](ARCHITECTURE.md) - How everything fits together

### Troubleshooting
1. Check service logs: `make logs` or `docker-compose logs <service>`
2. Review health dashboard: http://localhost:8000/health/dashboard/
3. Verify services: `docker-compose ps` (should show 15/16 healthy)
4. Check tests: `docker-compose exec web pytest tests/unit/ -v`

### For AI Agents
- **Primary context**: [../.github/copilot-instructions.md](../.github/copilot-instructions.md) (1437 lines)
- **Current priorities**: [PHASE_STATUS.md](PHASE_STATUS.md) → "Immediate Next Steps"
- **Architecture patterns**: [ARCHITECTURE.md](ARCHITECTURE.md) → "Service Responsibilities"

---

**Last Updated**: October 28, 2025 - Post Phase 3 completion, documentation reorganization, AI Enhancement plan active  
**Next Milestone**: Phase 1 - Data Preparation for ASMBTR (Nov 1-2, 2025)

