# Phase 9 Testing Plan

**Date**: October 17, 2025  
**Status**: In Progress - Dependencies Installing  
**Branch**: refactor (30 commits)

---

## Installation Progress

### Current Step
Installing all dependencies from `requirements.txt` (excluding `uwsgi` which doesn't work on Windows).

**Command Running**:
```bash
.venv/Scripts/python.exe -m pip install -r requirements-no-uwsgi.txt
```

**Packages Being Installed** (~130+ packages):
- ✅ Django 5.2.7 (already installed)
- 🔄 Django REST Framework
- 🔄 Celery + Redis client
- 🔄 ML Libraries (PyTorch 2.9, scikit-learn, xgboost, lightgbm)
- 🔄 AI/LLM (OpenAI, Anthropic, Langchain, transformers)
- 🔄 RAG (FAISS, ChromaDB, sentence-transformers)
- 🔄 Testing (pytest, pytest-django, pytest-cov)
- 🔄 Data Science (pandas, numpy, scipy, statsmodels)
- 🔄 Visualization (matplotlib, seaborn, plotly, streamlit)
- 🔄 And many more...

**Note**: `uwsgi` skipped (Windows incompatible - uses `os.uname()` which doesn't exist on Windows)

---

## Test Suite Plan

Once installation completes, we'll run the following tests in order:

### 1. Django System Check ✅
**Purpose**: Verify Django configuration is valid  
**Command**:
```bash
.venv/Scripts/python.exe manage.py check
```

**Expected Result**: `System check identified no issues (0 silenced).`

**Checks**:
- All INSTALLED_APPS are importable
- Settings are valid
- URL patterns are correct
- Models are properly defined

---

### 2. Import Test ✅
**Purpose**: Verify fks_project module imports correctly  
**Command**:
```bash
.venv/Scripts/python.exe -c "import sys; sys.path.insert(0, '.'); import fks_project; print('✅ fks_project imports successfully')"
```

**Expected Result**: `✅ fks_project imports successfully`

**Checks**:
- fks_project/__init__.py imports Celery correctly
- All module dependencies are satisfied

---

### 3. Celery App Check ✅
**Purpose**: Verify Celery app initializes  
**Command**:
```bash
.venv/Scripts/python.exe -c "import sys; sys.path.insert(0, '.'); from fks_project.celery import app; print(f'✅ Celery app initialized: {app.main}')"
```

**Expected Result**: `✅ Celery app initialized: fks_project`

---

### 4. Task Import Test ✅
**Purpose**: Verify trading_app.tasks module imports  
**Command**:
```bash
.venv/Scripts/python.exe -c "import sys; sys.path.insert(0, '.'); from src.trading_app import tasks; print(f'✅ Tasks module imported. Functions: {len([x for x in dir(tasks) if not x.startswith(\"_\") and callable(getattr(tasks, x))])}')"
```

**Expected Result**: `✅ Tasks module imported. Functions: 16`

---

### 5. Database Migrations Check ✅
**Purpose**: Check for any pending migrations  
**Command**:
```bash
.venv/Scripts/python.exe manage.py makemigrations --dry-run
```

**Expected Result**: `No changes detected` (all migrations already created)

**If migrations needed**:
```bash
.venv/Scripts/python.exe manage.py makemigrations
.venv/Scripts/python.exe manage.py migrate
```

---

### 6. Celery Task Registration (Optional) ⚠️
**Purpose**: Verify all 16 tasks are registered  
**Requirement**: Requires Redis server running  
**Command**:
```bash
celery -A fks_project inspect registered
```

**Expected Result**: List showing all 16 tasks with `trading_app.tasks.*` prefix:
1. trading_app.tasks.fetch_latest_prices
2. trading_app.tasks.fetch_historical_data
3. trading_app.tasks.generate_trading_signals
4. trading_app.tasks.update_open_positions
5. trading_app.tasks.check_position_triggers
6. trading_app.tasks.record_account_balances
7. trading_app.tasks.run_daily_optimization
8. trading_app.tasks.send_discord_notification
9. trading_app.tasks.send_performance_summary
10. trading_app.tasks.cleanup_old_data
11. trading_app.tasks.run_backtest_async
12. trading_app.tasks.ingest_completed_trades
13. trading_app.tasks.ingest_trading_signals
14. trading_app.tasks.ingest_backtest_results
15. trading_app.tasks.ingest_all_trading_data
16. trading_app.tasks.cleanup_old_rag_data

**Note**: This test requires Redis. If Redis isn't running, we'll skip this test and document that Celery tasks need Redis for runtime verification.

---

### 7. Pytest Test Suite (Optional) ⚠️
**Purpose**: Run full test suite  
**Command**:
```bash
.venv/Scripts/python.exe -m pytest tests/ -v --tb=short
```

**Expected Result**: Tests pass or document any failures

**Note**: Some tests may fail if they require:
- Database connection (PostgreSQL)
- External services (Redis, API keys)
- Environment variables not set

We'll run this and document results, but failures may be expected in development environment.

---

### 8. Import Path Verification ✅
**Purpose**: Verify no imports reference old `src/trading/` paths  
**Command**:
```bash
grep -r "from trading\." src/ --include="*.py" --exclude-dir=__pycache__
grep -r "import trading\." src/ --include="*.py" --exclude-dir=__pycache__
```

**Expected Result**: No matches found (all should use `trading_app`)

---

### 9. Settings Verification ✅
**Purpose**: Verify INSTALLED_APPS doesn't reference 'trading'  
**Command**:
```bash
grep -n "^[[:space:]]*['\"]trading['\"]" fks_project/settings.py
```

**Expected Result**: No matches (should only have 'trading_app')

---

## Success Criteria

### Minimum Requirements (Must Pass)
- [ ] Django system check passes
- [ ] fks_project module imports successfully
- [ ] Celery app initializes without errors
- [ ] trading_app.tasks module imports
- [ ] No migrations pending (or migrations apply cleanly)
- [ ] No imports reference old `src/trading/` paths
- [ ] INSTALLED_APPS doesn't include 'trading'

### Optional Tests (Document Results)
- [ ] Celery task registration (requires Redis)
- [ ] Pytest test suite (may have env-specific failures)

---

## Known Limitations

### Windows Development Environment
- **uwsgi**: Skipped (Linux-only WSGI server)
- **Redis**: May not be running (required for Celery runtime tests)
- **PostgreSQL**: May not be configured (required for database tests)
- **API Keys**: May not be set (required for external service tests)

### Expected Behavior
- Core Django functionality should work
- Module imports should work
- Code structure should be valid
- Runtime functionality (Celery, database, APIs) may require deployment environment

---

## Contingency Plans

### If Django Check Fails
1. Review error message for missing imports
2. Check if any apps in INSTALLED_APPS are missing
3. Verify settings.py syntax
4. Check for circular imports

### If Task Import Fails
1. Check trading_app/tasks.py for syntax errors
2. Verify all imports in tasks.py are available
3. Check for missing dependencies (Celery decorators, etc.)

### If Migrations Needed
1. Review generated migration files
2. Apply migrations if they look correct
3. Document what changed in migration

---

## Post-Testing Actions

Once all tests complete:

1. **Update PHASE9C_TESTING_STATUS.md** with results
2. **Commit test results** (if any files changed)
3. **Update TODO list** - mark Phase 9 testing complete
4. **Proceed to Phase 10** - Documentation updates

---

## Timeline

**Estimated Duration**: 30-45 minutes total
- Dependencies installation: 20-30 minutes (in progress)
- Test execution: 5-10 minutes
- Documentation: 5 minutes

**Current Progress**:
- ⏳ Installing dependencies (~5 minutes elapsed)
- 🔲 Running tests (pending)
- 🔲 Documentation update (pending)

---

**Last Updated**: October 17, 2025 12:35 PM  
**Next Update**: After dependency installation completes
