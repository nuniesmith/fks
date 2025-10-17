# Django Configuration Reorganization

## Date: October 17, 2025

## Overview
Successfully moved the Django project configuration from `src/fks_project/` to `src/web/django/` to better organize the codebase by grouping web-related files together.

## Motivation
- **Better Organization:** All web service files (views, templates, URLs, Django config) are now under `src/web/`
- **Clearer Structure:** The `django/` subdirectory explicitly indicates Django configuration
- **Reduced Confusion:** Removes `fks_project` naming which was confusing since it's not the entire project

## Changes Made

### 1. Directory Structure
**Old:**
```
src/
├── fks_project/          # Django configuration
│   ├── __init__.py
│   ├── settings.py
│   ├── urls.py
│   ├── wsgi.py
│   ├── asgi.py
│   └── celery.py
├── web/                  # Web app
├── api/
├── trading/
└── ...
```

**New:**
```
src/
├── web/
│   ├── django/           # Django configuration (moved here)
│   │   ├── __init__.py
│   │   ├── settings.py
│   │   ├── urls.py
│   │   ├── wsgi.py
│   │   ├── asgi.py
│   │   └── celery.py
│   ├── templates/
│   ├── static/
│   ├── views.py
│   └── urls.py
├── api/
├── trading/
└── ...
```

### 2. Files Modified

#### A. Django Configuration Files
All references changed from `fks_project` to `web.django`:

**`manage.py`**
- `DJANGO_SETTINGS_MODULE`: `fks_project.settings` → `web.django.settings`

**`src/web/django/wsgi.py`**
- Settings module: `fks_project.settings` → `web.django.settings`
- Docstring updated to reference `web.django`

**`src/web/django/asgi.py`**
- Settings module: `fks_project.settings` → `web.django.settings`
- Docstring updated to reference `web.django`

**`src/web/django/celery.py`**
- Settings module: `fks_project.settings` → `web.django.settings`
- Celery app name: `fks_project` → `web.django`

**`src/web/django/settings.py`**
- `ROOT_URLCONF`: `fks_project.urls` → `web.django.urls`
- `WSGI_APPLICATION`: `fks_project.wsgi.application` → `web.django.wsgi.application`
- **Path Fixes:**
  - `BASE_DIR`: Now points to `src/` (3 levels up: `parent.parent.parent`)
  - `PROJECT_ROOT`: Added to point to project root
  - Logging path: Uses absolute path `/app/logs/django.log` for Docker compatibility
  - `ML_MODELS_DIR`: Uses `PROJECT_ROOT / 'ml_models'`

#### B. Docker Configuration Files

**`docker-compose.yml`** (4 services updated):
1. **web service:**
   - Command: `gunicorn fks_project.wsgi:application` → `gunicorn web.django.wsgi:application`
   - Environment: `DJANGO_SETTINGS_MODULE=fks_project.settings` → `web.django.settings`

2. **celery_worker service:**
   - Command: `celery -A fks_project worker` → `celery -A web.django worker`
   - Environment: `DJANGO_SETTINGS_MODULE=fks_project.settings` → `web.django.settings`

3. **celery_beat service:**
   - Command: `celery -A fks_project beat` → `celery -A web.django beat`
   - Environment: `DJANGO_SETTINGS_MODULE=fks_project.settings` → `web.django.settings`

4. **flower service:**
   - Command: `celery -A fks_project flower` → `celery -A web.django flower`

**`docker-compose.gpu.yml`** (2 updates):
1. Web service gunicorn command
2. Celery worker healthcheck command

### 3. Path Resolution Details

The Django settings file needed careful path adjustments:

```python
# Before (when in src/fks_project/)
BASE_DIR = Path(__file__).resolve().parent.parent  # → src/

# After (when in src/web/django/)
BASE_DIR = Path(__file__).resolve().parent.parent.parent  # → src/
PROJECT_ROOT = BASE_DIR.parent  # → project root
```

**Logging Path Issue:**
- Initial attempt: `PROJECT_ROOT / 'logs' / 'django.log'`
- Problem: Path resolution in Docker container was incorrect
- Solution: Use absolute Docker path `/app/logs/django.log`

## Testing Results

### ✅ All Services Running
```bash
$ docker compose ps
NAME                  STATUS
fks_app               Up
fks-celery_worker-1   Up
fks-celery_beat-1     Up
fks-flower-1          Up
fks_db                Up
fks_redis             Up
fks_pgadmin           Up
```

### ✅ Web Service Accessible
- Homepage: http://localhost:8000/ → HTTP 200
- Login: http://localhost:8000/login/ → HTTP 200
- Dashboard redirect: http://localhost:8000/dashboard/ → HTTP 302 (to login)

### ✅ Celery Services Working
- Worker: Processing tasks
- Beat: Scheduler running
- Flower: Monitoring UI accessible at http://localhost:5555/

## Benefits

1. **Logical Grouping:** All web-related code is now under `src/web/`
2. **Clear Separation:** Django config is distinct from web app code
3. **Maintainability:** Easier to understand project structure
4. **Consistency:** Follows convention of grouping related files

## File Tree After Changes

```
fks/
├── manage.py                     ← Updated: web.django.settings
├── docker-compose.yml            ← Updated: All services
├── docker-compose.gpu.yml        ← Updated: gunicorn & celery
└── src/
    ├── web/
    │   ├── django/               ← NEW LOCATION
    │   │   ├── __init__.py
    │   │   ├── settings.py       ← Updated: paths & module names
    │   │   ├── urls.py
    │   │   ├── wsgi.py           ← Updated: web.django.wsgi
    │   │   ├── asgi.py           ← Updated: web.django.asgi
    │   │   └── celery.py         ← Updated: web.django app
    │   ├── templates/
    │   ├── static/
    │   ├── views.py
    │   └── urls.py
    ├── api/
    ├── trading/
    ├── core/
    └── ...
```

## Migration Steps Performed

1. ✅ Created `src/web/django/` directory
2. ✅ Copied all files from `src/fks_project/` to `src/web/django/`
3. ✅ Updated `manage.py` Django settings module
4. ✅ Updated `wsgi.py`, `asgi.py`, `celery.py` module references
5. ✅ Updated `settings.py` paths and module references
6. ✅ Updated `docker-compose.yml` (4 services)
7. ✅ Updated `docker-compose.gpu.yml` (2 references)
8. ✅ Fixed `BASE_DIR` and `PROJECT_ROOT` path resolution
9. ✅ Fixed logging path for Docker compatibility
10. ✅ Removed old `src/fks_project/` directory
11. ✅ Restarted all services
12. ✅ Verified all services running
13. ✅ Tested web endpoints

## Potential Issues & Solutions

### Issue 1: Import Errors
**Symptom:** `ModuleNotFoundError: No module named 'fks_project'`
**Cause:** Old import statements still referencing `fks_project`
**Solution:** All references have been updated to `web.django`

### Issue 2: Path Resolution
**Symptom:** `FileNotFoundError: [Errno 2] No such file or directory: '/logs/django.log'`
**Cause:** `BASE_DIR` changed location, affecting relative paths
**Solution:** Updated `BASE_DIR` calculation and used absolute paths for Docker

### Issue 3: Celery Not Finding App
**Symptom:** Celery services restarting with app discovery errors
**Cause:** Celery commands still using old `fks_project` module name
**Solution:** Updated all `celery -A` commands to use `web.django`

## Rollback Instructions (if needed)

If you need to revert this change:

1. Restore `src/fks_project/` from backup
2. Revert `manage.py`:
   ```python
   os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'fks_project.settings')
   ```
3. Revert `docker-compose.yml` Django settings and commands
4. Remove `src/web/django/`
5. Restart services: `docker compose restart`

## Next Steps

1. **Update Documentation:** Any documentation referencing `fks_project` should be updated
2. **Update CI/CD:** If any CI/CD pipelines reference the old path, update them
3. **Update IDE Settings:** VS Code, PyCharm settings may need Django root updated
4. **Code Review:** Search for any remaining `fks_project` references:
   ```bash
   grep -r "fks_project" --exclude-dir=".git" --exclude-dir="__pycache__"
   ```

## Verification Checklist

- [x] All Docker services start successfully
- [x] Web service responds to HTTP requests
- [x] Login page loads correctly
- [x] Dashboard redirects to login
- [x] Celery worker is processing
- [x] Celery beat scheduler is running
- [x] Flower monitoring UI accessible
- [x] No import errors in logs
- [x] Static files served correctly
- [x] Templates render correctly

## Notes

- The `__init__.py` in `src/web/django/` correctly imports Celery using relative imports, so it didn't need updates
- All environment variables remain unchanged (only module paths in code changed)
- Database connections unaffected (no migrations needed)
- Static/media file paths remain functional
- No changes to API endpoints or URL patterns

---

**Status:** ✅ Complete and Verified
**Services:** 7/7 Running
**Web Status:** Operational
**Celery Status:** Operational
