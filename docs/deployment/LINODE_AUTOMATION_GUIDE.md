# Linode Server Automation - Setup Guide

This guide5. Copy the token and add as `LINODE_CLI_TOKEN` secret

**Having issues?** See the [Linode Token Troubleshooting Guide](LINODE_TOKEN_TROUBLESHOOTING.md) for detailed help.explains how to set up automated Linode server creation using GitHub Actions and your existing StackScript.

## 🚀 Quick Overview

The automation will:
1. ✅ Create/verify a StackScript on Linode using your existing script
2. ✅ Create a new Arch Linux server (4GB, $24/month recommended)
3. ✅ Run the two-phase StackScript setup automatically
4. ✅ Monitor setup progress and provide connection details
5. ✅ Send Discord notifications on completion
6. ✅ Support Tailscale for secure access

## 📋 Required GitHub Secrets

Before using the automation, you need to configure these secrets in your GitHub repository:

### Go to: Repository → Settings → Secrets and variables → Actions → New repository secret

### 🔑 Required Secrets

| Secret Name | Description | Example | Where to Get |
|-------------|-------------|---------|--------------|
| `LINODE_CLI_TOKEN` | Linode API Personal Access Token | `abcdef123456...` | [Linode Cloud Manager → Profile → API Tokens](https://cloud.linode.com/profile/tokens) |
| `FKS_DEV_ROOT_PASSWORD` | Root password for the server | `MySecureRootPass123!` | Choose a strong password |
| `JORDAN_PASSWORD` | Password for jordan user | `MyJordanPass123!` | Choose a strong password |
| `FKS_USER_PASSWORD` | Password for fks_user | `MyFksPass123!` | Choose a strong password |
| `TAILSCALE_AUTH_KEY` | Tailscale authentication key (REQUIRED) | `tskey-auth-...` | [Tailscale Admin Console → Settings → Keys](https://login.tailscale.com/admin/settings/keys) |

### 🔑 Optional Secrets (Recommended)

| Secret Name | Description | Example | Where to Get |
|-------------|-------------|---------|--------------|
| `DOCKER_USERNAME` | Docker Hub username | `yourusername` | Your Docker Hub account |
| `DOCKER_TOKEN` | Docker Hub access token | `dckr_pat_...` | [Docker Hub → Account Settings → Security](https://hub.docker.com/settings/security) |
| `NETDATA_CLAIM_TOKEN` | Netdata Cloud claim token | `xxx-xxx-xxx` | [Netdata Cloud → Space Settings](https://app.netdata.cloud/) |
| `NETDATA_CLAIM_ROOM` | Netdata Cloud room ID | `room-id-here` | Netdata Cloud room URL |
| `DISCORD_WEBHOOK_SERVERS` | Discord webhook for notifications | `https://discord.com/api/webhooks/...` | Discord Server → Integrations → Webhooks |

## 🛠️ Step-by-Step Setup

### 1. Create Linode API Token
1. Go to [Linode Cloud Manager](https://cloud.linode.com/profile/tokens)
2. Click "Create a Personal Access Token"
3. Set Label: `GitHub Actions FKS`
4. Set Expiry: `Never` (or your preferred duration)
5. Permissions needed:
   - **Linodes**: Read/Write
   - **StackScripts**: Read/Write
   - **Images**: Read Only
6. Click "Create Token"
7. Copy the token and add as `LINODE_CLI_TOKEN` secret

### 2. Get Tailscale Auth Key (REQUIRED)
1. Go to [Tailscale Admin Console](https://login.tailscale.com/admin/settings/keys)
2. Click "Generate auth key"
3. Settings:
   - ✅ Reusable
   - ✅ Ephemeral (optional, for temporary servers)
   - Set expiration as needed
4. Copy the key and add as `TAILSCALE_AUTH_KEY` secret

### 3. Set Up Docker Hub (Optional but Recommended)
1. Go to [Docker Hub Security Settings](https://hub.docker.com/settings/security)
2. Click "New Access Token"
3. Set Description: `GitHub Actions FKS`
4. Set Permissions: `Read, Write, Delete`
5. Copy token and add as `DOCKER_TOKEN` secret
6. Add your Docker Hub username as `DOCKER_USERNAME` secret

### 4. Configure Netdata Monitoring (Optional)
1. Go to [Netdata Cloud](https://app.netdata.cloud/)
2. Create or select a Space
3. Go to Space Settings → "Connecting Nodes"
4. Copy the claim token and room ID
5. Add as `NETDATA_CLAIM_TOKEN` and `NETDATA_CLAIM_ROOM` secrets

### 5. Set Up Discord Notifications (Optional)
1. Go to your Discord server
2. Server Settings → Integrations → Webhooks
3. Create a new webhook
4. Copy the webhook URL
5. Add as `DISCORD_WEBHOOK_SERVERS` secret

## 🚀 How to Use

### Option 1: GitHub UI (Recommended)
1. Go to your repository on GitHub
2. Click "Actions" tab
3. Find "Create Linode Server with Arch Linux" workflow
4. Click "Run workflow"
5. Configure options:
   - **Server name**: `fks` (or your preferred name)
   - **Linode type**: `g6-standard-2` (4GB RAM, $24/month)
   - **Region**: Choose closest to you
   - **OS**: `linode/arch` (recommended)
   - **Enable backups**: `true` (+$2.4/month)
   - **Delete existing**: `false` (set to `true` to replace existing server)

### Option 2: GitHub CLI
```bash
gh workflow run create-linode-server.yml \
  -f server_name=fks \
  -f linode_type=g6-standard-2 \
  -f linode_region=ca-central \
  -f linode_image=linode/arch \
  -f enable_backups=true \
  -f delete_existing=false \
  -f reason="Production deployment"
```

## 📊 Server Configuration Options

### Linode Plans
| Plan | RAM | CPUs | Storage | Monthly Cost | Use Case |
|------|-----|------|---------|--------------|----------|
| `g6-standard-1` | 2GB | 1 | 50GB | $12 | Development/Testing |
| `g6-standard-2` | 4GB | 2 | 80GB | $24 | **Recommended for FKS** |
| `g6-standard-4` | 8GB | 4 | 160GB | $48 | Production/High Load |

### Regions
| Region Code | Location | Good For |
|-------------|----------|----------|
| `us-east` | Newark, NJ | US East Coast |
| `us-west` | Fremont, CA | US West Coast |
| `us-central` | Dallas, TX | US Central |
| `ca-central` | Toronto, ON | **Canada** |
| `eu-west` | London, UK | Europe |
| `ap-south` | Singapore | Asia Pacific |

### Operating Systems
| Image | Description | Recommendation |
|-------|-------------|----------------|
| `linode/arch` | **Arch Linux** | ✅ **Recommended** - Latest packages, optimized for your stack |
| `linode/ubuntu24.04` | Ubuntu 24.04 LTS | ✅ Good alternative, long-term support |
| `linode/ubuntu22.04` | Ubuntu 22.04 LTS | ✅ Stable, well-tested |

## 🔄 Workflow Process

### Phase 1: Validation & Creation (2-3 minutes)
1. ✅ Validate all required secrets
2. ✅ Install and configure Linode CLI
3. ✅ Check for existing StackScript (create if needed)
4. ✅ Delete existing server (if requested)
5. ✅ Create new Linode server

### Phase 2: Server Setup Monitoring (15-20 minutes)
1. ⏳ Wait for server to boot
2. ⏳ Monitor StackScript Phase 1 (system setup)
3. ⏳ Monitor automatic reboot
4. ⏳ Monitor StackScript Phase 2 (service setup)
5. ✅ Extract Tailscale IP for secure access
6. ✅ Send completion notification

## 📱 What You Get

### After successful completion:
- 🖥️ **Fully configured Arch Linux server**
- 🐳 **Docker environment ready**
- 🔒 **Tailscale VPN configured**
- 👤 **Users created**: `jordan` (sudo), `fks_user`, `actions_user`
- 🔥 **Firewall configured** (SSH + Tailscale only)
- 📊 **Monitoring setup** (Netdata)
- 🔑 **SSH access ready**

### Connection Information:
```bash
# Public SSH access
ssh jordan@<public-ip>

# Secure Tailscale access
ssh jordan@<tailscale-ip>

# Web interfaces (via Tailscale)
http://<tailscale-ip>:3000   # Web UI
http://<tailscale-ip>:8000   # API
http://<tailscale-ip>:19999  # Monitoring
```

## 🔧 Manual Steps After Creation

1. **SSH to your server**:
   ```bash
   ssh jordan@<server-ip>
   ```

2. **Clone your repository**:
   ```bash
   git clone https://github.com/your-username/fks.git
   cd fks
   ```

3. **Start your services**:
   ```bash
   ./start.sh
   # or
   docker compose up -d
   ```

4. **Check status**:
   ```bash
   docker compose ps
   system-status  # Custom alias created by StackScript
   ```

## 🛡️ Security Features

- 🔒 **Tailscale VPN**: All application ports restricted to Tailscale network
- 🔥 **Firewall**: Only SSH and Tailscale ports open to public
- 👤 **User Separation**: Non-root users with appropriate permissions
- 🔑 **SSH Keys**: Password + key authentication
- 📊 **Monitoring**: Fail2ban, system monitoring

## 🐛 Troubleshooting

### Common Issues:

1. **StackScript timeout**:
   - The workflow waits up to 25 minutes
   - You can SSH manually to check progress: `tail -f /var/log/fks-setup.log`

2. **Tailscale not connecting**:
   - Check auth key is valid: `tailscale status`
   - Regenerate auth key if expired

3. **SSH connection refused**:
   - Wait a few more minutes for setup to complete
   - Check server status in Linode Cloud Manager

4. **Docker services not starting**:
   - SSH to server and run: `sudo systemctl restart docker`
   - Check logs: `journalctl -u docker -f`

### Monitoring Commands:
```bash
# Check StackScript progress
tail -f /var/log/fks-setup.log

# Check Phase 2 service
sudo journalctl -u fks-phase2.service -f

# Check system status
system-status

# Check Tailscale
tailscale status
```

## 💰 Cost Breakdown

### Monthly Costs (USD):
- **Server (4GB)**: $24.00
- **Backups**: $2.40 (10% of server cost)
- **Bandwidth**: $0.00 (1TB included)
- **Total**: ~$26.40/month

### Additional Services:
- **Tailscale**: Free (up to 100 devices)
- **Netdata Cloud**: Free (community tier)
- **Discord**: Free

## 🎯 Next Steps

1. Set up the required secrets (see table above)
2. Run the workflow to create your first server
3. SSH to the server and clone your repository
4. Configure your GitHub Actions for deployment to the new server
5. Set up monitoring and alerts as needed

The automation handles all the complex server setup, so you can focus on your trading system development! 🚀
