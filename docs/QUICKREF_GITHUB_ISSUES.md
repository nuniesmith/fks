# 🎯 GitHub Issues Quick Reference

**Created**: October 18, 2025  
**Total Issues**: 10 strategic issues  
**Estimated Completion**: 3-4 weeks

---

## 📋 Issue List

### 🔴 CRITICAL (Do First)

- **#48**: [P3.2] Fix Legacy Import Errors
  - **Impact**: Unblocks 20 failing tests (41% → 100% pass rate)
  - **Effort**: 1-2 days
  - **Blocker**: Prevents CI/CD, testing, coverage
  
- **#49**: [P3.3] Implement FKS Intelligence RAG Tasks  
  - **Impact**: Core trading functionality (16 task stubs → implementations)
  - **Effort**: 1-2 weeks
  - **Blocker**: No automated trading without this

### 🟡 HIGH (Next Sprint)

- **#39**: [P3.4] Replace Mock Data in Views (15 TODOs)
- **#41**: [P3.6] Expand Test Coverage (41% → 80%)
- **#42**: [P3.7] Verify RAG Integration
- **#45**: [P3.10] Runtime Security Checks

### 🟢 MEDIUM (Polish)

- **#43**: [P3.8] Update Dependencies (pip-audit)
- **#44**: [P3.9] Add Async Support (6-7x faster)
- **#46**: [P3.11] Fix Markdown Lint (189 errors)
- **#47**: [P3.12] GPU Optimization (6GB VRAM)

### ⚪ LOW (Optional)

- **#40**: [P3.5] Cleanup Small Files (24 → <10)

---

## ⚡ Quick Commands

```bash
# View all issues
gh issue list

# Start work on critical issue
gh issue develop 48 --checkout

# Check specific issue
gh issue view 48

# Create PR from issue
gh pr create --fill

# Check CI status
gh run list --limit 5
```

---

## 🚀 Recommended Sprint Plan

### Sprint 1 (Week 1): Critical Fixes

```bash
# Issue #48: Fix imports (Days 1-2)
git checkout -b fix/legacy-imports
pytest tests/ -v  # Target: 34/34 passing

# Issue #49: Implement RAG tasks (Days 3-5)
git checkout -b feature/rag-tasks
# Implement 16 tasks in src/trading/tasks.py
```

### Sprint 2 (Week 2): High Priority

```bash
# Issue #39: Replace mock data
# Issue #41: Expand test coverage to 80%
# Issue #42: Verify RAG integration
# Issue #45: Add security middleware
```

### Sprint 3 (Week 3): Polish

```bash
# Issue #43: Update deps (pip-audit)
# Issue #44: Add async (6-7x speedup)
# Issue #46: Fix markdown (189 errors)
# Issue #47: GPU optimization
```

### Sprint 4 (Week 4): Ship It

```bash
# Issue #40: Cleanup (optional)
# Final testing
# Deploy to staging
```

---

## 📊 Success Metrics Tracker

| Metric | Baseline | Target | Issue | Status |
|--------|----------|--------|-------|--------|
| Test Pass Rate | 14/34 (41%) | 34/34 (100%) | #48 | ⏳ |
| Code Coverage | ~41% | 80%+ | #41 | ⏳ |
| Mock Data TODOs | 15 | 0 | #39 | ⏳ |
| RAG Tasks | 0/16 | 16/16 | #49 | ⏳ |
| Security CVEs | ? | 0 critical | #43 | ⏳ |
| Markdown Lint | 189 | 0 | #46 | ⏳ |
| Data Fetch Speed | ~2s/10sym | ~300ms | #44 | ⏳ |

---

## 🎯 Daily Workflow

### Morning

```bash
# Pull latest changes
git pull origin main

# Check CI status
gh run list --limit 1

# Review issues
gh issue list --assignee @me
```

### Development

```bash
# Start feature branch
gh issue develop <number> --checkout

# Run tests frequently
pytest tests/ -v -x  # Stop on first failure

# Commit small changes
git commit -m "feat: <short description>"
```

### End of Day

```bash
# Push work
git push origin HEAD

# Update issue
gh issue comment <number> --body "Progress: <summary>"

# Check tomorrow's priorities
gh issue list --label "phase:3-testing" --sort created
```

---

## 🛠️ Essential Commands

### Testing

```bash
pytest tests/ -v                          # All tests
pytest tests/ -x                          # Stop on first fail
pytest tests/ --cov=src --cov-report=html # Coverage
pytest -m unit -v                         # Unit only
pytest -m "not slow" -v                   # Skip slow
```

### Quality

```bash
make lint                                 # Ruff, mypy, black
make format                               # Auto-format
pip-audit requirements.txt                # Security
```

### Docker

```bash
make up                                   # Start services
make logs                                 # Follow logs
make migrate                              # Run migrations
make down                                 # Stop all
```

### Monitoring

- Health: http://localhost:8000/health/dashboard/
- Grafana: http://localhost:3000
- Flower: http://localhost:5555

---

## 📚 Key Files

```
.github/copilot-instructions.md      # Comprehensive guide
docs/GITHUB_ISSUES_SUMMARY.md        # This file (detailed)
docs/ARCHITECTURE.md                 # System architecture
tests/TEST_GUIDE.md                  # Testing guide
src/web/django/settings.py           # Django config
src/trading/tasks.py                 # 16 tasks to implement
src/web/views.py                     # 15 TODOs to fix
```

---

## 🔗 Resources

- **Full Summary**: `docs/GITHUB_ISSUES_SUMMARY.md`
- **Issues**: https://github.com/nuniesmith/fks/issues
- **Copilot Chat**: Use this file for context

---

## 💡 Pro Tips

1. **Fix #48 first** - Unblocks everything else
2. **TDD approach** - Write tests before code
3. **Commit often** - Small commits = easier debugging
4. **Use health dashboard** - Quick system overview
5. **Monitor CI** - Fix failures immediately
6. **Update copilot-instructions.md** - Document decisions

---

**Status**: Ready to ship in 3-4 weeks  
**Next Action**: Start Issue #48 (Fix imports)

🚀 Good luck!
