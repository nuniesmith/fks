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

## Status
- ✅ Old test directories removed (Phase 7)
- ✅ React/TypeScript frontend removed (Phase 6)  
- ⏳ Framework directory - pending import fixes
- ⏳ Domain directory - pending import fixes
- ✅ Django directory - safe to remove
- ⏳ Old docs - optional cleanup
