# FKS Trading Platform - Architecture Refactoring Plan

**Status**: DRAFT - Do NOT execute until Phase 1 complete  
**Created**: October 18, 2025  
**Target**: Post-production stability (4-6 weeks out)

---

## ⚠️ IMPORTANT: Prerequisites

**DO NOT START THIS REFACTORING UNTIL:**
- [ ] All 34 tests passing (currently 14/34 - 41%)
- [ ] All 16 Celery tasks implemented (currently 0/16)
- [ ] All mock data replaced with real queries (currently 15 TODOs)
- [ ] Test coverage ≥ 80% (currently ~41%)
- [ ] Production deployment successful (not yet attempted)
- [ ] 2+ weeks of stable trading with real data

**Estimated time to prerequisites**: 3-4 weeks

---

## 📊 Current vs. Proposed Structure

### Current Layout (Working, but not optimal)

```
src/
├── api/              # FastAPI routes (legacy, being migrated)
├── authentication/   # User auth, API keys
├── config/           # ❌ Legacy - causes import errors (Issue #48)
├── core/             # Base models, database utils
├── data/             # Providers (Binance, Polygon), adapters
├── framework/        # Reusable middleware, rate limiter, circuit breaker
├── infrastructure/   # External services, exchanges
├── trading/          # Signals, strategies, backtesting, tasks
└── web/              # Django templates, views, RAG system
```

**Problems**:
- Mixed concerns (business logic + infrastructure)
- `config` module conflicts with Django settings
- No clear domain boundaries
- Coupling between `core`, `framework`, `infrastructure`

### Proposed DDD Structure (Target for Phase 3)

```
apps/                          # Bounded contexts (Django apps)
├── trading/                   # Trading domain
│   ├── domain/
│   │   ├── models.py         # Entities: Position, Trade, Signal
│   │   └── value_objects.py  # PositionSize, RiskParams
│   ├── services/
│   │   ├── signal_service.py      # Signal generation logic
│   │   ├── backtest_service.py    # Backtesting engine
│   │   └── optimizer_service.py   # Strategy optimization
│   ├── repositories/
│   │   └── trade_repository.py    # Data access layer
│   ├── api/
│   │   ├── views.py          # REST endpoints
│   │   └── serializers.py    # DRF serializers
│   └── tasks.py              # Celery tasks for trading
│
├── data/                      # Data domain
│   ├── domain/
│   │   └── models.py         # Candle, Tick, Market
│   ├── services/
│   │   ├── provider_service.py    # Adapter orchestration
│   │   └── sync_service.py        # Data synchronization
│   ├── providers/            # External adapters (unchanged)
│   │   ├── binance.py
│   │   ├── polygon.py
│   │   └── alpha_vantage.py
│   └── tasks.py              # Celery tasks for data sync
│
├── intelligence/              # AI/RAG domain (from web/rag/)
│   ├── domain/
│   │   └── models.py         # Document, Embedding, Query
│   ├── services/
│   │   ├── intelligence_orchestrator.py
│   │   ├── embeddings_service.py
│   │   └── document_processor.py
│   ├── llm/
│   │   ├── local_llm.py
│   │   └── openai_fallback.py
│   └── api/
│       └── views.py          # RAG query endpoints
│
├── web/                       # Presentation layer
│   ├── views/
│   │   ├── dashboard.py
│   │   ├── trading.py
│   │   └── performance.py
│   ├── templates/
│   ├── static/
│   └── forms.py
│
└── authentication/            # Auth domain (minimal changes)
    ├── models.py
    ├── services/
    │   └── auth_service.py
    └── middleware/

config/                        # Django settings (NOT src/config/)
├── settings/
│   ├── base.py               # Shared settings
│   ├── development.py        # Local dev (DEBUG=True)
│   ├── production.py         # Production (DEBUG=False)
│   └── testing.py            # Test environment
├── urls.py                   # Root URL config
├── wsgi.py
└── celery.py                 # Celery config

infrastructure/                # Shared infrastructure
├── database/
│   ├── base.py               # Base models, managers
│   └── timescaledb.py        # Hypertable setup
├── cache/
│   └── redis_client.py
└── messaging/
    └── celery_app.py

shared/                        # Cross-cutting concerns (from framework/)
├── middleware/
│   ├── circuit_breaker.py
│   ├── rate_limiter.py
│   └── error_handler.py
├── exceptions/
│   └── base.py               # FKSException hierarchy
└── utils/
    ├── datetime.py
    └── validation.py

tools/                         # Utilities (from scripts/)
├── migration/
├── deployment/
└── analysis/

docs/                          # Documentation (minimal changes)
tests/                         # Tests (mirrors apps/ structure)
monitoring/                    # Prometheus, Grafana (unchanged)
deployment/                    # Docker, nginx (from docker/, nginx/)
notebooks/                     # Experiments (unchanged)
```

---

## 🎯 Migration Strategy

### Phase 3A: Preparation (Week 1)

**Before touching code:**

1. **Create migration branch**
   ```bash
   git checkout -b refactor/ddd-architecture
   ```

2. **Audit current imports**
   ```bash
   # Find all absolute imports
   grep -r "from src\." src/ > /tmp/imports_audit.txt
   grep -r "import src\." src/ >> /tmp/imports_audit.txt
   ```

3. **Document domain boundaries**
   - Map current modules to DDD domains
   - Identify shared code (goes to `shared/`)
   - List external integrations (stays in providers)

4. **Set up import mapper**
   ```python
   # tools/migration/import_mapper.py
   IMPORT_MAP = {
       'src.trading.signals': 'apps.trading.services.signal_service',
       'src.web.rag': 'apps.intelligence.services',
       'config': 'config.settings',  # Fix Issue #48
       # ... 200+ mappings
   }
   ```

### Phase 3B: Incremental Migration (Weeks 2-4)

**One domain at a time, with tests passing after each:**

#### Week 2: Trading Domain
```bash
# 1. Create new structure
mkdir -p apps/trading/{domain,services,repositories,api}

# 2. Move files (preserve git history)
git mv src/trading/models.py apps/trading/domain/models.py
git mv src/trading/signals/generator.py apps/trading/services/signal_service.py
git mv src/trading/backtest/ apps/trading/services/backtest_service.py

# 3. Update imports in moved files
sed -i 's/from src\.trading/from apps.trading/g' apps/trading/**/*.py

# 4. Run tests IMMEDIATELY
pytest tests/unit/test_trading/ -v
# If fails, fix before proceeding
```

#### Week 3: Data Domain
```bash
git mv src/data/models/ apps/data/domain/
git mv src/data/providers/ apps/data/providers/  # Unchanged
# Update imports, test
pytest tests/integration/test_data/ -v
```

#### Week 4: Intelligence Domain
```bash
git mv src/web/rag/ apps/intelligence/
# Update imports, test
pytest tests/unit/test_rag/ -v
```

### Phase 3C: Settings Refactoring (Week 5)

**Split Django settings by environment:**

```python
# config/settings/base.py (common settings)
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent

INSTALLED_APPS = [
    'django.contrib.admin',
    # ... Django apps
    'apps.trading',
    'apps.data',
    'apps.intelligence',
    'apps.web',
    'apps.authentication',
]

# Shared settings...

# config/settings/development.py
from .base import *

DEBUG = True
ALLOWED_HOSTS = ['localhost', '127.0.0.1']

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('DB_NAME', 'trading_db_dev'),
        # ... dev DB config
    }
}

# config/settings/production.py
from .base import *

DEBUG = False
ALLOWED_HOSTS = [os.getenv('ALLOWED_HOST')]

# Production-specific settings
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
# ...
```

**Update manage.py:**
```python
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
```

### Phase 3D: Cleanup (Week 6)

1. **Remove legacy directories**
   ```bash
   git rm -r src/config/  # After fixing all imports
   git rm -r src/infrastructure/  # After moving to infrastructure/
   ```

2. **Consolidate small files**
   ```bash
   # Merge 24 small files (Issue #40)
   # Remove empty __init__.py where unnecessary
   ```

3. **Update documentation**
   - `docs/ARCHITECTURE.md` - New DDD structure
   - `.github/copilot-instructions.md` - Updated paths
   - `README.md` - New quick start

---

## 🧪 Testing Strategy

### Test Coverage Requirements

**Before each migration step:**
```bash
# Baseline coverage
pytest tests/ --cov=src --cov-report=term > /tmp/coverage_before.txt

# After migration
pytest tests/ --cov=apps --cov-report=term > /tmp/coverage_after.txt

# Compare (must be ≥ baseline)
diff /tmp/coverage_before.txt /tmp/coverage_after.txt
```

### Regression Testing

**Critical paths to verify after each domain:**
1. **Trading**: Signal generation → Backtest → Position update
2. **Data**: Market data sync → Indicator calculation → Storage
3. **Intelligence**: Document ingestion → RAG query → Recommendation

```bash
# End-to-end smoke test
pytest tests/integration/test_e2e.py -v --tb=short
```

---

## 📈 Expected Benefits

### Quantified Improvements (Based on DDD Research)

| Metric | Current | Post-Refactor | Improvement |
|--------|---------|---------------|-------------|
| Domain isolation | Low (mixed concerns) | High (bounded contexts) | +40% modularity |
| Test clarity | Medium (integration-heavy) | High (unit testable services) | +30% coverage |
| Onboarding time | 2-3 weeks (complex structure) | 1 week (clear domains) | -50% ramp-up |
| Deployment flexibility | Monolith only | Per-domain possible | +100% options |
| Code navigation | Medium (nested src/) | High (apps/ by domain) | +25% speed |

### Performance Gains

- **Query efficiency**: +20-30% from optimized repositories (select_related)
- **Import speed**: -15% from removing circular dependencies
- **Test execution**: -20% from better isolation (fewer fixtures)

---

## ⚠️ Risks & Mitigations

### Risk 1: Import Breakage
**Likelihood**: High  
**Impact**: Critical  
**Mitigation**:
- Use automated import rewriting tool
- Test after each file move
- Keep old imports as deprecation warnings for 1 release

### Risk 2: Lost Git History
**Likelihood**: Medium  
**Impact**: High  
**Mitigation**:
- Use `git mv` (preserves history)
- Tag pre-refactor state: `git tag pre-ddd-refactor`
- Document moved files in migration log

### Risk 3: Team Disruption
**Likelihood**: Low (solo dev)  
**Impact**: Low  
**Mitigation**:
- Complete in dedicated sprint
- Notify via GitHub discussions

---

## 🚀 Rollout Plan

### Step-by-Step Execution

```bash
# 1. Ensure prerequisites met
pytest tests/ -v  # Must be 34/34 passing
pytest tests/ --cov=src --cov-fail-under=80  # Must pass

# 2. Create feature branch
git checkout -b refactor/ddd-architecture
git tag pre-ddd-refactor  # Safety net

# 3. Phase 3A: Prepare (1 week)
# - Audit imports
# - Document domains
# - Set up tooling

# 4. Phase 3B: Migrate domains (3 weeks)
# Week 2: Trading
# Week 3: Data  
# Week 4: Intelligence

# 5. Phase 3C: Settings split (1 week)

# 6. Phase 3D: Cleanup (1 week)

# 7. Final validation
pytest tests/ --cov=apps --cov-fail-under=80
make lint
docker-compose up --build  # Verify build

# 8. Merge to main
git checkout main
git merge refactor/ddd-architecture
git push origin main
```

---

## 📚 References

### DDD Implementation
- [A Practical Blueprint for DDD in Django](https://medium.com/@hamz.ghp/a-practical-blueprint-for-domain-driven-design-ddd-in-django-projects-2d36652b03b9)
- [Scalable Django Architecture 2025](https://python.plainenglish.io/scalable-django-project-architecture-best-practices-for-2025-6be2f9665f7e)

### Django Best Practices
- [Two Scoops of Django](https://www.feldroy.com/books/two-scoops-of-django-3-x) - Chapter on project layout
- [Django Forum: Project Structure](https://forum.djangoproject.com/t/best-practices-for-structuring-django-projects/39835)

### Migration Tools
- `git mv` - Preserve history
- `sed` - Bulk import updates
- `rope` - Python refactoring library

---

## 🎯 Success Criteria

**Refactoring is complete when:**
- [ ] All 34 tests passing (≥100%)
- [ ] Coverage ≥ 80% (currently ~41%)
- [ ] Import errors = 0
- [ ] Build time ≤ current (no regression)
- [ ] Docker compose up succeeds
- [ ] Health dashboard green
- [ ] Documentation updated
- [ ] Team (you) can navigate confidently

**Timeline**: 6 weeks AFTER Phase 1 & 2 complete

---

## 💡 Alternatives Considered

### Option 1: Full Polyrepo Split
**Pros**: Maximum isolation, independent deploys  
**Cons**: Overhead for solo dev, shared code duplication  
**Decision**: Defer until team size > 3

### Option 2: Incremental Modularization (NO DDD)
**Pros**: Less disruption, gradual improvement  
**Cons**: Doesn't solve root coupling issues  
**Decision**: Partial approach (fix imports first)

### Option 3: Stay As-Is
**Pros**: Zero refactoring cost  
**Cons**: Tech debt compounds, scalability limits  
**Decision**: Rejected - current issues justify change

---

**Status**: DRAFT - Review after Phase 1 complete  
**Next Review**: 4 weeks from now (Week of Nov 15, 2025)  
**Owner**: Jordan (solo dev)
