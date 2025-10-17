# FKS Trading Systems - Simplified Deployment Guide

## 🚀 Quick Start

This guide provides a streamlined deployment process using a single script that combines all deployment stages.

### Prerequisites

- Linode account with API token
- Tailscale account with auth key
- Linux/macOS system with bash

## 📋 Step-by-Step Deployment

### Step 1: Setup Environment Variables

Run the interactive environment setup script:

```bash
./scripts/setup-env.sh
```

This will:
- Prompt you for all required credentials
- Generate secure random passwords
- Create a `.env.fks` file with your configuration
- Validate all required variables are set

### Step 2: Load Environment

Load the environment variables:

```bash
source .env.fks
```

### Step 3: Deploy

Run the deployment script:

```bash
# Full deployment (creates server, builds, deploys)
./scripts/deploy-fks.sh --mode full

# Or with a new server (force creation)
./scripts/deploy-fks.sh --mode full --force-new
```

## 🎯 Deployment Modes

### Full Deployment (Recommended)
```bash
./scripts/deploy-fks.sh --mode full
```
- Creates/detects server
- Runs Docker builds  
- Sets up server infrastructure
- Deploys applications
- Finalizes configuration

### Server Setup Only
```bash
./scripts/deploy-fks.sh --mode server-only
```
- Creates/detects server
- Sets up infrastructure
- Skips application deployment

### Deploy to Existing Server
```bash
./scripts/deploy-fks.sh --mode deploy-only --target-server 192.168.1.100
```
- Builds applications
- Deploys to specified server
- Skips server creation

### Builds Only
```bash
./scripts/deploy-fks.sh --mode builds-only
```
- Runs Docker builds only
- No server operations

## ⚙️ Configuration Options

### Server Configuration
```bash
# Custom server type
./scripts/deploy-fks.sh --mode full --type g6-standard-4

# Different region
./scripts/deploy-fks.sh --mode full --region us-east

# Specific target server
./scripts/deploy-fks.sh --mode deploy-only --target-server 192.168.1.100
```

### Build Options
```bash
# Skip builds (use existing images)
./scripts/deploy-fks.sh --mode full --skip-builds

# Force rebuild
export FORCE_CPU_BUILDS=true
./scripts/deploy-fks.sh --mode full
```

### Testing Options
```bash
# Dry run (show what would be done)
./scripts/deploy-fks.sh --mode full --dry-run

# Verbose output
./scripts/deploy-fks.sh --mode full --verbose
```

## 🔑 Required Environment Variables

The setup script will prompt for these:

| Variable | Description | Example |
|----------|-------------|---------|
| `LINODE_CLI_TOKEN` | Linode API token | `abc123...` |
| `FKS_DEV_ROOT_PASSWORD` | Root password | Auto-generated |
| `JORDAN_PASSWORD` | Jordan user password | Auto-generated |
| `FKS_USER_PASSWORD` | FKS user password | Auto-generated |
| `ACTIONS_USER_PASSWORD` | Actions user password | Auto-generated |
| `TAILSCALE_AUTH_KEY` | Tailscale auth key | `tskey-auth-...` |

## 🛡️ Security Features

### Password Management
- Automatic secure password generation
- SSH key-based authentication setup
- User isolation with sudo privileges

### Network Security
- Tailscale VPN integration
- Firewall configuration with port restrictions
- Application ports restricted to Tailscale network

### Access Control
- Multiple user accounts with different access levels
- SSH fallback authentication methods
- Automated retry logic for deployments

## 📊 Deployment Process

### Stage 0: Server Creation/Detection
- Creates new Linode server or detects existing
- Configures DNS (if new server)
- Sets up basic networking

### Stage 1: Initial Setup
- Creates user accounts
- Installs system dependencies
- Sets up SSH keys
- Configures Tailscale

### Stage 2: Application Deployment
- Tests SSH connectivity with fallback users
- Clones/updates repository
- Runs Docker containers
- Health checks

### Stage 3: Finalization
- Configures firewall rules
- Sets up monitoring
- Validates services

## 🔄 Advanced Usage

### Environment File Management
```bash
# Create new environment
./scripts/setup-env.sh

# Use existing environment
source .env.fks

# Backup environment
cp .env.fks .env.fks.backup
```

### Deployment Patterns

#### Development Workflow
```bash
# Deploy to development server
./scripts/deploy-fks.sh --mode deploy-only --target-server dev.fkstrading.xyz

# Quick redeploy without builds
./scripts/deploy-fks.sh --mode deploy-only --skip-builds
```

#### Production Workflow
```bash
# Full production deployment
./scripts/deploy-fks.sh --mode full --type g6-standard-4

# Production server with monitoring
export NETDATA_CLAIM_TOKEN="your-token"
./scripts/deploy-fks.sh --mode full
```

#### Testing Workflow
```bash
# Test deployment without changes
./scripts/deploy-fks.sh --mode full --dry-run

# Build testing only
./scripts/deploy-fks.sh --mode builds-only
```

## 🆘 Troubleshooting

### Common Issues

#### SSH Connection Failed
```bash
# Check server status
./scripts/deploy-fks.sh --mode server-only --verbose

# Test SSH manually
ssh root@SERVER_IP
```

#### Build Failures
```bash
# Clean builds
export FORCE_CPU_BUILDS=true
./scripts/deploy-fks.sh --mode builds-only
```

#### Service Startup Issues
```bash
# Deploy only with verbose logging
./scripts/deploy-fks.sh --mode deploy-only --verbose

# Manual service check
ssh jordan@SERVER_IP "docker compose ps"
```

### Debug Commands
```bash
# Check environment
./scripts/deploy-fks.sh --help

# Validate environment file
source .env.fks && echo "Environment loaded successfully"

# Test Linode CLI
linode-cli linodes list
```

## 📈 Monitoring and Maintenance

### Access Information
After successful deployment:
- **SSH**: `ssh jordan@SERVER_IP`
- **Web Interface**: `http://SERVER_IP:3000`
- **VNC Web**: `http://SERVER_IP:6080`
- **API**: `http://SERVER_IP:8002`

### Health Checks
```bash
# Service status
ssh jordan@SERVER_IP "docker compose ps"

# System resources
ssh jordan@SERVER_IP "htop"

# Logs
ssh jordan@SERVER_IP "docker compose logs -f"
```

### Updates
```bash
# Application update
./scripts/deploy-fks.sh --mode deploy-only

# System updates
ssh jordan@SERVER_IP "sudo pacman -Syu"
```

## 🎉 Success!

After deployment completes successfully:

1. **Connect via Tailscale**: More secure than direct IP
2. **Test web interfaces**: Verify all services are running
3. **Configure trading settings**: Update configuration as needed
4. **Set up monitoring**: Enable Netdata if desired
5. **Backup configuration**: Save your environment file securely

## 🔗 Related Documentation

- [GitHub Actions Deployment](./GITHUB_ACTIONS_GUIDE.md) - Automated CI/CD
- [Manual Deployment](./DEPLOYMENT_GUIDE.md) - Detailed manual process
- [Troubleshooting Guide](./TROUBLESHOOTING.md) - Common issues and solutions
- [Security Guide](./SECURITY.md) - Security best practices
