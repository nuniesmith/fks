# 🔐 Authentication System - Quick Reference

## 🚀 Quick Start (5 Minutes)

### 1. Build & Start
```bash
docker-compose build web
docker-compose up -d
```

### 2. Run Migrations
```bash
docker-compose exec web python manage.py makemigrations authentication
docker-compose exec web python manage.py migrate
```

### 3. Create Test Users
```bash
docker-compose exec web python manage.py create_test_users
```

### 4. Test It
```bash
# Via script
bash scripts/test_auth.sh

# Or manually
curl -X POST http://localhost/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"username":"test_trader","password":"trader123"}'
```

## 👥 Test User Credentials

| Username | Password | Type | Features |
|----------|----------|------|----------|
| `test_admin` | `admin123` | Admin | Everything |
| `test_trader` | `trader123` | Trader | Trading + API |
| `test_analyst` | `analyst123` | Analyst | Analytics + Reports |
| `test_viewer` | `viewer123` | Viewer | Dashboard only |
| `test_trial` | `trial123` | Trial | Limited access |

## 🔑 API Endpoints

```bash
# Authentication
POST /auth/register/     # Create account
POST /auth/login/        # Login
POST /auth/logout/       # Logout
GET  /auth/me/           # Current user info

# User State (Redis)
POST /auth/state/        # Update user state
GET  /auth/me/           # Get user state

# User Management
GET    /auth/users/                        # List users
GET    /auth/users/{id}/                   # Get user
PATCH  /auth/users/{id}/                   # Update user
GET    /auth/users/{id}/sessions/          # Active sessions
POST   /auth/users/{id}/terminate_session/ # End session

# API Keys
GET    /auth/api-keys/              # List keys
POST   /auth/api-keys/              # Create key
POST   /auth/api-keys/{id}/regenerate/  # Regenerate
POST   /auth/api-keys/{id}/toggle/      # Enable/disable

# Admin
GET /admin/                     # Django admin panel
GET /api-auth/                  # DRF browsable API auth
```

## 🧪 Testing Multi-User States

### Set User State (Redis)
```python
# In Django shell: docker-compose exec web python manage.py shell
from authentication.models import User

user = User.objects.get(username='test_trader')
user.set_user_state({
    'theme': 'dark',
    'exchange': 'binance',
    'watchlist': ['BTC', 'ETH'],
    'strategy': 'grid_trading',
    'notifications': {
        'email': True,
        'discord': True
    }
})

# Retrieve state
state = user.get_user_state()
print(state)
```

### Test Concurrent Sessions
```python
# Add multiple sessions
user.add_session('session1', {'device': 'desktop', 'ip': '192.168.1.1'})
user.add_session('session2', {'device': 'mobile', 'ip': '192.168.1.2'})

# View sessions
sessions = user.get_active_sessions()
print(f"Active: {len(sessions)}")

# Remove session
user.remove_session('session1')
```

### Create API Key
```python
from authentication.models import APIKey
import secrets

api_key = APIKey.objects.create(
    user=user,
    name='Trading Bot',
    key=secrets.token_urlsafe(48),
    permissions=['trading', 'analytics'],
    rate_limit=200
)

print(f"API Key: {api_key.key}")
```

### Use API Key
```bash
curl -H "X-API-Key: YOUR_KEY_HERE" \
     http://localhost/auth/me/
```

## 🔍 View Redis Data

```bash
# Connect to Redis
docker-compose exec redis redis-cli

# View all user keys
KEYS user:*

# Get user state
GET user:1:state

# Get user sessions
GET user:1:sessions

# Check rate limits
KEYS rate_limit:*
GET rate_limit:user:1
```

## 🛡️ Security Features

- ✅ **Session Management**: Redis-backed, concurrent session limits
- ✅ **Rate Limiting**: Per-user and per-IP limits
- ✅ **API Keys**: With permissions and rate limits
- ✅ **Password Validation**: Django's built-in validators
- ✅ **CSRF Protection**: Enabled for web forms
- ✅ **Secure Cookies**: HTTPOnly, SameSite=Lax
- ✅ **Nginx Basic Auth**: Optional layer for admin tools

## 📊 Monitor Usage

### Django Admin
```
http://localhost/admin/authentication/
```

View:
- Users and their types/statuses
- Active sessions
- API keys and usage
- User profiles and stats

### Check Logs
```bash
# Django logs
tail -f logs/django.log

# Nginx logs
tail -f logs/nginx/access.log
tail -f logs/nginx/error.log
```

### Redis Stats
```bash
docker-compose exec redis redis-cli INFO stats
```

## 🎯 Common Tasks

### Change User Type
```python
user = User.objects.get(username='test_viewer')
user.user_type = 'trader'
user.status = 'active'
user.api_key_enabled = True
user.save()
```

### Suspend User
```python
user = User.objects.get(username='test_trader')
user.status = 'suspended'
user.save()

# Terminate all sessions
for session in user.sessions.filter(is_active=True):
    session.terminate()
```

### Check User Permissions
```python
user = User.objects.get(username='test_trader')

# Check specific feature
can_trade = user.can_access_feature('trading')
print(f"Can trade: {can_trade}")

# Check premium status
is_premium = user.is_premium
print(f"Is premium: {is_premium}")
```

### Update Profile
```python
profile = user.profile
profile.risk_tolerance = 'high'
profile.email_notifications = True
profile.preferred_exchanges = ['binance', 'coinbase']
profile.save()
```

## 🐛 Troubleshooting

### Sessions Not Working?
```bash
# Check Redis
docker-compose exec redis redis-cli ping
# Should return: PONG

# Check Django cache
docker-compose exec web python manage.py shell
>>> from django.core.cache import cache
>>> cache.set('test', 'value', 60)
>>> cache.get('test')
# Should return: 'value'
```

### Rate Limit Issues?
```bash
# Clear rate limits
docker-compose exec redis redis-cli
> KEYS rate_limit:*
> DEL rate_limit:user:1
```

### Import Errors?
```bash
# Rebuild container
docker-compose build web
docker-compose up -d web
```

## 📚 Full Documentation

- **Complete Guide**: [docs/AUTHENTICATION_IMPLEMENTATION.md](./AUTHENTICATION_IMPLEMENTATION.md)
- **Quick Setup**: [docs/AUTH_QUICKSTART.md](./AUTH_QUICKSTART.md)
- **Summary**: [docs/AUTHENTICATION_SUMMARY.md](./AUTHENTICATION_SUMMARY.md)

## 🔧 Environment Variables

Add to `.env`:
```bash
# Required
DJANGO_SECRET_KEY=your-secret-key-here

# Optional (defaults shown)
SESSION_COOKIE_SECURE=False  # True in production
SESSION_COOKIE_AGE=604800    # 7 days
DEBUG=True                   # False in production
```

## ✨ Features Ready for Testing

- [x] Multiple user types with different permissions
- [x] Redis-backed session management
- [x] Concurrent session limiting
- [x] User state persistence (Redis)
- [x] API key authentication
- [x] Rate limiting (IP and user-based)
- [x] Session tracking with metadata
- [x] Admin panel integration
- [x] RESTful API for all operations
- [x] Nginx integration ready

## 🎉 That's It!

You now have a fully functional authentication system ready for multi-user and multi-state testing!

Run the test script to verify:
```bash
bash scripts/test_auth.sh
```

Happy testing! 🚀
