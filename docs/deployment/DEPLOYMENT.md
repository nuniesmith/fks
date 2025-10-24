# 🚀 FKS Multi-Server Deployment Guide

## Overview

Your FKS deployment workflow is now properly configured for automatic deployment on commits to `main` and `develop` branches, with comprehensive cleanup capabilities and cost-optimized multi-server architecture.

## Automatic Deployment Configuration

### ✅ **Triggers**
- **Automatic**: Deploys on push to `main` or `develop` branches
- **Manual**: Workflow dispatch with customizable options

### ✅ **Deployment Modes**
- `single` - Traditional single-server deployment
- `multi-auth` - Deploy only auth server (g6-nanode-1, $5/month)
- `multi-api` - Deploy only API server (g6-standard-1, $12/month)
- `multi-web` - Deploy only web server (g6-nanode-1, $5/month)
- `multi-all` - Deploy all three servers ($22/month total)

### ✅ **Cost-Optimized Architecture**
```
🔐 Auth Server:  g6-nanode-1   (1GB RAM) - $5/month
⚡ API Server:   g6-standard-1 (2GB RAM) - $12/month
🌐 Web Server:   g6-nanode-1   (1GB RAM) - $5/month
💵 Total:        $22/month for complete multi-server setup
```

## Cleanup & Resource Management

### 🧹 **Pre-Deployment Cleanup** (New Feature)
The workflow now includes a comprehensive cleanup step that runs before deployment:

#### **Linode Servers**
- Finds and deletes old FKS servers (`fks`, `fks-auth`, `fks-api`, `fks-web`)
- Prevents orphaned servers from previous deployments
- Ensures clean environment for new deployment

#### **Cloudflare DNS Records**
- Removes old DNS records for all FKS subdomains
- Cleans up: `fks.7gram.xyz`, `auth.7gram.xyz`, `api.7gram.xyz`, `web.7gram.xyz`
- Prevents DNS conflicts during redeployment

#### **Tailscale Devices** (Optional)
- Removes old FKS devices from Tailscale network
- Requires `TAILSCALE_OAUTH_CLIENT_ID` and `TAILSCALE_OAUTH_SECRET` secrets
- Keeps your Tailscale network clean

### 🛡️ **Failure Handling**
- Automatic server cleanup on deployment failures (NVIDIA firmware conflict fixes)
- Comprehensive error reporting with server IDs and cleanup status
- DNS record cleanup on partial failures

## 🚀 Deployment Options

### Quick Deploy (Recommended)

Deploy all three servers with default settings:

```bash
# Via GitHub Actions UI:
# 1. Go to Actions tab
# 2. Select "Deploy FKS Multi-Server Service"
# 3. Click "Run workflow"
# 4. Select deployment_mode: "multi-all"
# 5. Click "Run workflow"
```

### Deployment Modes

| Mode | Description | Use Case |
|------|-------------|----------|
| `multi-all` | Deploy all three servers | **Recommended** for production |
| `single` | Traditional single-server | Development/testing |
| `multi-auth` | Deploy only auth server | Partial updates |
| `multi-api` | Deploy only API server | API-specific changes |
| `multi-web` | Deploy only web server | Frontend updates |

### Advanced Options

- **`create_new_servers`**: Create new Linode instances (default: true)
- **`update_dns`**: Update Cloudflare DNS records (default: true)
- **`target_region`**: Linode region (default: ca-central)

## 📋 Prerequisites

### Required GitHub Secrets

Your FKS repository must have these secrets configured:

#### Infrastructure Secrets
```bash
LINODE_CLI_TOKEN          # Linode API token
FKS_ROOT_PASSWORD         # Root password for servers
JORDAN_PASSWORD           # Your user password
ACTIONS_USER_PASSWORD     # Service user password
```

#### Networking Secrets
```bash
TAILSCALE_AUTH_KEY        # Tailscale auth key for VPN
TAILSCALE_OAUTH_CLIENT_ID # Optional: Tailscale OAuth
TAILSCALE_OAUTH_SECRET    # Optional: Tailscale OAuth
```

#### DNS Secrets
```bash
CLOUDFLARE_API_TOKEN      # Cloudflare API token
CLOUDFLARE_ZONE_ID        # Cloudflare zone ID for 7gram.xyz
```

#### Container Registry (Optional)
```bash
DOCKER_USERNAME           # Docker Hub username
DOCKER_TOKEN             # Docker Hub token
DISCORD_WEBHOOK_URL      # Discord notifications
```

## 🔧 Configuration Files

Ensure your FKS repository has the proper Docker Compose files for multi-server deployment:

```
fks/
├── docker-compose.auth.yml    # Auth server configuration
├── docker-compose.api.yml     # API server configuration  
├── docker-compose.web.yml     # Web server configuration
├── docker-compose.yml         # Single server fallback
├── start-multi.sh            # Multi-server startup script
└── config/                   # Configuration files
    ├── main.yaml
    └── ...
```

## 🌐 Access URLs

After successful deployment:

### Multi-Server Setup
- **Auth Portal**: https://auth.7gram.xyz
- **Trading API**: https://api.7gram.xyz  
- **Web Interface**: https://fks.7gram.xyz

### Tailscale Access (Internal)
- **Auth**: http://fks-auth:9000
- **API**: http://fks-api:8080
- **Web**: http://fks-web:80

## 🔍 Monitoring & Troubleshooting

### Check Deployment Status

1. **GitHub Actions**: Monitor the workflow progress
2. **Server Logs**: SSH into servers and check logs
3. **Service Health**: Use the built-in health checks

### Common Issues

#### Services Not Starting
```bash
# SSH into the problematic server
ssh fks_user@fks-auth  # or fks-api, fks-web

# Check service status
cd /home/fks_user/fks
docker compose ps
docker compose logs
```

#### DNS Not Resolving
- Wait 5-10 minutes for DNS propagation
- Check Cloudflare dashboard for DNS records
- Verify Tailscale connectivity as fallback

#### Connection Issues
```bash
# Test Tailscale connectivity
tailscale ping fks-auth
tailscale ping fks-api
tailscale ping fks-web

# Check if services are responding
curl http://fks-auth:9000/health
curl http://fks-api:8080/health
curl http://fks-web/health
```

## 🔄 Updates & Maintenance

### Deploying Updates

For code changes:
```bash
# Push to main branch triggers automatic deployment
git push origin main

# Or manually trigger with specific mode
# Use GitHub Actions UI with deployment_mode: "multi-all"
```

### Partial Updates

Update specific services:
```bash
# Update only API server
deployment_mode: "multi-api"

# Update only frontend
deployment_mode: "multi-web"
```

### Server Maintenance

```bash
# Recreate all servers
create_new_servers: true
deployment_mode: "multi-all"

# Update only configurations (no new servers)
create_new_servers: false
deployment_mode: "multi-all"
```

## 💰 Cost Management

Current setup cost breakdown:
- Auth Server: $5/month (1GB RAM)
- API Server: $12/month (2GB RAM)
- Web Server: $5/month (1GB RAM)
- **Total**: $22/month

### Cost Optimization Tips

1. **Use multi-server**: More efficient than single large server
2. **Monitor usage**: Scale down if needed during development
3. **Regional selection**: Choose region closest to users
4. **Scheduled shutdowns**: Stop dev servers when not in use

## 🎯 Next Steps

1. **Test Deployment**: Run a test deployment with `multi-all` mode
2. **Configure Monitoring**: Set up alerts for service health
3. **Backup Strategy**: Implement database and config backups
4. **SSL Certificates**: Ensure SSL is properly configured
5. **Performance Tuning**: Monitor and optimize based on usage

---

For questions or issues, check the [Actions repository](https://github.com/nuniesmith/actions) or the deployment logs in GitHub Actions.
