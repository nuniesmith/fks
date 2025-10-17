# Phase 9: Cleanup Report

## Files/Directories to Remove

### 1. Old Framework Directory (928K)
**Location:** `src/framework/`
**Reason:** Code migrated to `src/core/` and `src/api_app/` in Phase 4
**Contents:**
- cache/ → Migrated to src/core/cache/
- config/ → Migrated to src/config_app/
- exceptions/ → Migrated to src/core/exceptions/
- lifecycle/
- logging/ → Migrated to src/core/utils/logging.py
- middleware/ → Migrated to src/api_app/middleware/
- patterns/ → Migrated to src/core/patterns/
- services/

**Action:** Remove after confirming no active imports

### 2. Old Domain Directory (92K)
**Location:** `src/domain/`
**Reason:** Trading logic migrated to `src/trading_app/` in Phase 4
**Contents:**
- analytics/
- events/
- market/
- ml/
- portfolio/
- risk/
- trading/ → Migrated to src/trading_app/

**Action:** Remove after confirming migration complete

### 3. Old Django Project Location (36K)
**Location:** `src/django/`
**Reason:** Moved to root `fks_project/` in Phase 5
**Contents:**
- celery.py → Moved to root
- fks_project/ → Moved to root

**Action:** Safe to remove (already migrated in Phase 5)

### 4. Legacy Files in New Apps
**Files:**
- `src/config_app/legacy_config.py` - Old config from root
- `src/trading_app/backtest/legacy_engine.py` - Old backtest engine
- `src/trading_app/signals/legacy_generator.py` - Old signal generator

**Action:** Keep for now (may be referenced), mark for future cleanup

### 5. Old Phase Documentation
**Files in docs/:**
- ALL_PHASES_COMPLETE.md (pre-refactor)
- PHASE1_README.md (old phase 1 doc)
- PHASE3_COMPLETION_REPORT.md (duplicate)
- PHASE3_SUMMARY.md (duplicate)

**Action:** Can be archived or removed (we have PHASE*_COMPLETE.md for each)

## Import Dependencies to Fix

Before removing `src/framework/` and `src/domain/`, need to update imports in:

### Framework References
```
src/trading_app/engine/_impl.py
src/api_app/middleware/circuit_breaker/core.py
src/api_app/middleware/circuit_breaker/decorators.py
src/api_app/middleware/circuit_breaker/state_providers/__init__.py
src/api_app/middleware/circuit_breaker/__init__.py
```

### Recommended Approach
1. Check each file to see if it imports from framework
2. Update imports to use new app structure
3. Verify no other files import from framework/domain
4. Remove directories

## Cleanup Commands

```bash
# After fixing imports, remove old directories
git rm -r src/framework/
git rm -r src/domain/
git rm -r src/django/

# Remove old phase docs (optional)
git rm docs/ALL_PHASES_COMPLETE.md
git rm docs/PHASE1_README.md
git rm docs/PHASE3_COMPLETION_REPORT.md
git rm docs/PHASE3_SUMMARY.md

# Commit cleanup
git commit -m "Phase 9: Remove old framework, domain, and django directories"
```

## Space Savings
- src/framework/: 928K
- src/domain/: 92K
- src/django/: 36K
- **Total: ~1.06MB**

## Cleanup Actions Completed

### ✅ Phase 9 Cleanup #1 (Oct 17, 2025)
- Removed `src/django/` directory (36K, 9 files)
- Removed duplicate phase docs:
  - `docs/ALL_PHASES_COMPLETE.md`
  - `docs/PHASE3_COMPLETION_REPORT.md`
  - `docs/PHASE3_SUMMARY.md`
- Removed empty directories:
  - `src/templates/` (empty)
  - `src/static/` (empty)
- Cleaned Python cache:
  - 53 `__pycache__` directories
  - 402 `.pyc` and `.pyo` files

**Space Saved:** ~36K tracked + cache files

### 🔧 CRITICAL FIX: Django Project Restoration (Oct 17, 2025)
**Issue Discovered:** The `fks_project/` Django configuration directory was accidentally deleted from working tree

**Impact:** 
- Django settings.py missing
- WSGI/ASGI/Celery config missing  
- Project unable to run

**Resolution:**
- Restored via `git restore fks_project/`
- Files restored:
  - fks_project/__init__.py
  - fks_project/settings.py
  - fks_project/urls.py
  - fks_project/wsgi.py
  - fks_project/asgi.py
  - fks_project/celery.py
  - fks_project/trading/models.py
- Also restored start-enhanced.sh
- Cleaned up duplicate root docs (CLEANUP_LOG.md, MIGRATION_MAP.md, PHASE3_SUMMARY.md, PHASE4_5_COMPLETE.md, PHASE4_PROGRESS.md, REFACTOR_PLAN.md)

**Lesson Learned:** Always verify critical Django config files before cleanup commits

## Remaining Legacy Directories to Evaluate

### src/framework/ (928K, 64 Python files)
**Status:** ⚠️ Still has active imports in new apps
**References found in:**
- src/trading_app/engine/_impl.py
- src/api_app/middleware/circuit_breaker/*.py

**Action needed:** Update imports before removal

### src/domain/ (92K)
**Status:** ⚠️ Unclear if fully migrated
**Contains:** analytics, events, market, ml, portfolio, risk, trading

**Action needed:** Verify migration to trading_app

### src/trading/ (380K) - Old Django App
**Status:** ⚠️ Separate from src/trading_app/
**Contains:** models.py, views.py, migrations/, admin.py

**Note:** This is the OLD trading Django app, while `src/trading_app/` is the NEW refactored trading logic. Need to determine if models/migrations are still needed.

### Other Existing Apps (Keep - Active)
- ✅ src/core/ - New core framework
- ✅ src/config_app/ - New config management
- ✅ src/trading_app/ - New trading logic
- ✅ src/api_app/ - New API middleware
- ✅ src/web_app/ - New web interface
- ✅ src/data/ - Data services (existing)
- ⚠️ src/worker/ - **LEGACY microservice (evaluate for removal)**
- ✅ src/chatbot/ - Chatbot (existing)
- ✅ src/rag/ - RAG system (existing)
- ✅ src/forecasting/ - Forecasting (existing)
- ✅ src/engine/ - Engine (existing)
- ⚠️ src/training/ - **LEGACY microservice (evaluate for removal)**
- ⚠️ src/transformer/ - **LEGACY microservice (evaluate for removal)**
- ✅ src/services/ - Services (existing)
- ✅ src/infrastructure/ - Infrastructure (existing)
- ✅ src/staticfiles/ - Collected static files (Django generated)
- ✅ src/logs/ - Log files

### ⚠️ LEGACY MICROSERVICE ARCHITECTURE
**Discovery:** src/worker/, src/transformer/, src/training/ are remnants of OLD microservice architecture

**Evidence:**
- These directories import from `framework.services.template` (old microservice template)
- docker-compose.yml shows `celery -A fks_project worker` (NOT separate microservices)
- Architecture changed: Microservices → Django Monolith + Celery
- No separate service containers in docker-compose for worker/transformer/training

**Current Architecture (docker-compose):**
- `web`: Django app (gunicorn)
- `celery_worker`: Celery worker (NOT src/worker/)
- `celery_beat`: Celery scheduler
- `flower`: Celery monitoring
- `db`: PostgreSQL + TimescaleDB
- `redis`: Redis

**Action Required:**
1. Find Celery task definitions in Django apps (trading_app, api_app, etc.)
2. Verify all worker/transformer/training logic migrated to Celery tasks
3. Remove src/worker/, src/transformer/, src/training/ if confirmed legacy
4. **This represents major architectural shift - document carefully!**

**Potential Space Savings:**
- src/worker/: ~200K estimate
- src/transformer/: ~150K estimate  
- src/training/: ~250K estimate
- **Total: ~600K additional savings**

## Next Cleanup Steps

1. **Fix framework imports** in api_app and trading_app
2. **Verify domain migration** completeness
3. **Evaluate src/trading/** - Determine if models/migrations needed
4. **Remove framework/ and domain/** after fixing imports
5. **Consolidate** or remove old trading app if superseded

## Phase 9A: Legacy Microservices Removed ✅

### Completed: October 17, 2025

**Removed Directories:**
- ✅ src/worker/ (68K, 38 files) - Old worker microservice
- ✅ src/transformer/ (56K, 41 files) - Old ML transformer microservice
- ✅ src/training/ (36K, 19 files) - Old training microservice

**Changes:**
- Removed 98 files, 3,553 lines of code
- Updated fks_project/settings.py - Removed 'src.worker' from INSTALLED_APPS
- Architecture confirmed: Microservices → Django Monolith + Celery
- docker-compose.yml uses celery_worker (NOT these microservice dirs)

**Space Saved:** 160K tracked files

**Commit:** 785b564

---

## Phase 9B: Dead Code Removed ✅

### Completed: October 17, 2025

**Removed Directories:**
- ✅ src/domain/ (92K, 46 files) - Legacy domain logic, never migrated
- ✅ src/data/pipelines/ (20K, 4 files) - Dead code with broken imports

**Analysis:**
- All 6 domain imports were in src/data/pipelines/ only
- src/data/pipelines/ never imported by any other code
- Classes referenced don't exist (MarketDataEvent, ETLPipeline, DataCleaner, etc.)
- Skeleton/placeholder code never implemented

**Changes:**
- Removed 50 files, 3,055 lines of code
- No INSTALLED_APPS changes needed (weren't registered)

**Space Saved:** 112K tracked files

**Commit:** 5476aaa

---

## Status Summary

### Phase 9 Progress: ~60% Complete

**Completed Cleanup:**
- ✅ Old test directories removed (Phase 7)
- ✅ React/TypeScript frontend removed (Phase 6)
- ✅ Old Django project removed (Phase 9 initial)
- ✅ Duplicate docs removed (Phase 9 initial)
- ✅ Empty directories removed (Phase 9 initial)
- ✅ Python cache cleaned (Phase 9 initial)
- 🔧 **CRITICAL: Django config restored** (Phase 9)
- ✅ **Phase 9A: Legacy microservices removed** (160K, 98 files)
- ✅ **Phase 9B: Dead code removed** (112K, 50 files)

**Remaining Work:**
- ⚠️ src/framework/ (928K) - Complex middleware coupling to api_app
- 🔴 src/trading/ (380K) - **CRITICAL: 16 active Celery tasks!**

**Phase 9 Totals:**
- **Files Removed:** 148 files (98 + 50)
- **Lines Deleted:** 6,608 lines (3,553 + 3,055)
- **Space Saved:** 272K tracked files
- **Commits:** 2 (Phase 9A + Phase 9B)

## Remaining Totals

**Still To Remove:**
- src/framework/: 928K (after fixing complex middleware imports)
- src/trading/: 380K (after migrating 16 active Celery tasks)
- **Total Remaining:** ~1.3MB

**Grand Total Achieved + Potential:** ~1.6MB legacy code removal
