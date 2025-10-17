# GitHub Actions Secrets Quick Reference

## Required Secrets for Cloudflare DNS Management

Add these secrets to: **Repository Settings → Secrets and variables → Actions**

### Cloudflare Configuration

| Secret Name | Required | Description | How to Get |
|------------|----------|-------------|------------|
| `CLOUDFLARE_API_TOKEN` | ✅ Yes | API token with DNS edit permissions | [Create Token](https://dash.cloudflare.com/profile/api-tokens) |
| `CLOUDFLARE_ZONE_ID` | ✅ Yes | Zone ID for fkstrading.xyz (32-char hex) | Cloudflare Dashboard → Domain → Overview → Zone ID |

### Server Configuration

| Secret Name | Required | Description | Example |
|------------|----------|-------------|---------|
| `PRODUCTION_IP` | ✅ Yes (main) | Production server public IP | `203.0.113.42` |
| `STAGING_IP` | ⚠️ Optional | Staging server IP (only if using develop branch) | `198.51.100.42` |

### Deployment Configuration (Existing)

| Secret Name | Required | Description |
|------------|----------|-------------|
| `SSH_PRIVATE_KEY` | ✅ Yes | SSH private key for deployment |
| `DEPLOY_HOST` | ✅ Yes | Server hostname or IP |
| `DEPLOY_USER` | ✅ Yes | SSH username |
| `DEPLOY_PATH` | ✅ Yes | Project path on server |
| `DOCKER_USERNAME` | ✅ Yes | Docker Hub username |
| `DOCKER_API_TOKEN` | ✅ Yes | Docker Hub API token (Personal Access Token) |
| `DOCKER_REPOSITORY` | ✅ Yes | Docker repository (e.g., username/fks-trading) |
| `SLACK_WEBHOOK` | ⚠️ Optional | Slack webhook for notifications |

## Quick Setup Steps

### 1. Create Cloudflare API Token

```bash
# Visit: https://dash.cloudflare.com/profile/api-tokens
# Click "Create Token" → "Use template" for "Edit zone DNS"
# Permissions: Zone.DNS (Edit), Zone.Zone (Read)
# Resources: Include specific zone (fkstrading.xyz)
```

### 2. Get Zone ID

```bash
# Visit: https://dash.cloudflare.com/
# Select fkstrading.xyz domain
# Copy Zone ID from right sidebar under "API" section
```

### 3. Test Your Token

```bash
# Verify token works
curl -X GET "https://api.cloudflare.com/client/v4/user/tokens/verify" \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  -H "Content-Type: application/json"

# Expected response: {"success":true,"errors":[],"messages":[],"result":{"id":"...","status":"active"}}
```

### 4. Add Secrets to GitHub

```bash
# Go to GitHub repo → Settings → Secrets and variables → Actions
# Click "New repository secret"
# Add each secret listed above
```

## Environment Behavior

| Branch | DNS Record | IP Used | WWW Record | Deploy |
|--------|-----------|---------|------------|--------|
| `main` | fkstrading.xyz | `PRODUCTION_IP` | ✅ Yes | ✅ Yes |
| `develop` | staging.fkstrading.xyz | `STAGING_IP` | ❌ No | ❌ No |

## DNS Record Configuration

All records are created with:
- **Type**: A record
- **TTL**: 300 seconds (5 minutes)
- **Proxied**: Yes (through Cloudflare CDN)
- **Auto-managed**: Controlled by GitHub Actions

## Workflow Trigger

Automatic on push to:
- `main` branch (production)
- `develop` branch (staging)

Manual trigger:
- Actions tab → CI/CD Pipeline → Run workflow

## Verification Commands

```bash
# Check DNS resolution
dig fkstrading.xyz +short

# Check with Cloudflare DNS
dig @1.1.1.1 fkstrading.xyz +short

# Check DNS propagation globally
# Visit: https://dnschecker.org/#A/fkstrading.xyz

# Test HTTPS endpoint
curl -I https://fkstrading.xyz

# Verify Cloudflare proxy
curl -I https://fkstrading.xyz | grep -i cf-ray
```

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Job skipped | Push to `main` or `develop` branch |
| Authentication failed | Regenerate `CLOUDFLARE_API_TOKEN` |
| DNS not updating | Verify `CLOUDFLARE_ZONE_ID` is correct |
| Wrong IP | Check `PRODUCTION_IP` or `STAGING_IP` secret |
| API error | Review GitHub Actions logs for details |

## Current Setup

- **Domain**: fkstrading.xyz
- **Current IP**: 100.114.87.27 (Tailscale - desktop-win)
- **Nginx**: Configured with SSL reverse proxy
- **SSL**: Self-signed certificates (dev), Let's Encrypt ready (prod)

## Next Actions

1. ✅ Create Cloudflare API token
2. ✅ Get Zone ID from dashboard
3. ✅ Add both secrets to GitHub
4. ✅ Update `PRODUCTION_IP` secret (if different from 100.114.87.27)
5. ✅ Test workflow with manual trigger
6. ✅ Push to develop/main to trigger automatic update

## Documentation

Full guide: `docs/CLOUDFLARE_GITHUB_ACTIONS_SETUP.md`

---

**Last Updated**: January 2025
