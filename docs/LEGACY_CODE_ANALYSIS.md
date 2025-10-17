# Legacy Code Analysis - Phase 9

**Analysis Date:** October 17, 2025  
**Branch:** refactor  
**Purpose:** Determine which legacy directories can be safely removed

---

## Summary

### CONFIRMED LEGACY (Can Remove)
1. ✅ **src/framework/** (928K) - Migrated to `src/core/`
2. ✅ **src/domain/** (92K) - Migrated to `src/trading_app/`
3. ⚠️ **src/transformer/** (~150K) - Microservice architecture remnant
4. ⚠️ **src/training/** (~250K) - Microservice architecture remnant

### ACTIVE / NEEDS MIGRATION
1. ⚠️ **src/trading/** (380K) - OLD Django app with Celery tasks (16 tasks defined!)
2. ⚠️ **src/worker/** (~200K) - Hybrid: Listed in INSTALLED_APPS but has microservice code

---

## Detailed Analysis

### 1. src/trading/ - OLD Django Trading App

**Status:** 🔴 ACTIVE - Has Celery tasks that are currently used!

**Evidence:**
```python
# In fks_project/settings.py line 70-72:
# Legacy Django apps (to be migrated)
'trading',
```

**Celery Tasks Found (16 total):**
- `src/trading/tasks.py` contains:
  - fetch_latest_prices
  - fetch_historical_data
  - generate_trading_signals
  - update_open_positions
  - check_position_triggers
  - record_account_balances
  - run_daily_optimization
  - send_discord_notification
  - send_performance_summary
  - cleanup_old_data
  - run_backtest_async
  - ingest_completed_trades
  - ingest_trading_signals
  - ingest_backtest_results
  - ingest_all_trading_data
  - cleanup_old_rag_data

**Celery Configuration:**
- docker-compose.yml shows: `celery -A fks_project worker`
- These tasks are actively used by Celery workers

**Action Required:**
1. ⚠️ **CRITICAL:** These tasks are ACTIVE and used by celery_worker
2. Need to migrate tasks from `src/trading/tasks.py` to `src/trading_app/tasks.py`
3. After migration, remove old `src/trading/` app
4. Update `fks_project/settings.py` to remove `'trading'` from INSTALLED_APPS

**Migration Steps:**
```bash
# 1. Create new tasks.py in trading_app
cp src/trading/tasks.py src/trading_app/tasks.py

# 2. Update imports in tasks.py to use new app structure
# from trading.models → from trading_app.models

# 3. Test all tasks work with new imports
celery -A fks_project inspect registered

# 4. Update any code calling these tasks
grep -r "trading.tasks" src/ --include="*.py"

# 5. Remove old app
git rm -r src/trading/
```

---

### 2. src/worker/ - Hybrid Django App + Microservice Code

**Status:** 🟡 AMBIGUOUS - Listed as Django app but has microservice architecture

**Evidence:**
```python
# In fks_project/settings.py line 63-67:
# Existing apps
'src.data',
'src.worker',  # ← Listed as existing Django app
```

**Structure:**
```
src/worker/
├── __init__.py (placeholder: "__all__ = []")
├── main.py (microservice entry point - starts HTTP server)
├── service.py (microservice code)
├── app.py
├── ensemble.py
├── fks_logging.py
├── executors/
├── monitoring/
├── scheduler/
├── tasks/
├── task_queue/
└── tests/
```

**Microservice Evidence:**
- `main.py` imports `framework.services.template.start_template_service`
- Starts HTTP server on port 8006
- NOT used in docker-compose.yml (no `worker:` service defined)

**Django App Evidence:**
- Listed in INSTALLED_APPS
- But NO: models.py, apps.py, views.py, urls.py, migrations/

**Analysis:**
This appears to be **transitional code** - registered as a Django app for compatibility but still contains old microservice structure.

**Docker Compose Reality:**
```yaml
celery_worker:
  command: celery -A fks_project worker  # Uses Django Celery, NOT src/worker/main.py
```

**Action Required:**
1. Check if any Django code imports from `src.worker`
2. If no imports → can be removed (microservice architecture abandoned)
3. If has imports → need to migrate to `src/core` or `src/trading_app`

**Investigation Command:**
```bash
# Check if anything imports from src.worker
grep -r "from src.worker\|from worker\|import worker" src/ --include="*.py" | grep -v "src/worker/"
```

---

### 3. src/transformer/ - ML Transformer Microservice

**Status:** 🔴 LEGACY - Microservice not used in docker-compose

**Evidence:**
- Has `main.py` that starts HTTP server
- Imports `framework.services.template`
- NOT in docker-compose.yml (no `transformer:` service)
- NOT in INSTALLED_APPS

**Structure:**
```
src/transformer/
├── __init__.py
├── main.py (starts HTTP server)
├── service.py
└── app.py
```

**Docker Compose Reality:**
No `transformer:` service defined. Architecture changed to Django monolith + Celery.

**Action Required:**
1. Check if ML transformer logic needed
2. If needed → migrate to Celery task in `src/trading_app/tasks.py`
3. Remove src/transformer/

---

### 4. src/training/ - ML Training Microservice

**Status:** 🔴 LEGACY - Microservice not used in docker-compose

**Evidence:**
- Has `main.py` that starts HTTP server
- Imports `framework.services.template`
- NOT in docker-compose.yml (no `training:` service)
- NOT in INSTALLED_APPS

**Structure:**
```
src/training/
├── __init__.py
├── main.py (starts HTTP server)
├── service.py
├── dataset_manager.py
├── gpu_manager.py
├── training_types.py
└── types.py
```

**Docker Compose Reality:**
No `training:` service defined. Architecture changed to Django monolith + Celery.

**Action Required:**
1. Check if ML training logic needed
2. If needed → migrate to Celery task in `src/trading_app/tasks.py`
3. Remove src/training/

---

### 5. src/framework/ - Old Framework Code

**Status:** 🟡 LEGACY but still IMPORTED (928K, 64 files)

**Evidence:**
- Code migrated to `src/core/`
- But 20+ files still import from `framework.*`

**Imports Found In:**
- src/worker/service.py
- src/worker/scheduler/scheduler.py
- src/worker/main.py
- src/worker/executors/*.py
- src/transformer/main.py
- src/training/main.py
- src/trading_app/engine/_impl.py
- Plus framework's own internal imports

**Action Required:**
1. Update imports: `from framework.*` → `from core.*`
2. Then remove src/framework/

---

### 6. src/domain/ - Old Domain Logic

**Status:** 🟡 LEGACY - Migrated to src/trading_app/

**Evidence:**
- Code appears to be in `src/trading_app/domain/` or `src/trading_app/models/`
- Need to verify no remaining imports

**Action Required:**
1. Search for imports: `from domain.*`
2. If none found → safe to remove
3. Remove src/domain/

---

## Migration Priority Order

### Phase 9A: Immediate (No Dependencies)
1. ✅ Remove `src/domain/` (verify no imports)
2. ✅ Remove `src/transformer/` (not used)
3. ✅ Remove `src/training/` (not used)

**Estimated Space Savings:** ~492K

### Phase 9B: After Import Fixes
1. Fix 20+ imports from `framework.*` to `core.*`
2. Remove `src/framework/`

**Estimated Space Savings:** 928K

### Phase 9C: After Task Migration (CRITICAL)
1. Create `src/trading_app/tasks.py`
2. Migrate 16 Celery tasks from `src/trading/tasks.py`
3. Update task imports throughout codebase
4. Test all Celery tasks work
5. Remove `src/trading/` and old 'trading' from INSTALLED_APPS

**Estimated Space Savings:** 380K

### Phase 9D: After Worker Analysis
1. Determine if `src/worker/` has any used code
2. Either migrate to `src/core/` or remove entirely
3. Remove from INSTALLED_APPS

**Estimated Space Savings:** ~200K

---

## Total Potential Savings

- src/domain/: 92K
- src/transformer/: ~150K
- src/training/: ~250K
- src/framework/: 928K
- src/trading/: 380K
- src/worker/: ~200K

**Total: ~2MB of legacy code**

---

## Risk Assessment

### LOW RISK (Can remove immediately)
- ✅ src/domain/ (if no imports found)
- ✅ src/transformer/ (not in docker-compose)
- ✅ src/training/ (not in docker-compose)

### MEDIUM RISK (After import fixes)
- ⚠️ src/framework/ (need to update 20+ imports first)
- ⚠️ src/worker/ (check for Django imports first)

### HIGH RISK (Needs careful migration)
- 🔴 src/trading/ (has 16 ACTIVE Celery tasks!)

---

## Next Steps

1. ✅ Run import checks for domain/transformer/training
2. ✅ Remove confirmed unused directories
3. ⚠️ Fix framework imports
4. 🔴 Migrate Celery tasks (CRITICAL - app won't work without these!)
5. ✅ Update INSTALLED_APPS
6. ✅ Run Django migrations
7. ✅ Run test suite
