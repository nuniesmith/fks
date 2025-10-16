# FKS Project Refactoring Plan

**Date:** October 16, 2025  
**Goal:** Transform FKS from a fragmented Django+React hybrid into a clean, modular Django-centric trading platform

## Executive Summary

This refactor will:
- ✅ Eliminate React/Node.js frontend (convert to Django templates)
- ✅ Consolidate fragmented Django structure into proper apps
- ✅ Remove duplicates and backup files
- ✅ Implement clean separation of concerns
- ✅ Reduce tech stack complexity by ~40%
- ✅ Improve maintainability and testing

**Estimated Timeline:** 2-4 weeks  
**Risk Level:** Medium (mitigated by incremental approach)

---

## Phase 1: Preparation & Analysis ✓

### Current State Analysis

**Existing Django Apps (in src/django/fks_project/):**
- `trading` - Trading logic
- `forecasting` - ML forecasting
- `chatbot` - Chat interface
- `rag` - RAG system

**Issues Identified:**

1. **Duplicates Found:**
   - `src/data/adapters/binance.py` vs `binance_new.py` (identical except newline)
   - `src/data/adapters/binance.py.bak` (backup file)
   - Multiple Binance references across adapters/providers

2. **Structural Problems:**
   - Django project isolated in `src/django/fks_project/`
   - React frontend in `src/web/` with full TSX/Vite setup
   - Deep nesting: `framework/middleware/rate_limiter/algorithms/`
   - Scattered tests: `src/tests/`, `src/data/tests/`

3. **Frontend Complexity:**
   - 30+ React components (TSX)
   - Vite build system
   - Complex state management (contexts, stores)
   - Misaligned with Python backend

### Git Status
- Uncommitted changes present (will commit before refactor)
- Branch: main
- Clean working tree needed before proceeding

---

## Phase 2: Clean Duplicates & Backups

### Actions

1. **Delete Backup Files:**
   ```bash
   rm src/data/adapters/binance.py.bak
   ```

2. **Merge Duplicate Binance Adapters:**
   - Keep: `binance.py` (has proper newline)
   - Delete: `binance_new.py`
   - Update imports in `__init__.py`

3. **Consolidate Logging:**
   - Merge `data/app_logging.py` + `worker/fks_logging.py`
   - Create: `core/utils/logging.py`

4. **Audit Static Files:**
   - Check if `staticfiles/admin/` is needed
   - Check if `staticfiles/rest_framework/` is needed
   - Remove unused Django admin assets if not using full admin

### Verification
- Run tests after each deletion
- Ensure no broken imports

---

## Phase 3: Create New Django App Structure

### Target Structure

```
fks/
├── manage.py                    # Move from src/django/fks_project/
├── fks_project/                 # Main Django project (from src/django/fks_project/)
│   ├── __init__.py
│   ├── settings.py
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
├── apps/                        # All Django apps go here
│   ├── core/                    # Base framework (NEW)
│   │   ├── __init__.py
│   │   ├── apps.py
│   │   ├── admin.py
│   │   ├── models.py            # Base models
│   │   ├── migrations/
│   │   ├── exceptions/          # From src/exceptions/
│   │   ├── utils/               # Helpers, logging
│   │   ├── metrics/             # From src/framework/metrics/
│   │   └── registry.py
│   ├── config/                  # Config management (NEW)
│   │   ├── __init__.py
│   │   ├── apps.py
│   │   ├── schema/              # Validators
│   │   ├── providers/           # Env, file providers
│   │   └── manager.py
│   ├── data/                    # Data handling (MIGRATE from src/data/)
│   │   ├── __init__.py
│   │   ├── apps.py
│   │   ├── admin.py
│   │   ├── models.py            # Candle, Tick models
│   │   ├── migrations/
│   │   ├── adapters/            # API adapters (cleaned)
│   │   ├── providers/           # Data providers
│   │   ├── pipelines/           # ETL
│   │   ├── storage/             # Store, cache
│   │   └── tests/
│   ├── trading/                 # Trading logic (EXISTING + MERGE)
│   │   ├── __init__.py
│   │   ├── apps.py
│   │   ├── admin.py
│   │   ├── models.py
│   │   ├── migrations/
│   │   ├── strategies/          # From src/domain/trading/strategies/
│   │   ├── indicators/          # From src/indicators/
│   │   ├── backtest/            # From src/backtest.py, src/engine/
│   │   ├── execution/
│   │   └── tests/
│   ├── api/                     # REST API (NEW)
│   │   ├── __init__.py
│   │   ├── apps.py
│   │   ├── routes.py            # API routes
│   │   ├── middleware/          # Auth, rate limiting
│   │   ├── serializers.py
│   │   └── tests/
│   ├── web/                     # UI/Frontend (NEW - replaces React)
│   │   ├── __init__.py
│   │   ├── apps.py
│   │   ├── views.py             # Page views
│   │   ├── urls.py              # UI routes
│   │   ├── templates/           # Django HTML templates
│   │   │   ├── base.html
│   │   │   ├── components/      # Reusable HTML
│   │   │   └── pages/           # Dashboard, strategy pages
│   │   ├── static/              # CSS/JS (minimal)
│   │   │   ├── css/
│   │   │   └── js/
│   │   ├── forms.py
│   │   └── tests/
│   ├── worker/                  # Celery tasks (EXISTING - migrate)
│   │   ├── __init__.py
│   │   ├── apps.py
│   │   ├── tasks/
│   │   ├── scheduler/
│   │   └── tests/
│   ├── forecasting/             # ML forecasting (EXISTING)
│   ├── chatbot/                 # Chatbot (EXISTING)
│   └── rag/                     # RAG system (EXISTING)
├── tests/                       # Root-level tests
│   ├── __init__.py
│   ├── conftest.py
│   ├── unit/
│   └── integration/
├── docs/
├── scripts/
├── sql/
├── docker/
├── requirements.txt
└── README.md
```

### New Apps to Create

1. **core** - Base framework
2. **config** - Configuration management
3. **api** - REST API
4. **web** - UI (Django templates)

### Steps

```bash
# Move to root first
cd /mnt/c/Users/jordan/nextcloud/code/repos/fks

# Create apps directory
mkdir -p apps

# Create new Django apps
cd apps
django-admin startapp core
django-admin startapp config
django-admin startapp api
django-admin startapp web
```

---

## Phase 4: Migrate Existing Code

### 4.1 Move Domain Logic to Core

**From:** `src/domain/`  
**To:** `apps/core/`

Files to migrate:
- `domain/entities/` → `core/models.py` (as Django models)
- `domain/value_objects/` → `core/models.py` or `core/utils/`
- `domain/exceptions/` → `core/exceptions/`

### 4.2 Move Framework to Config

**From:** `src/framework/config/`  
**To:** `apps/config/`

Files to migrate:
- `framework/config/manager.py` → `config/manager.py`
- `framework/config/schema/` → `config/schema/`
- `framework/config/providers/` → `config/providers/`

### 4.3 Consolidate Data App

**From:** `src/data/`  
**To:** `apps/data/`

Steps:
1. Copy entire `src/data/` to `apps/data/`
2. Add Django app structure (`apps.py`, `admin.py`, `migrations/`)
3. Convert models to Django ORM if needed
4. Delete duplicates (binance_new.py, .bak files)

### 4.4 Merge Trading Logic

**From:** `src/domain/trading/`, `src/indicators/`, `src/backtest.py`, `src/engine/`  
**To:** `apps/trading/`

Organization:
- `domain/trading/strategies/` → `trading/strategies/`
- `indicators/` → `trading/indicators/`
- `backtest.py` + `engine/backtest/` → `trading/backtest/`
- `domain/trading/execution/` → `trading/execution/`

### 4.5 Create API App

**From:** `src/domain/trading/api/`, `src/framework/middleware/`  
**To:** `apps/api/`

Structure:
- `domain/trading/api/routes/` → `api/routes.py`
- `framework/middleware/auth/` → `api/middleware/auth.py`
- `framework/middleware/rate_limiter/` → `api/middleware/rate_limiter.py`

### 4.6 Migrate Worker

**From:** `src/worker/`  
**To:** `apps/worker/`

Steps:
1. Copy `src/worker/` to `apps/worker/`
2. Add Django app structure
3. Keep Celery tasks as-is
4. Update imports

### 4.7 Keep Existing Django Apps

These apps are already good:
- `forecasting` → move to `apps/forecasting/`
- `chatbot` → move to `apps/chatbot/`
- `rag` → move to `apps/rag/`

---

## Phase 5: Move Django Project to Root

### Steps

1. **Move Django Project:**
   ```bash
   cp -r src/django/fks_project/* ./
   # Result: manage.py, fks_project/ at root
   ```

2. **Update settings.py:**
   ```python
   INSTALLED_APPS = [
       'django.contrib.admin',
       'django.contrib.auth',
       'django.contrib.contenttypes',
       'django.contrib.sessions',
       'django.contrib.messages',
       'django.contrib.staticfiles',
       
       # Third-party
       'rest_framework',
       'corsheaders',
       'django_celery_beat',
       'django_celery_results',
       
       # Local apps (NEW)
       'apps.core.apps.CoreConfig',
       'apps.config.apps.ConfigConfig',
       'apps.data.apps.DataConfig',
       'apps.trading.apps.TradingConfig',
       'apps.api.apps.ApiConfig',
       'apps.web.apps.WebConfig',
       'apps.worker.apps.WorkerConfig',
       'apps.forecasting.apps.ForecastingConfig',
       'apps.chatbot.apps.ChatbotConfig',
       'apps.rag.apps.RagConfig',
   ]
   
   TEMPLATES = [
       {
           'BACKEND': 'django.template.backends.django.DjangoTemplates',
           'DIRS': [BASE_DIR / 'apps/web/templates'],
           'APP_DIRS': True,
           ...
       },
   ]
   
   STATICFILES_DIRS = [
       BASE_DIR / 'apps/web/static',
   ]
   ```

3. **Update ROOT_URLCONF:**
   ```python
   # fks_project/urls.py
   urlpatterns = [
       path('admin/', admin.site.urls),
       path('api/', include('apps.api.urls')),
       path('', include('apps.web.urls')),
   ]
   ```

---

## Phase 6: Convert React Frontend to Django Templates

### 6.1 Analysis of React Components

**Current React Components (src/web/components/):**
- `TradingDashboard.tsx` - Main dashboard
- `TradingChart.tsx` - Chart display
- `NotificationSystem.tsx` - Alerts
- `ThemeProvider.tsx` / `ThemeToggle.tsx` - Dark mode
- `ModernCard.tsx`, `ModernHeader.tsx`, `ModernNavigation.tsx` - UI components
- `ErrorBoundary.tsx` - Error handling
- Plus 20+ more components

**Conversion Strategy:**
- Dashboard → `apps/web/templates/pages/dashboard.html`
- Charts → Use Chart.js directly in HTML
- Notifications → Django messages framework
- Theme → CSS variables + localStorage JS
- Components → Reusable Django template includes

### 6.2 Create Base Template

**File:** `apps/web/templates/base.html`

```html
<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}FKS Trading Platform{% endblock %}</title>
    
    <!-- Bootstrap CSS -->
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    
    <!-- Chart.js -->
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
    
    <!-- Custom CSS -->
    <link rel="stylesheet" href="{% static 'css/main.css' %}">
    
    {% block extra_head %}{% endblock %}
</head>
<body>
    <!-- Navigation -->
    {% include 'components/navigation.html' %}
    
    <!-- Messages/Notifications -->
    {% if messages %}
    <div class="container mt-3">
        {% for message in messages %}
        <div class="alert alert-{{ message.tags }} alert-dismissible fade show" role="alert">
            {{ message }}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
        {% endfor %}
    </div>
    {% endif %}
    
    <!-- Main Content -->
    <main class="container-fluid">
        {% block content %}{% endblock %}
    </main>
    
    <!-- Footer -->
    {% include 'components/footer.html' %}
    
    <!-- Bootstrap JS -->
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    
    <!-- Theme Toggle -->
    <script src="{% static 'js/theme.js' %}"></script>
    
    {% block extra_js %}{% endblock %}
</body>
</html>
```

### 6.3 Convert Key Pages

**Dashboard Page:**

**From:** `src/web/components/TradingDashboard.tsx`  
**To:** `apps/web/templates/pages/dashboard.html`

```html
{% extends 'base.html' %}
{% load static %}

{% block title %}Trading Dashboard - FKS{% endblock %}

{% block content %}
<div class="row">
    <!-- Portfolio Summary -->
    <div class="col-md-4">
        {% include 'components/portfolio_card.html' %}
    </div>
    
    <!-- Charts -->
    <div class="col-md-8">
        {% include 'components/trading_chart.html' %}
    </div>
</div>

<div class="row mt-4">
    <!-- Recent Signals -->
    <div class="col-md-6">
        {% include 'components/signals_table.html' %}
    </div>
    
    <!-- Active Positions -->
    <div class="col-md-6">
        {% include 'components/positions_table.html' %}
    </div>
</div>
{% endblock %}

{% block extra_js %}
<script src="{% static 'js/dashboard.js' %}"></script>
{% endblock %}
```

**View:**

```python
# apps/web/views.py
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from apps.trading.models import Signal, Position
from apps.data.models import Candle

@login_required
def dashboard(request):
    context = {
        'recent_signals': Signal.objects.filter(user=request.user)[:10],
        'active_positions': Position.objects.filter(user=request.user, status='open'),
        'portfolio_value': calculate_portfolio_value(request.user),
    }
    return render(request, 'pages/dashboard.html', context)
```

### 6.4 Replace React Hooks with Django Views

**React State Management → Django Context:**

| React | Django Equivalent |
|-------|------------------|
| `useState` | Context variables passed to template |
| `useEffect` | Server-side data fetching in view |
| `useContext` | Template context processors |
| `useCallback` | View functions |
| API calls | Direct Django ORM queries |

**Example:**

**React (OLD):**
```tsx
const [signals, setSignals] = useState([]);
useEffect(() => {
    fetchSignals().then(data => setSignals(data));
}, []);
```

**Django (NEW):**
```python
# View automatically fetches on page load
signals = Signal.objects.filter(user=request.user)
return render(request, 'dashboard.html', {'signals': signals})
```

### 6.5 Interactive Elements

For real-time features (charts, live prices), use:

1. **Chart.js** - Client-side charting
2. **HTMX** - Partial page updates (optional)
3. **Vanilla JS** - Simple interactivity
4. **Django Channels** - WebSocket (if needed for live data)

**Example - Live Chart Update:**

```javascript
// apps/web/static/js/dashboard.js
function updateChart() {
    fetch('/api/latest-candles/')
        .then(response => response.json())
        .then(data => {
            chart.data.datasets[0].data = data;
            chart.update();
        });
}

setInterval(updateChart, 5000); // Update every 5 seconds
```

### 6.6 Delete React Codebase

After conversion is complete and tested:

```bash
rm -rf src/web/components/
rm -rf src/web/pages/
rm -rf src/web/hooks/
rm -rf src/web/context/
rm -rf src/web/node_modules/
rm src/web/package.json
rm src/web/vite.config.ts
rm src/web/tsconfig.json
```

---

## Phase 7: Consolidate Tests

### Current Test Structure

- `src/tests/` - Root tests
- `src/data/tests/` - Data tests
- Various test files scattered

### Target Structure

```
tests/
├── __init__.py
├── conftest.py              # Pytest fixtures
├── unit/
│   ├── test_core.py
│   ├── test_data.py
│   ├── test_trading.py
│   └── test_api.py
└── integration/
    ├── test_data_pipeline.py
    ├── test_trading_flow.py
    └── test_api_endpoints.py
```

### Steps

1. **Move all tests to root `tests/`:**
   ```bash
   mv src/tests/* tests/unit/
   mv src/data/tests/* tests/unit/
   ```

2. **Update test imports:**
   ```python
   # OLD
   from src.data.adapters import BinanceAdapter
   
   # NEW
   from apps.data.adapters import BinanceAdapter
   ```

3. **Create conftest.py:**
   ```python
   # tests/conftest.py
   import pytest
   from django.test import Client
   
   @pytest.fixture
   def client():
       return Client()
   
   @pytest.fixture
   def sample_candle():
       from apps.data.models import Candle
       return Candle.objects.create(...)
   ```

4. **Run tests:**
   ```bash
   pytest tests/ -v
   coverage run -m pytest
   coverage report
   ```

**Target:** 80%+ test coverage

---

## Phase 8: Update Configuration & Dependencies

### 8.1 Update requirements.txt

**Remove:**
```
# Node.js-related packages (none expected, but check)
```

**Add:**
```
Django>=4.2.0
django-bootstrap5>=23.3
channels>=4.0.0  # If using WebSocket
```

**Keep:**
```
celery
redis
psycopg2-binary
pandas
numpy
scikit-learn
torch
transformers
```

### 8.2 Update settings.py

Full updated settings:

```python
# fks_project/settings.py

INSTALLED_APPS = [
    # Django
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Third-party
    'rest_framework',
    'corsheaders',
    'django_celery_beat',
    'django_celery_results',
    'channels',  # If using WebSocket
    
    # Local apps
    'apps.core',
    'apps.config',
    'apps.data',
    'apps.trading',
    'apps.api',
    'apps.web',
    'apps.worker',
    'apps.forecasting',
    'apps.chatbot',
    'apps.rag',
]

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'apps/web/templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'apps/web/static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
```

### 8.3 Update Import Paths

Create a script to update imports:

```python
# scripts/update_imports.py
import os
import re

def update_imports(file_path):
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Update import patterns
    content = re.sub(r'from src\.data', 'from apps.data', content)
    content = re.sub(r'from src\.domain', 'from apps.core', content)
    content = re.sub(r'from src\.framework', 'from apps.config', content)
    
    with open(file_path, 'w') as f:
        f.write(content)

# Run on all Python files
for root, dirs, files in os.walk('apps'):
    for file in files:
        if file.endswith('.py'):
            update_imports(os.path.join(root, file))
```

---

## Phase 9: Testing & Validation

### 9.1 Pre-Launch Checklist

- [ ] All imports updated
- [ ] All tests passing
- [ ] Migrations created and applied
- [ ] Static files collected
- [ ] Admin interface working
- [ ] API endpoints responding
- [ ] UI pages rendering
- [ ] Celery tasks running
- [ ] Database connections working

### 9.2 Test Commands

```bash
# Run migrations
python manage.py makemigrations
python manage.py migrate

# Collect static files
python manage.py collectstatic --noinput

# Run tests
pytest tests/ -v
python manage.py test

# Check for issues
python manage.py check
python manage.py check --deploy

# Start development server
python manage.py runserver
```

### 9.3 Smoke Tests

1. **Visit pages:**
   - http://localhost:8000/ (Dashboard)
   - http://localhost:8000/admin/
   - http://localhost:8000/api/

2. **Test API:**
   ```bash
   curl http://localhost:8000/api/signals/
   curl http://localhost:8000/api/positions/
   ```

3. **Test Celery:**
   ```bash
   celery -A fks_project worker --loglevel=info
   celery -A fks_project beat --loglevel=info
   ```

---

## Phase 10: Documentation & Deployment

### 10.1 Update README.md

```markdown
# FKS Trading Platform

## Architecture

- **Backend:** Django 4.2+ (Python)
- **Database:** PostgreSQL + TimescaleDB
- **Cache:** Redis
- **Tasks:** Celery
- **UI:** Server-rendered Django templates (HTML/CSS/JS)

## Project Structure

```
fks/
├── manage.py
├── fks_project/          # Django project
├── apps/                 # Django apps
│   ├── core/            # Base framework
│   ├── data/            # Data handling
│   ├── trading/         # Trading logic
│   ├── api/             # REST API
│   ├── web/             # UI templates
│   └── worker/          # Celery tasks
└── tests/               # Unit & integration tests
```

## Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Start server
python manage.py runserver
```
```

### 10.2 Update Docker Configuration

**Dockerfile:**
```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Collect static files
RUN python manage.py collectstatic --noinput

CMD ["gunicorn", "fks_project.wsgi:application", "--bind", "0.0.0.0:8000"]
```

**docker-compose.yml:**
```yaml
version: '3.8'

services:
  web:
    build: .
    command: gunicorn fks_project.wsgi:application --bind 0.0.0.0:8000
    volumes:
      - .:/app
    ports:
      - "8000:8000"
    depends_on:
      - db
      - redis
    env_file:
      - .env
  
  db:
    image: timescale/timescaledb:latest-pg15
    volumes:
      - postgres_data:/var/lib/postgresql/data
    environment:
      - POSTGRES_DB=trading_db
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=postgres
  
  redis:
    image: redis:7-alpine
  
  celery_worker:
    build: .
    command: celery -A fks_project worker --loglevel=info
    depends_on:
      - redis
      - db
    env_file:
      - .env
  
  celery_beat:
    build: .
    command: celery -A fks_project beat --loglevel=info
    depends_on:
      - redis
      - db
    env_file:
      - .env

volumes:
  postgres_data:
```

### 10.3 Create Migration Guide

**File:** `docs/MIGRATION_GUIDE.md`

Document:
- What changed
- How to migrate custom code
- Breaking changes
- New patterns to follow

---

## Timeline & Milestones

| Phase | Duration | Milestone |
|-------|----------|-----------|
| 1. Preparation | 1 day | Analysis complete, backups created |
| 2. Clean Duplicates | 1 day | All duplicates removed, tests pass |
| 3. Create Apps | 2 days | New Django apps scaffolded |
| 4. Migrate Code | 5 days | All code moved to new structure |
| 5. Move Django Root | 1 day | Django project at root, imports updated |
| 6. Convert Frontend | 5 days | React replaced with Django templates |
| 7. Consolidate Tests | 2 days | All tests in one place, 80%+ coverage |
| 8. Update Config | 1 day | Dependencies updated, settings correct |
| 9. Testing | 3 days | Full QA, smoke tests, bug fixes |
| 10. Documentation | 2 days | README, docs, deployment guide |

**Total:** ~3 weeks (15 working days)

---

## Risk Mitigation

1. **Git Branching:**
   - Create `refactor` branch
   - Commit after each phase
   - Merge to `main` only after full testing

2. **Incremental Testing:**
   - Run tests after each file move
   - Keep old structure until new one works
   - Use symlinks temporarily if needed

3. **Rollback Plan:**
   - Keep backup branch
   - Document each change
   - Can revert to old structure if critical bugs

4. **Performance:**
   - Profile before/after
   - Monitor query counts
   - Cache aggressively

---

## Success Criteria

- ✅ Zero Node.js dependencies
- ✅ All code in proper Django apps
- ✅ No duplicate files
- ✅ 80%+ test coverage
- ✅ All features working
- ✅ <2s page load times
- ✅ Clean `git diff` history
- ✅ Complete documentation

---

## Next Steps

1. **Commit current changes** to save work
2. **Create refactor branch**
3. **Start Phase 2** (Clean duplicates)
4. **Execute plan incrementally**

---

**Questions or Concerns?**

This plan is designed to be flexible. Adjust timelines as needed, but maintain the incremental approach for safety.
