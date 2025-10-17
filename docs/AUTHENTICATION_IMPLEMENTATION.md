# Authentication System Setup Guide

This guide explains how to set up and use the authentication system for the FKS Trading Platform.

## Overview

The authentication system provides:

- **User Management**: Multiple user types (Admin, Trader, Analyst, Viewer)
- **Session Management**: Redis-backed sessions with concurrent session limiting
- **API Keys**: Programmatic access with rate limiting
- **Nginx Integration**: Basic auth for admin tools + Django auth for web interface
- **User States**: Store and retrieve user-specific state data in Redis
- **Rate Limiting**: IP and user-based rate limiting
- **Multi-factor Security**: Combination of Django auth + Nginx basic auth

## Architecture

```
┌─────────────┐
│   Client    │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│    Nginx    │ ◄── Basic Auth (.htpasswd)
└──────┬──────┘
       │
       ▼
┌─────────────┐
│   Django    │ ◄── Session/Token Auth
└──────┬──────┘
       │
       ├──────────► PostgreSQL (User data)
       │
       └──────────► Redis (Sessions, State, Rate limits)
```

## Initial Setup

### 1. Update Requirements

Add to `requirements.txt`:

```bash
pydantic-settings>=2.0.0
user-agents>=2.2.0
djangorestframework>=3.14.0
```

### 2. Run Migrations

```bash
# Inside the container or locally
docker-compose exec web python manage.py makemigrations authentication
docker-compose exec web python manage.py migrate
```

### 3. Create Superuser

```bash
docker-compose exec web python manage.py createsuperuser
```

### 4. Generate Nginx Basic Auth Credentials

```bash
bash scripts/generate_htpasswd.sh
```

This creates `./nginx/.htpasswd` file which is already mounted in docker-compose.yml.

### 5. Restart Services

```bash
docker-compose down
docker-compose up -d
```

## User Types and Permissions

| User Type | Permissions | Features |
|-----------|-------------|----------|
| **Admin** | All | Full system access, user management |
| **Trader** | Trading, Backtest, Analytics, API | Can execute trades, access API |
| **Analyst** | Analytics, Backtest, Reports | View-only trading data |
| **Viewer** | Dashboard, Reports | Basic monitoring |

## User Statuses

- **Active**: Full access
- **Trial**: Limited features/time
- **Inactive**: Account disabled
- **Suspended**: Temporary restriction

## API Endpoints

### Authentication

```bash
# Register new user
POST /auth/register/
{
  "username": "trader1",
  "email": "trader1@example.com",
  "password": "SecurePass123!",
  "password_confirm": "SecurePass123!",
  "first_name": "John",
  "last_name": "Doe"
}

# Login
POST /auth/login/
{
  "username": "trader1",
  "password": "SecurePass123!"
}

# Logout
POST /auth/logout/

# Get current user info
GET /auth/me/

# Update user state (Redis)
POST /auth/state/
{
  "last_viewed_chart": "BTC/USDT",
  "selected_strategy": "grid_trading",
  "theme": "dark"
}
```

### User Management

```bash
# List users (admin only)
GET /auth/users/

# Get user details
GET /auth/users/{id}/

# Update user
PATCH /auth/users/{id}/
{
  "user_type": "trader",
  "status": "active"
}

# Get user's active sessions
GET /auth/users/{id}/sessions/

# Terminate a session
POST /auth/users/{id}/terminate_session/
{
  "session_key": "abc123..."
}
```

### API Keys

```bash
# List API keys
GET /auth/api-keys/

# Create API key
POST /auth/api-keys/
{
  "name": "Trading Bot Key",
  "permissions": ["trading", "read_data"],
  "rate_limit": 100
}

# Regenerate API key
POST /auth/api-keys/{id}/regenerate/

# Toggle API key status
POST /auth/api-keys/{id}/toggle/
```

## Using API Keys

Include the API key in requests:

### Header Method (Recommended)

```bash
curl -H "X-API-Key: your-api-key-here" \
     https://fkstrading.xyz/api/v1/protected/data
```

### Query Parameter Method

```bash
curl "https://fkstrading.xyz/api/v1/protected/data?api_key=your-api-key-here"
```

## Session Management

### Redis Session Keys

- `user:{user_id}:state` - User state data
- `user:{user_id}:sessions` - Active sessions list
- `session_token:{token}` - Session tokens
- `api_key:{key}:usage` - API key usage tracking
- `rate_limit:{identifier}` - Rate limit counters

### Concurrent Sessions

Each user has a `max_concurrent_sessions` limit. When exceeded, the oldest session is automatically terminated.

### Manual Session Management

```python
from authentication.models import User

user = User.objects.get(username='trader1')

# Get active sessions
sessions = user.get_active_sessions()

# Set user state
user.set_user_state({
    'theme': 'dark',
    'selected_exchange': 'binance',
    'watchlist': ['BTC', 'ETH', 'SOL']
})

# Get user state
state = user.get_user_state()

# Check permissions
can_trade = user.can_access_feature('trading')
```

## Rate Limiting

### Default Limits

- **Anonymous users**: 100 requests/minute
- **Authenticated users**: 300 requests/minute
- **API keys**: Custom (default 100 requests/minute)

### Response Headers

```
X-RateLimit-Limit: 300
X-RateLimit-Remaining: 275
```

### Rate Limit Exceeded Response

```json
{
  "error": "Rate limit exceeded",
  "message": "Too many requests. Please try again later.",
  "retry_after": 60
}
```

## Nginx Configuration

### Protected Endpoints

Edit `nginx/conf.d/fkstrading.xyz.conf` to enable authentication for specific paths:

```nginx
# Admin area - Basic auth
location /admin/ {
    auth_basic "Admin Area";
    auth_basic_user_file /etc/nginx/.htpasswd;
    
    proxy_pass http://django;
    # ... other proxy settings
}

# Flower - Basic auth
location /flower/ {
    auth_basic "Celery Monitoring";
    auth_basic_user_file /etc/nginx/.htpasswd;
    
    # ... proxy settings
}

# Protected API - Django auth or API key
location /api/v1/protected/ {
    # Handled by Django middleware
    proxy_pass http://django;
    # ... proxy settings
}
```

## Testing Multiple Users

### Create Test Users

```python
# In Django shell: docker-compose exec web python manage.py shell

from authentication.models import User, UserProfile

# Create admin user
admin = User.objects.create_user(
    username='admin',
    email='admin@example.com',
    password='admin123',
    user_type='admin',
    status='active',
    is_staff=True,
    is_superuser=True
)

# Create trader user
trader = User.objects.create_user(
    username='trader1',
    email='trader1@example.com',
    password='trader123',
    user_type='trader',
    status='active',
    max_concurrent_sessions=5
)

# Create trial user
trial = User.objects.create_user(
    username='trial_user',
    email='trial@example.com',
    password='trial123',
    user_type='viewer',
    status='trial'
)

# Profiles are created automatically via signal or in save method
```

### Test Different States

```python
# Test user state management
trader.set_user_state({
    'last_login_location': 'New York',
    'preferred_pairs': ['BTC/USDT', 'ETH/USDT'],
    'notification_settings': {
        'email': True,
        'discord': True,
        'trades': True
    }
})

# Retrieve state
state = trader.get_user_state()
print(state)

# Test session management
trader.add_session('session_123', {'device': 'mobile', 'ip': '192.168.1.1'})
sessions = trader.get_active_sessions()
print(f"Active sessions: {len(sessions)}")
```

### Test API Keys

```python
from authentication.models import APIKey
import secrets

# Create API key for trader
api_key = APIKey.objects.create(
    user=trader,
    name='Trading Bot',
    key=secrets.token_urlsafe(48),
    permissions=['trading', 'read_data'],
    rate_limit=200
)

print(f"API Key: {api_key.key}")
```

## Security Best Practices

1. **Use HTTPS in Production**: Set `SESSION_COOKIE_SECURE=True`
2. **Strong Passwords**: Enforce minimum 8 characters with complexity
3. **Regular Key Rotation**: Regenerate API keys periodically
4. **Monitor Sessions**: Check for suspicious concurrent sessions
5. **Rate Limit Tuning**: Adjust based on usage patterns
6. **Audit Logs**: Enable logging for authentication events
7. **Two-Factor Auth** (Future): Add TOTP support

## Environment Variables

Add to your `.env` file:

```bash
# Django Secret Key (CRITICAL - change in production!)
DJANGO_SECRET_KEY=your-super-secret-key-here

# Session Settings
SESSION_COOKIE_SECURE=True  # Only in production with HTTPS
SESSION_COOKIE_AGE=604800   # 7 days in seconds

# Redis Configuration (already configured)
REDIS_URL=redis://redis:6379/1
CELERY_BROKER_URL=redis://redis:6379/0
```

## Troubleshooting

### Sessions Not Persisting

```bash
# Check Redis connection
docker-compose exec redis redis-cli ping

# Check session in Redis
docker-compose exec redis redis-cli
> KEYS user:*:state
> GET user:1:state
```

### API Key Not Working

```python
# In Django shell
from authentication.models import APIKey
from authentication.utils import validate_api_key

is_valid, key_obj, error = validate_api_key('your-api-key')
print(f"Valid: {is_valid}, Error: {error}")
```

### Rate Limit Issues

```bash
# Check rate limit in Redis
docker-compose exec redis redis-cli
> KEYS rate_limit:*
> GET rate_limit:user:1
```

## Monitoring

### View Active Sessions

```bash
# In Django admin: http://your-domain/admin/authentication/usersession/
# Or via API: GET /auth/users/{id}/sessions/
```

### Check User Statistics

```bash
docker-compose exec web python manage.py shell

from authentication.models import User, UserProfile

# Get user stats
for profile in UserProfile.objects.all():
    print(f"{profile.user.username}: {profile.total_trades} trades, "
          f"{profile.success_rate:.2f}% success rate")
```

## Next Steps

1. Implement frontend login/logout UI
2. Add password reset functionality
3. Implement email verification
4. Add OAuth2 providers (Google, GitHub)
5. Implement two-factor authentication
6. Add detailed audit logging
7. Create user dashboard for session management

## Support

For issues or questions, check:
- Django admin: `/admin/`
- API docs: `/api/schema/swagger/` (if configured)
- Logs: `./logs/django.log`
