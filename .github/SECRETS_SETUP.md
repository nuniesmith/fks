# CI/CD Secrets Configuration Guide

This guide explains how to configure GitHub secrets required for the CI/CD pipeline.

## Required Secrets

### 1. Discord Notifications (Optional but Recommended)
**Secret Name**: `DISCORD_WEBHOOK`  
**Description**: Webhook URL for sending CI/CD notifications to Discord

**How to Get**:
1. Open Discord and go to Server Settings → Integrations → Webhooks
2. Click "New Webhook"
3. Name it "FKS CI/CD Bot"
4. Select the channel for notifications
5. Copy the Webhook URL
6. Add to GitHub: Settings → Secrets and variables → Actions → New repository secret

**Example Value**: `https://discord.com/api/webhooks/123456789/abcdefghijklmnopqrstuvwxyz`

### 2. Docker Hub (Required for Docker Builds)
**Secret Names**: 
- `DOCKER_USERNAME`
- `DOCKER_API_TOKEN`
- `DOCKER_REPOSITORY`

**How to Get**:
1. Create account at https://hub.docker.com
2. Go to Account Settings → Security → New Access Token
3. Name it "GitHub Actions" with Read & Write permissions
4. Copy the token (save it securely, shown only once)
5. Add three secrets to GitHub:
   - `DOCKER_USERNAME`: Your Docker Hub username
   - `DOCKER_API_TOKEN`: The token you just created
   - `DOCKER_REPOSITORY`: Your repository name (e.g., `username/fks-trading`)

**Example Values**:
- `DOCKER_USERNAME`: `myusername`
- `DOCKER_API_TOKEN`: `dckr_pat_aBcDeFgHiJkLmNoPqRsTuVwXyZ`
- `DOCKER_REPOSITORY`: `myusername/fks-trading`

### 3. Cloudflare DNS (Required for Auto-Deployment)
**Secret Names**:
- `CLOUDFLARE_API_TOKEN`
- `CLOUDFLARE_ZONE_ID`
- `PRODUCTION_IP`
- `STAGING_IP`

**How to Get**:

#### Cloudflare API Token:
1. Log in to Cloudflare Dashboard
2. Go to My Profile → API Tokens
3. Click "Create Token"
4. Use "Edit zone DNS" template
5. Select your zone (domain)
6. Copy the token

#### Zone ID:
1. Go to Cloudflare Dashboard
2. Select your domain
3. Find Zone ID in the right sidebar under "API"

#### Server IPs:
- Get your production and staging server IPs
- Or use Tailscale IPs if using VPN

**Example Values**:
- `CLOUDFLARE_API_TOKEN`: `abcdef1234567890abcdef1234567890`
- `CLOUDFLARE_ZONE_ID`: `1234567890abcdef1234567890abcdef`
- `PRODUCTION_IP`: `203.0.113.1`
- `STAGING_IP`: `203.0.113.2`

### 4. Codecov (Optional, for Coverage Reports)
**Secret Name**: Not required - Codecov action uses `GITHUB_TOKEN` automatically

If you want to use Codecov:
1. Sign up at https://codecov.io with GitHub
2. Add your repository
3. Upload token will be provided (usually not needed for public repos)

## Setting Up Secrets

### Via GitHub Web UI
1. Go to your repository on GitHub
2. Click Settings (top menu)
3. Click Secrets and variables → Actions (left sidebar)
4. Click "New repository secret"
5. Enter name and value
6. Click "Add secret"
7. Repeat for all secrets

### Via GitHub CLI
```bash
# Install GitHub CLI if not already installed
# https://cli.github.com

# Authenticate
gh auth login

# Add secrets
gh secret set DISCORD_WEBHOOK -b "https://discord.com/api/webhooks/..."
gh secret set DOCKER_USERNAME -b "myusername"
gh secret set DOCKER_API_TOKEN -b "dckr_pat_..."
gh secret set DOCKER_REPOSITORY -b "myusername/fks-trading"
gh secret set CLOUDFLARE_API_TOKEN -b "abcdef..."
gh secret set CLOUDFLARE_ZONE_ID -b "1234567890..."
gh secret set PRODUCTION_IP -b "203.0.113.1"
gh secret set STAGING_IP -b "203.0.113.2"
```

## Verifying Secrets

After adding secrets, verify they're set correctly:

```bash
# List all secrets (values are hidden)
gh secret list
```

Expected output:
```
CLOUDFLARE_API_TOKEN
CLOUDFLARE_ZONE_ID
DISCORD_WEBHOOK
DOCKER_API_TOKEN
DOCKER_REPOSITORY
DOCKER_USERNAME
PRODUCTION_IP
STAGING_IP
```

## Optional Secrets

### Codecov Token (for private repos)
**Secret Name**: `CODECOV_TOKEN`  
**How to Get**: https://codecov.io → Add repository → Copy token

### Sentry DSN (for error tracking)
**Secret Name**: `SENTRY_DSN`  
**How to Get**: https://sentry.io → Create project → Copy DSN

## Workflow Behavior Without Secrets

If secrets are not configured, workflows will:

- ✅ **Still run tests and lints** - Core CI checks don't need secrets
- ⚠️ **Skip Docker builds** - Needs Docker Hub credentials
- ⚠️ **Skip Discord notifications** - Notifications won't be sent
- ⚠️ **Skip DNS updates** - Deployment automation won't work
- ⚠️ **Skip Codecov upload** - Coverage trends won't be tracked

## Security Best Practices

1. **Never commit secrets to git** - Use secrets, not .env files
2. **Rotate tokens regularly** - Every 90 days recommended
3. **Use least privilege** - API tokens should have minimal permissions
4. **Monitor usage** - Check for unauthorized access
5. **Delete unused tokens** - Remove old/test tokens

## Troubleshooting

### "Secret not found" error
- Verify secret name matches exactly (case-sensitive)
- Check secret is set at repository level, not organization
- Ensure you have admin access to repository

### Discord webhook not working
- Test webhook URL directly with curl
- Check channel permissions
- Verify webhook wasn't deleted in Discord

### Docker push failing
- Verify Docker Hub credentials are correct
- Check token hasn't expired
- Ensure repository exists in Docker Hub

### Cloudflare DNS update failing
- Verify API token has "Edit zone DNS" permission
- Check Zone ID matches your domain
- Ensure IPs are valid IPv4 addresses

## Getting Help

If you encounter issues:
1. Check workflow logs in GitHub Actions tab
2. Review error messages carefully
3. Verify secret values are correct
4. Test credentials manually before adding to GitHub

## Reference Links

- [GitHub Actions Secrets](https://docs.github.com/en/actions/security-guides/encrypted-secrets)
- [Discord Webhooks](https://support.discord.com/hc/en-us/articles/228383668-Intro-to-Webhooks)
- [Docker Hub Access Tokens](https://docs.docker.com/docker-hub/access-tokens/)
- [Cloudflare API](https://developers.cloudflare.com/api/)
