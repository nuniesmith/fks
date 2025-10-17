# FKS Platform - Secrets Configuration Guide

**Last Updated**: October 17, 2025  
**Purpose**: Comprehensive guide for all secrets and environment variables

---

## 🔐 Overview

This guide consolidates all secret management for the FKS trading platform including:
- GitHub Actions secrets
- Docker Hub credentials
- Cloudflare DNS/SSL
- Linode API tokens
- Database credentials
- API keys (exchanges, LLMs, etc.)

---

## 📋 Quick Checklist

### Required for Local Development
- [ ] `.env` file created from `.env.example`
- [ ] Database credentials set
- [ ] Redis configuration
- [ ] Exchange API keys (Binance, etc.)

### Required for CI/CD (GitHub Actions)
- [ ] DOCKER_USERNAME
- [ ] DOCKER_API_TOKEN
- [ ] LINODE_API_TOKEN
- [ ] SSH_PRIVATE_KEY
- [ ] CLOUDFLARE_API_TOKEN (if using Cloudflare)

### Optional Secrets
- [ ] OPENAI_API_KEY (for RAG with OpenAI)
- [ ] DISCORD_WEBHOOK_URL (for notifications)
- [ ] SLACK_WEBHOOK_URL (for alerts)

---

## 🔧 Local Development (.env)

### Database Configuration
```bash
# PostgreSQL + TimescaleDB
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_secure_password
POSTGRES_DB=trading_db
POSTGRES_HOST=db
POSTGRES_PORT=5432
DATABASE_URL=postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@${POSTGRES_HOST}:${POSTGRES_PORT}/${POSTGRES_DB}
```

### Redis Configuration
```bash
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD=
REDIS_DB=0
REDIS_URL=redis://${REDIS_HOST}:${REDIS_PORT}/${REDIS_DB}
```

### Django Settings
```bash
DJANGO_SECRET_KEY=your-secret-key-here-change-in-production
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,desktop-win
```

### Exchange API Keys
```bash
# Binance
BINANCE_API_KEY=your_binance_api_key
BINANCE_API_SECRET=your_binance_secret

# Add other exchanges as needed
COINBASE_API_KEY=
KRAKEN_API_KEY=
```

### LLM API Keys (Optional)
```bash
# OpenAI (for RAG if not using local LLM)
OPENAI_API_KEY=sk-...

# Anthropic
ANTHROPIC_API_KEY=

# OpenRouter (fallback)
OPENROUTER_API_KEY=
```

### Notification Webhooks (Optional)
```bash
# Discord
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...

# Slack
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
```

---

## 🐳 Docker Hub Secrets

### DOCKER_USERNAME
- **Description**: Your Docker Hub username
- **Example**: `yourusername`
- **How to get**: Your Docker Hub account username
- **Used in**: GitHub Actions for pushing images

### DOCKER_API_TOKEN
- **Description**: Docker Hub Personal Access Token (PAT)
- **Example**: `dckr_pat_abcd1234...`
- **How to get**:
  1. Go to https://hub.docker.com/settings/security
  2. Click "New Access Token"
  3. Name it "GitHub Actions FKS"
  4. Copy the token immediately (shown only once!)
- **Used in**: GitHub Actions docker login

---

## 🌐 Cloudflare Secrets

### CLOUDFLARE_API_TOKEN
- **Description**: API token with DNS edit permissions
- **Example**: `abc123...`
- **How to get**:
  1. Go to https://dash.cloudflare.com/profile/api-tokens
  2. Click "Create Token"
  3. Use "Edit zone DNS" template
  4. Add permissions:
     - Zone → DNS → Edit
     - Zone → Zone → Read
  5. Select specific zone: `fkstrading.xyz`
- **Used in**: GitHub Actions for DNS updates

### CLOUDFLARE_ZONE_ID
- **Description**: Zone ID for your domain
- **Example**: `abc123...` (32-char hex)
- **How to get**:
  1. Go to Cloudflare Dashboard
  2. Select your domain
  3. Find "Zone ID" on the right sidebar
- **Used in**: GitHub Actions DNS management

---

## 🖥️ Linode Secrets

### LINODE_API_TOKEN
- **Description**: Linode API token for server management
- **Example**: `abc123...`
- **How to get**:
  1. Go to https://cloud.linode.com/profile/tokens
  2. Click "Create a Personal Access Token"
  3. Name it "FKS Deploy"
  4. Select permissions:
     - Linodes: Read/Write
     - StackScripts: Read
     - Images: Read
  5. Set expiration (or never)
  6. Copy token immediately
- **Used in**: GitHub Actions for deployment automation

---

## 🔑 SSH Deployment Secrets

### SSH_PRIVATE_KEY
- **Description**: SSH private key for server access
- **Example**: 
  ```
  -----BEGIN OPENSSH PRIVATE KEY-----
  b3BlbnNzaC1rZXktdjEAAAAABG5vbmUAAAAEbm9uZQAAAAAAAAABAAACFwAAAAdzc2gtcn
  ...
  -----END OPENSSH PRIVATE KEY-----
  ```
- **How to get**:
  ```bash
  # Generate new key pair
  ssh-keygen -t ed25519 -C "github-actions-fks"
  
  # Copy private key (entire file)
  cat ~/.ssh/id_ed25519
  
  # Copy public key to server
  ssh-copy-id user@server
  ```
- **Used in**: GitHub Actions SSH deployment

### DEPLOY_HOST
- **Description**: Server hostname or IP
- **Example**: `fkstrading.xyz` or `100.114.87.27`
- **Used in**: GitHub Actions deployment

### DEPLOY_USER
- **Description**: SSH username
- **Example**: `jordan` or `ubuntu`
- **Used in**: GitHub Actions deployment

### DEPLOY_PATH
- **Description**: Deployment directory path
- **Example**: `/home/jordan/fks`
- **Used in**: GitHub Actions deployment

---

## 🎯 How to Add GitHub Secrets

### Via Web Interface
1. Go to your GitHub repository
2. Click **Settings** tab
3. Navigate to **Secrets and variables** → **Actions**
4. Click **New repository secret**
5. Enter the secret name and value
6. Click **Add secret**

### Via GitHub CLI
```bash
# Set a secret
gh secret set SECRET_NAME

# Set from file
gh secret set SECRET_NAME < secret.txt

# Set from command output
echo "secret_value" | gh secret set SECRET_NAME

# List all secrets
gh secret list
```

---

## 🧪 Testing Secrets Locally

### Test Database Connection
```bash
docker compose exec web python manage.py dbshell
```

### Test Redis Connection
```bash
docker compose exec redis redis-cli ping
# Should return: PONG
```

### Test Exchange API
```bash
docker compose exec web python manage.py shell
>>> from data.providers.binance import BinanceDataProvider
>>> provider = BinanceDataProvider()
>>> provider.test_connection()
```

### Test LLM API
```bash
docker compose exec web python -c "
from openai import OpenAI
client = OpenAI()
print('OpenAI API: OK')
"
```

---

## 🔒 Security Best Practices

### DO ✅
- Use strong, unique passwords for each service
- Rotate API keys regularly (every 90 days)
- Use environment-specific secrets (dev/staging/prod)
- Store secrets in secure password manager
- Use GitHub secrets for CI/CD (never commit)
- Limit API token permissions to minimum required
- Monitor API usage for suspicious activity
- Use 2FA on all accounts

### DON'T ❌
- Never commit secrets to git
- Don't share secrets via chat/email
- Don't use same password across services
- Don't grant more permissions than needed
- Don't skip secret rotation
- Don't use production secrets in development
- Don't log secrets (even in debug mode)

---

## 🚨 Incident Response

### If Secrets Are Compromised

1. **Immediate Actions**:
   - Revoke compromised credentials immediately
   - Generate new secrets
   - Update GitHub secrets
   - Redeploy services

2. **Investigation**:
   - Check git history for leaks
   - Review access logs
   - Identify how leak occurred

3. **Prevention**:
   - Add leaked pattern to `.gitignore`
   - Use git-secrets or similar tool
   - Train team on secret handling

### Leaked to Git History
```bash
# Remove from git history (use carefully!)
git filter-branch --force --index-filter \
  "git rm --cached --ignore-unmatch .env" \
  --prune-empty --tag-name-filter cat -- --all

# Force push (breaks others' repos!)
git push origin --force --all
```

---

## 📚 Related Documentation

- [Environment Setup](../setup/ENVIRONMENT_SETUP.md)
- [Deployment Guide](DEPLOYMENT.md)
- [GitHub Actions Guide](GITHUB_ACTIONS.md)
- [Local Development](../setup/LOCAL_DEV_DOMAIN_SETUP.md)

---

## 🆘 Troubleshooting

### "Invalid credentials" error
- Verify secret is set correctly in GitHub
- Check for trailing spaces/newlines
- Ensure secret name matches code reference

### "Permission denied" error
- Check API token permissions
- Verify token hasn't expired
- Ensure correct authentication method

### "Connection refused" error
- Verify host/port are correct
- Check firewall rules
- Ensure service is running

---

**Security Note**: Never share this file with actual secret values. Keep this as a template only.
