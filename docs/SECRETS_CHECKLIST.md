# GitHub Secrets - Quick Setup

## All Required Secrets

Copy this list and check off as you add each secret to GitHub.

### Add Secrets Here:
**Repository Settings → Secrets and variables → Actions → New repository secret**

---

## ✅ Checklist

### Docker Hub (3 secrets)
- [ ] `DOCKER_USERNAME` = `your_docker_username`
- [ ] `DOCKER_API_TOKEN` = `dckr_pat_XXXXXXXXXXXXXXXXXXXX`
- [ ] `DOCKER_REPOSITORY` = `your_docker_username/fks-trading`

### Cloudflare (2 secrets)
- [ ] `CLOUDFLARE_API_TOKEN` = `your_cloudflare_api_token`
- [ ] `CLOUDFLARE_ZONE_ID` = `your_32_char_zone_id`

### Server IPs (2 secrets)
- [ ] `PRODUCTION_IP` = `100.114.87.27` (or your production IP)
- [ ] `STAGING_IP` = `your_staging_ip` (optional)

### Deployment (4 secrets)
- [ ] `SSH_PRIVATE_KEY` = `-----BEGIN OPENSSH PRIVATE KEY-----...`
- [ ] `DEPLOY_HOST` = `fkstrading.xyz` (or server IP)
- [ ] `DEPLOY_USER` = `jordan` (or your SSH username)
- [ ] `DEPLOY_PATH` = `/home/jordan/nextcloud/code/repos/fks`

### Optional
- [ ] `SLACK_WEBHOOK` = `https://hooks.slack.com/services/...` (optional)

---

## Quick Links

### Create Tokens Here:
- **Docker API Token**: https://hub.docker.com/settings/security
- **Cloudflare API Token**: https://dash.cloudflare.com/profile/api-tokens
- **Cloudflare Zone ID**: https://dash.cloudflare.com/ → Select domain → Copy Zone ID from sidebar

### SSH Key Generation:
```bash
# Generate new SSH key for GitHub Actions
ssh-keygen -t ed25519 -C "github-actions-fks" -f ~/.ssh/github_actions_fks

# View private key (add to GitHub secret)
cat ~/.ssh/github_actions_fks

# View public key (add to server's ~/.ssh/authorized_keys)
cat ~/.ssh/github_actions_fks.pub
```

---

## Quick Setup Commands

### 1. Docker Hub
```bash
# Go to: https://hub.docker.com/settings/security
# Create token with Read & Write permissions
# Copy token starting with: dckr_pat_
```

### 2. Cloudflare
```bash
# API Token: https://dash.cloudflare.com/profile/api-tokens
# Permissions: Zone.DNS (Edit), Zone.Zone (Read)
# Zone: fkstrading.xyz

# Zone ID: https://dash.cloudflare.com/
# Select fkstrading.xyz → Copy Zone ID from right sidebar
```

### 3. Server Setup
```bash
# Generate SSH key
ssh-keygen -t ed25519 -C "github-actions" -f ~/.ssh/gh_actions

# Copy private key for GitHub secret
cat ~/.ssh/gh_actions

# Add public key to server
ssh-copy-id -i ~/.ssh/gh_actions.pub user@your-server
```

---

## Test Your Secrets

### Docker
```bash
echo $DOCKER_API_TOKEN | docker login -u $DOCKER_USERNAME --password-stdin
```

### Cloudflare
```bash
curl -X GET "https://api.cloudflare.com/client/v4/user/tokens/verify" \
  -H "Authorization: Bearer $CLOUDFLARE_API_TOKEN" \
  -H "Content-Type: application/json"
```

### SSH
```bash
ssh -i ~/.ssh/gh_actions $DEPLOY_USER@$DEPLOY_HOST
```

---

## Current Values for Your Setup

Based on your current configuration:

```
PRODUCTION_IP = 100.114.87.27  (Tailscale IP for desktop-win)
DEPLOY_HOST = fkstrading.xyz (or 100.114.87.27)
DEPLOY_USER = jordan (or your username)
DEPLOY_PATH = /home/jordan/nextcloud/code/repos/fks
DOCKER_REPOSITORY = yourusername/fks-trading
```

---

## Total Secrets Needed

- **Required**: 10 secrets
- **Optional**: 2 secrets (STAGING_IP, SLACK_WEBHOOK)
- **Time to setup**: ~15-20 minutes

---

## See Full Documentation

For detailed setup instructions, see:
- **`GITHUB_SECRETS_SETUP.md`** - Complete guide with examples
- **`GITHUB_SECRETS_QUICKREF.md`** - Quick reference table
- **`docs/CLOUDFLARE_GITHUB_ACTIONS_SETUP.md`** - Cloudflare-specific guide

---

**Last Updated**: October 17, 2025
