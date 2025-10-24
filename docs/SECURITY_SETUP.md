# 🔒 Security Setup Guide

## ⚠️ IMPORTANT: Read Before Deployment

This guide helps you secure your FKS Trading Platform before deployment.

---

## 🚨 Critical Actions Required

### 1. Rotate Exposed Credentials

**YOUR CREDENTIALS WERE EXPOSED IN .ENV FILE!** Please take immediate action:

#### Discord Webhook
Your webhook URL was visible. To secure it:
1. Go to Discord Server Settings → Integrations → Webhooks
2. Find the webhook: `1426890429760278529`
3. **Delete it** and create a new one
4. Add the new URL to `.env` (not committed to git)

#### Netdata Token
Your Netdata token was exposed. To secure it:
1. Go to https://app.netdata.cloud
2. Navigate to your space settings
3. **Revoke** the old token: `Sn5D3zsAEX9KA_YtztxjdHCpan6v-o...`
4. Generate a new claim token
5. Add to `.env` (not committed to git)

### 2. Check Git History

**Critical**: Check if `.env` was ever committed to git:

```bash
# Check git history for .env
git log --all --full-history -- .env

# If found, you need to remove it from history
git filter-branch --force --index-filter \
  "git rm --cached --ignore-unmatch .env" \
  --prune-empty --tag-name-filter cat -- --all

# Force push (CAUTION: coordinate with team)
git push origin --force --all
```

---

## 📝 Setup Checklist

### Step 1: Create Your .env File

```bash
# Copy the example file
cp .env.example .env

# Edit with secure values
nano .env  # or vim, code, etc.
```

### Step 2: Generate Strong Passwords

**PostgreSQL Password** (minimum 16 characters):
```bash
# Generate random password
openssl rand -base64 24
```

**PgAdmin Password** (minimum 12 characters):
```bash
openssl rand -base64 16
```

**Django Secret Key** (50+ characters):
```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

### Step 3: Update .env File

Edit `.env` with generated values:

```env
# Database
POSTGRES_USER=fks_user
POSTGRES_PASSWORD=<your-generated-password>
POSTGRES_DB=trading_db

# PgAdmin
PGADMIN_EMAIL=admin@fks.local
PGADMIN_PASSWORD=<your-generated-password>

# Django
DJANGO_SECRET_KEY=<your-generated-secret-key>

# External Services (optional)
DISCORD_WEBHOOK_URL=<your-new-webhook-url>
NETDATA_CLAIM_TOKEN=<your-new-token>
```

### Step 4: Verify Security

Run the security check:

```bash
make security-check
```

or

```bash
bash scripts/security-check.sh
```

### Step 5: Validate Configuration

```bash
# Check environment
make env-check

# Validate Docker Compose
make validate-compose
```

---

## 🔐 Production Security Hardening

### 1. Remove Development Ports

Edit `docker-compose.yml` for production:

```yaml
# Comment out or remove these port mappings:
# db:
#   ports:
#     - "5432:5432"  # Remove for production
# 
# redis:
#   ports:
#     - "6379:6379"  # Remove for production
```

### 2. Enable SSL/HTTPS

```bash
# Generate SSL certificates
make setup-ssl

# Or use Let's Encrypt
./scripts/ssl/upgrade-to-letsencrypt.sh
```

### 3. Use Docker Secrets (Production)

For production deployments, use Docker secrets instead of environment variables:

```yaml
# docker-compose.prod.yml
services:
  web:
    secrets:
      - postgres_password
      - django_secret_key
    environment:
      POSTGRES_PASSWORD_FILE: /run/secrets/postgres_password
      DJANGO_SECRET_KEY_FILE: /run/secrets/django_secret_key

secrets:
  postgres_password:
    external: true
  django_secret_key:
    external: true
```

### 4. Enable Security Headers

Ensure nginx configuration includes:

```nginx
# Security headers
add_header X-Frame-Options "SAMEORIGIN" always;
add_header X-Content-Type-Options "nosniff" always;
add_header X-XSS-Protection "1; mode=block" always;
add_header Referrer-Policy "no-referrer-when-downgrade" always;
add_header Content-Security-Policy "default-src 'self' http: https: data: blob: 'unsafe-inline'" always;
```

### 5. Enable Rate Limiting

Configure nginx rate limiting:

```nginx
limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;
limit_req_zone $binary_remote_addr zone=general:10m rate=100r/s;
```

---

## 🧪 Testing Your Security Setup

### 1. Check for Exposed Services

```bash
# From outside your server
nmap -p 80,443,5432,6379 your-server-ip

# You should ONLY see 80 and 443 open in production
```

### 2. Test SSL Configuration

```bash
# Check SSL cert
openssl s_client -connect your-domain.com:443 -servername your-domain.com

# Or use SSL Labs
# https://www.ssllabs.com/ssltest/
```

### 3. Verify Authentication

```bash
# Test database connection
docker-compose exec web python manage.py dbshell

# Should require your password
```

---

## 📚 Additional Resources

- [Django Security Checklist](https://docs.djangoproject.com/en/5.0/howto/deployment/checklist/)
- [Docker Security Best Practices](https://docs.docker.com/engine/security/)
- [OWASP Top 10](https://owasp.org/www-project-top-ten/)

---

## 🆘 If You Need Help

If you believe your credentials were compromised:

1. **Immediately** change all passwords and regenerate all tokens
2. Review access logs for suspicious activity
3. Enable 2FA on all external services
4. Consider rotating database encryption keys
5. Review and audit all API access

---

## ✅ Security Checklist

Before going to production, ensure:

- [ ] All default passwords changed
- [ ] Django SECRET_KEY is unique and random
- [ ] .env file is NOT in git
- [ ] SSL/HTTPS is enabled
- [ ] Database ports are not exposed
- [ ] Redis port is not exposed
- [ ] Strong passwords (16+ characters)
- [ ] Discord webhooks rotated
- [ ] Netdata tokens rotated
- [ ] Git history cleaned (if needed)
- [ ] Security headers configured
- [ ] Rate limiting enabled
- [ ] Regular backups configured
- [ ] Monitoring and alerting set up

---

**Remember**: Security is an ongoing process, not a one-time setup!
