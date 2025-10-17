# Quick Setup: Authentication System

## 1. Install Dependencies

```bash
pip install user-agents
# or add to requirements.txt and rebuild container
```

## 2. Run Migrations

```bash
docker-compose exec web python manage.py makemigrations authentication
docker-compose exec web python manage.py migrate
```

## 3. Create Admin User

```bash
docker-compose exec web python manage.py createsuperuser
```

## 4. Generate Nginx Basic Auth

```bash
bash scripts/generate_htpasswd.sh
# This creates ./nginx/.htpasswd
```

## 5. Restart Services

```bash
docker-compose down && docker-compose up -d
```

## 6. Test Authentication

### Web Interface
- Visit: https://fkstrading.xyz/admin/
- Login with superuser credentials

### API Test

```bash
# Register user
curl -X POST https://fkstrading.xyz/auth/register/ \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "email": "test@example.com",
    "password": "SecurePass123!",
    "password_confirm": "SecurePass123!"
  }'

# Login
curl -X POST https://fkstrading.xyz/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "password": "SecurePass123!"
  }' \
  -c cookies.txt

# Get current user (with session cookie)
curl https://fkstrading.xyz/auth/me/ \
  -b cookies.txt
```

## 7. Create API Key (Django Shell)

```bash
docker-compose exec web python manage.py shell
```

```python
from authentication.models import User, APIKey
import secrets

user = User.objects.get(username='testuser')
user.api_key_enabled = True
user.save()

api_key = APIKey.objects.create(
    user=user,
    name='Test API Key',
    key=secrets.token_urlsafe(48),
    permissions=['trading', 'read_data']
)

print(f"API Key: {api_key.key}")
```

## 8. Test API Key

```bash
curl -H "X-API-Key: YOUR_API_KEY_HERE" \
  https://fkstrading.xyz/auth/me/
```

## Done!

Your authentication system is now ready. See `AUTHENTICATION_IMPLEMENTATION.md` for full documentation.
