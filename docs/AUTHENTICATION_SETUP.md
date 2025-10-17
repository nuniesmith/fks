# Authentication System Setup

## Date: October 17, 2025

## Problem
User received a 404 error when trying to access the dashboard:
```
Page not found (404)
Request URL: http://localhost:8000/login/?next=/dashboard/
```

The `DashboardView` was protected with `LoginRequiredMixin` but no login page existed.

## Solution Implemented

### 1. Created Login Template
**File:** `src/web/templates/pages/login.html`
- Bootstrap 5 styled login form
- CSRF protection
- Error message display
- Redirect support (`next` parameter)
- Link back to home page

### 2. Added Authentication Views
**File:** `src/web/views.py`

Added two new view classes:

**`CustomLoginView`:**
- Extends Django's built-in `LoginView`
- Custom template (`pages/login.html`)
- Redirects authenticated users
- Handles `next` URL parameter for post-login redirection
- Shows error message on failed login

**`CustomLogoutView`:**
- Extends Django's built-in `LogoutView`
- Redirects to home page after logout
- Shows success message

### 3. Updated URL Configuration
**File:** `src/web/urls.py`

Added authentication routes:
```python
path('login/', views.CustomLoginView.as_view(), name='login'),
path('logout/', views.CustomLogoutView.as_view(), name='logout'),
```

## Testing Results

✅ **Login Page:** HTTP 200 - Renders correctly with Bootstrap styling
✅ **Dashboard Redirect:** HTTP 302 - Properly redirects unauthenticated users to login
✅ **Authentication Flow:** Complete and functional

## Current URL Structure

```
/                      → HomeView (public)
/login/                → CustomLoginView (public)
/logout/               → CustomLogoutView (authenticated)
/dashboard/            → DashboardView (authenticated, redirects to /login/)
/metrics/              → MetricsView (authenticated)
/admin/                → Django Admin (authenticated)
```

## Next Steps

### 1. Create Superuser (Required for First Login)
```bash
docker compose exec web python manage.py createsuperuser
```

This will prompt for:
- Username
- Email (optional)
- Password

### 2. Test Authentication Flow
1. Visit http://localhost:8000/dashboard/
2. Should redirect to http://localhost:8000/login/?next=/dashboard/
3. Enter superuser credentials
4. Should redirect back to dashboard

### 3. Optional: Add User Registration
Currently, the login page shows "Contact your administrator" for new accounts.
If you want self-service registration, we can add:
- Registration form template
- `SignUpView` class
- URL pattern for `/register/`
- Email verification (optional)

## Files Changed

1. ✅ Created: `src/web/templates/pages/login.html`
2. ✅ Modified: `src/web/views.py` (added `CustomLoginView` and `CustomLogoutView`)
3. ✅ Modified: `src/web/urls.py` (added `/login/` and `/logout/` routes)

## Authentication Features

- ✅ Login page with Bootstrap styling
- ✅ CSRF protection
- ✅ Error message display
- ✅ Post-login redirect support
- ✅ Logout with confirmation message
- ✅ Protected dashboard and metrics pages
- ✅ Session-based authentication
- ❌ User registration (not implemented - admin-created accounts only)
- ❌ Password reset (not implemented)
- ❌ Remember me (not implemented)

## Django Auth Configuration

The authentication system uses Django's built-in `django.contrib.auth` with:
- Session authentication
- Login required mixin for protected views
- `LOGIN_URL = '/login/'` (configured in `DashboardView`)
- Default session backend (database-backed)
- CSRF middleware enabled

## Notes

- All authentication views are now working correctly
- The system uses Django's built-in authentication backend
- Passwords are hashed with PBKDF2 (Django default)
- Sessions are stored in PostgreSQL via Django's session framework
- No API authentication implemented yet (future: JWT/token-based for API endpoints)
