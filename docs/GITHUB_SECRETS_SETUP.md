# GitHub Secrets Setup Guide

Complete list of all secrets required for the FKS Trading System CI/CD pipeline.

## How to Add Secrets

1. Go to your GitHub repository
2. Click **Settings** tab
3. Navigate to **Secrets and variables** → **Actions**
4. Click **New repository secret**
5. Enter the secret name and value
6. Click **Add secret**

---

## Required Secrets

### 🐳 Docker Hub Secrets (Required for Building/Pushing Images)

#### `DOCKER_USERNAME`
- **Description**: Your Docker Hub username
- **Example**: `yourusername`
- **How to get**: Your Docker Hub account username
- **Required**: ✅ Yes
- **Used in**: Docker build and push job

#### `DOCKER_API_TOKEN`
- **Description**: Docker Hub Personal Access Token (PAT)
- **Example**: `dckr_pat_abcd1234efgh5678ijkl9012mnop3456`
- **How to get**:
  1. Go to https://hub.docker.com/settings/security
  2. Click "New Access Token"
  3. Description: "GitHub Actions CI/CD"
  4. Permissions: Read & Write
  5. Click "Generate"
  6. Copy the token immediately (you won't see it again!)
- **Required**: ✅ Yes
- **Used in**: Docker login step

#### `DOCKER_REPOSITORY`
- **Description**: Full Docker repository path
- **Example**: `yourusername/fks-trading`
- **Format**: `username/repository-name`
- **How to get**: Combine your Docker Hub username with your repository name
- **Required**: ✅ Yes
- **Used in**: Docker metadata and build steps

---

### ☁️ Cloudflare DNS Secrets (Required for Automated DNS Management)

#### `CLOUDFLARE_API_TOKEN`
- **Description**: Cloudflare API token with DNS edit permissions
- **Example**: `a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0`
- **How to get**:
  1. Go to https://dash.cloudflare.com/profile/api-tokens
  2. Click "Create Token"
  3. Use "Edit zone DNS" template or create custom
  4. Permissions:
     - Zone → DNS → Edit
     - Zone → Zone → Read
  5. Zone Resources:
     - Include → Specific zone → fkstrading.xyz
  6. Click "Continue to summary"
  7. Click "Create Token"
  8. Copy the token immediately (you won't see it again!)
- **Required**: ✅ Yes
- **Used in**: DNS update job

#### `CLOUDFLARE_ZONE_ID`
- **Description**: Zone ID for fkstrading.xyz domain
- **Example**: `a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6`
- **Format**: 32-character hexadecimal string
- **How to get**:
  1. Go to https://dash.cloudflare.com/
  2. Click on your domain (fkstrading.xyz)
  3. Scroll to right sidebar under "API" section
  4. Copy the "Zone ID"
- **Required**: ✅ Yes
- **Used in**: DNS update job

---

### 🖥️ Server IP Secrets (Required for DNS Updates)

#### `PRODUCTION_IP`
- **Description**: Production server public IP address
- **Example**: `203.0.113.42` or `100.114.87.27` (your current Tailscale IP)
- **Format**: Standard IPv4 address (xxx.xxx.xxx.xxx)
- **How to get**:
  - Your production server's public IP
  - Currently using Tailscale IP: `100.114.87.27` for desktop-win
- **Required**: ✅ Yes (for main branch deployments)
- **Used in**: DNS update job when deploying to production

#### `STAGING_IP`
- **Description**: Staging server IP address
- **Example**: `198.51.100.42`
- **Format**: Standard IPv4 address (xxx.xxx.xxx.xxx)
- **How to get**: Your staging server's public IP
- **Required**: ⚠️ Optional (only if using develop branch for staging)
- **Used in**: DNS update job when deploying to staging

---

### 🔐 SSH Deployment Secrets (Required for Server Deployment)

#### `SSH_PRIVATE_KEY`
- **Description**: SSH private key for server access
- **Example**: 
  ```
  -----BEGIN OPENSSH PRIVATE KEY-----
  b3BlbnNzaC1rZXktdjEAAAAABG5vbmUAAAAEbm9uZQAAAAAAAAABAAABlwAAAAdzc2gtcn
  ...
  -----END OPENSSH PRIVATE KEY-----
  ```
- **How to get**:
  1. Generate SSH key pair: `ssh-keygen -t ed25519 -C "github-actions"`
  2. Copy the **private** key: `cat ~/.ssh/id_ed25519`
  3. Add **public** key to server: `~/.ssh/authorized_keys`
- **Required**: ✅ Yes (for deploy job)
- **Used in**: Deploy job for SSH authentication

#### `DEPLOY_HOST`
- **Description**: Server hostname or IP address
- **Example**: `fkstrading.xyz` or `203.0.113.42`
- **Format**: Domain name or IP address
- **How to get**: Your production server hostname or IP
- **Required**: ✅ Yes (for deploy job)
- **Used in**: Deploy job for SSH connection

#### `DEPLOY_USER`
- **Description**: SSH username for server access
- **Example**: `ubuntu` or `deploy` or `jordan`
- **Format**: Linux username
- **How to get**: The username you use to SSH into your server
- **Required**: ✅ Yes (for deploy job)
- **Used in**: Deploy job for SSH authentication

#### `DEPLOY_PATH`
- **Description**: Full path to project directory on server
- **Example**: `/home/ubuntu/fks` or `/opt/fks-trading`
- **Format**: Absolute path
- **How to get**: Where your project is located on the server
- **Required**: ✅ Yes (for deploy job)
- **Used in**: Deploy job to navigate to project directory

---

### 📢 Notification Secrets (Optional)

#### `SLACK_WEBHOOK`
- **Description**: Slack webhook URL for deployment notifications
- **Example**: `https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXXXXXX`
- **How to get**:
  1. Go to your Slack workspace
  2. Navigate to Apps → Incoming Webhooks
  3. Click "Add to Slack"
  4. Choose channel for notifications
  5. Copy the webhook URL
- **Required**: ⚠️ Optional (only if you want Slack notifications)
- **Used in**: Deploy job for success/failure notifications

---

## Complete Secrets Checklist

Use this checklist to verify all secrets are configured:

### Docker Secrets
- [ ] `DOCKER_USERNAME` - Docker Hub username
- [ ] `DOCKER_API_TOKEN` - Docker Hub Personal Access Token
- [ ] `DOCKER_REPOSITORY` - Full repository path (username/fks-trading)

### Cloudflare Secrets
- [ ] `CLOUDFLARE_API_TOKEN` - API token with DNS edit permissions
- [ ] `CLOUDFLARE_ZONE_ID` - Zone ID for fkstrading.xyz

### Server IP Secrets
- [ ] `PRODUCTION_IP` - Production server IP address
- [ ] `STAGING_IP` - Staging server IP (optional, only if using staging)

### Deployment Secrets
- [ ] `SSH_PRIVATE_KEY` - SSH private key for server access
- [ ] `DEPLOY_HOST` - Server hostname or IP
- [ ] `DEPLOY_USER` - SSH username
- [ ] `DEPLOY_PATH` - Project directory path on server

### Notification Secrets (Optional)
- [ ] `SLACK_WEBHOOK` - Slack webhook URL (optional)

---

## Quick Reference Table

| Secret Name | Required | Purpose | Where to Get |
|------------|----------|---------|--------------|
| `DOCKER_USERNAME` | ✅ Yes | Docker Hub authentication | Docker Hub account |
| `DOCKER_API_TOKEN` | ✅ Yes | Docker Hub authentication | hub.docker.com/settings/security |
| `DOCKER_REPOSITORY` | ✅ Yes | Docker image repository | username/fks-trading |
| `CLOUDFLARE_API_TOKEN` | ✅ Yes | DNS management | dash.cloudflare.com/profile/api-tokens |
| `CLOUDFLARE_ZONE_ID` | ✅ Yes | DNS zone identifier | Cloudflare dashboard → fkstrading.xyz |
| `PRODUCTION_IP` | ✅ Yes | Production DNS record | Your server's public IP |
| `STAGING_IP` | ⚠️ Optional | Staging DNS record | Your staging server IP |
| `SSH_PRIVATE_KEY` | ✅ Yes | Server deployment | Generate with ssh-keygen |
| `DEPLOY_HOST` | ✅ Yes | Deployment target | Server hostname/IP |
| `DEPLOY_USER` | ✅ Yes | SSH user | Server username |
| `DEPLOY_PATH` | ✅ Yes | Project location | Project path on server |
| `SLACK_WEBHOOK` | ⚠️ Optional | Notifications | Slack workspace settings |

---

## Example Values for Your Setup

Based on your current configuration:

```bash
# Docker Secrets
DOCKER_USERNAME=yourusername
DOCKER_API_TOKEN=dckr_pat_XXXXXXXXXXXXXXXXXXXX
DOCKER_REPOSITORY=yourusername/fks-trading

# Cloudflare Secrets
CLOUDFLARE_API_TOKEN=your_cloudflare_api_token_here
CLOUDFLARE_ZONE_ID=your_32_character_zone_id

# Server IP Secrets
PRODUCTION_IP=100.114.87.27  # Your current Tailscale IP for desktop-win
STAGING_IP=192.168.1.100     # Optional - your staging server IP

# Deployment Secrets
SSH_PRIVATE_KEY=-----BEGIN OPENSSH PRIVATE KEY-----...
DEPLOY_HOST=fkstrading.xyz   # Or your server IP
DEPLOY_USER=jordan           # Or your server username
DEPLOY_PATH=/home/jordan/nextcloud/code/repos/fks

# Optional Notifications
SLACK_WEBHOOK=https://hooks.slack.com/services/...  # Optional
```

---

## Verification Steps

### Test Docker Secrets

```bash
# Test Docker login locally
echo $DOCKER_API_TOKEN | docker login -u $DOCKER_USERNAME --password-stdin
```

### Test Cloudflare API Token

```bash
# Verify token works
curl -X GET "https://api.cloudflare.com/client/v4/user/tokens/verify" \
  -H "Authorization: Bearer YOUR_CLOUDFLARE_API_TOKEN" \
  -H "Content-Type: application/json"

# List DNS records
curl -X GET "https://api.cloudflare.com/client/v4/zones/YOUR_ZONE_ID/dns_records" \
  -H "Authorization: Bearer YOUR_CLOUDFLARE_API_TOKEN" \
  -H "Content-Type: application/json"
```

### Test SSH Connection

```bash
# Test SSH access
ssh -i /path/to/private_key $DEPLOY_USER@$DEPLOY_HOST

# Verify project path exists
ssh $DEPLOY_USER@$DEPLOY_HOST "ls -la $DEPLOY_PATH"
```

---

## Security Best Practices

### General
1. ✅ Never commit secrets to git
2. ✅ Use GitHub Secrets (encrypted at rest)
3. ✅ Rotate secrets every 90 days
4. ✅ Use minimum required permissions
5. ✅ Monitor access logs regularly

### Docker Hub
1. ✅ Use API tokens instead of passwords
2. ✅ Limit token to Read & Write permissions only
3. ✅ Set token expiry date (optional but recommended)
4. ✅ Revoke tokens immediately if compromised

### Cloudflare
1. ✅ Scope token to specific zone only
2. ✅ Use minimum permissions (DNS Edit + Zone Read)
3. ✅ Enable IP filtering if possible
4. ✅ Monitor audit logs for API usage

### SSH Keys
1. ✅ Use ed25519 or RSA 4096-bit keys
2. ✅ Use unique key for GitHub Actions (not your personal key)
3. ✅ Add passphrase to private key (optional)
4. ✅ Restrict public key in authorized_keys (optional)

### Monitoring
1. ✅ Enable GitHub Actions notifications
2. ✅ Review workflow logs regularly
3. ✅ Set up alerts for failed deployments
4. ✅ Monitor Cloudflare and Docker Hub for suspicious activity

---

## Troubleshooting

### Secret Not Working

**Check the secret value**:
- No extra spaces or newlines
- Complete value copied
- Correct secret name (case-sensitive)

**Check secret scope**:
- Secret is in repository secrets (not environment secrets)
- Workflow has access to secrets

### Docker Login Failed

**Check**:
- Username is correct
- API token is valid and not expired
- Token has Write permissions
- Repository name matches

### Cloudflare API Failed

**Check**:
- API token is valid
- Token has correct permissions (DNS Edit, Zone Read)
- Zone ID matches your domain
- Token is scoped to correct zone

### SSH Connection Failed

**Check**:
- Private key is complete (including header/footer)
- Public key is in server's authorized_keys
- Server hostname/IP is correct
- Username exists on server
- SSH port is open (default: 22)

---

## Next Steps

1. ✅ Add all required secrets to GitHub
2. ✅ Verify each secret works using test commands
3. ✅ Run workflow manually to test
4. ✅ Monitor first few deployments
5. ✅ Set up monitoring and alerts
6. ✅ Document any custom values for your team

---

## Additional Resources

- **Docker Hub Security**: https://docs.docker.com/security/for-developers/access-tokens/
- **Cloudflare API Docs**: https://developers.cloudflare.com/api/
- **GitHub Secrets**: https://docs.github.com/en/actions/security-guides/encrypted-secrets
- **SSH Key Generation**: https://docs.github.com/en/authentication/connecting-to-github-with-ssh
- **Slack Webhooks**: https://api.slack.com/messaging/webhooks

---

**Last Updated**: October 17, 2025  
**Status**: Ready for Setup  
**Total Required Secrets**: 10 (+ 2 optional)
