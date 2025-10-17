# GitHub Actions CI/CD Guide

## Overview
Complete guide for GitHub Actions workflows in the FKS Trading Systems, including CI/CD pipelines, deployment automation, and troubleshooting.

## Workflows

### Main Deployment Workflow (.github/workflows/deploy.yml)
Handles automated deployment to Linode servers with the following features:
- Two-stage deployment (foundation + services)
- Automatic server creation and configuration
- SSH key management
- Docker service deployment
- Health checks and notifications

### Key Features
- **Automatic Server Detection**: Checks for existing servers before creating new ones
- **SSH Key Pre-generation**: Generates SSH keys during workflow for security
- **Tailscale VPN Integration**: Secure remote access
- **Discord Notifications**: Deployment status updates
- **Error Recovery**: Automatic rollback on failures

## GitHub Secrets Configuration

### Required Secrets
```bash
# Linode Configuration
LINODE_CLI_TOKEN          # Linode API token
LINODE_ROOT_PASSWORD  # Root password for servers
DEPLOY_USER_PASSWORD  # Deploy user password

# SSH Keys (pre-generated)
SSH_PRIVATE_KEY       # Private key for deployment
SSH_PUBLIC_KEY        # Public key for server access

# Notification Services
DISCORD_WEBHOOK       # Discord webhook URL (optional)

# VPN Configuration
TAILSCALE_AUTHKEY    # Tailscale authentication key

# SSL/Domain (if using custom domain)
CLOUDFLARE_API_TOKEN # Cloudflare API token
DOMAIN_NAME          # Your domain name
```

### Setting Up Secrets
1. Navigate to Settings > Secrets > Actions in your GitHub repository
2. Add each secret with the appropriate value
3. Ensure no trailing whitespace in secret values
4. Use strong, unique passwords for all credentials

## Deployment Process

### Stage 1: Foundation Setup
1. Creates/validates Linode server
2. Configures SSH access and security
3. Installs Docker and dependencies
4. Sets up basic firewall rules

### Stage 2: Service Deployment
1. Deploys Docker containers
2. Configures NinjaTrader services
3. Sets up monitoring and logging
4. Performs health checks

## Troubleshooting

### Common Issues

#### SSH Connection Failures
```bash
# Check SSH key format
echo "$SSH_PRIVATE_KEY" | ssh-keygen -y -f /dev/stdin

# Test connection manually
ssh -i ~/.ssh/deploy_key -o StrictHostKeyChecking=no deploy@<IP>
```

#### Linode API Errors
- Verify LINODE_CLI_TOKEN is valid and has appropriate permissions
- Check API rate limits (max 2 servers with same label)
- Ensure sufficient account balance

#### Docker Service Failures
```bash
# Check Docker status
docker ps -a
docker logs <container_name>

# Restart services
docker-compose down
docker-compose up -d
```

### Debug Mode
Enable debug logging in workflow:
```yaml
env:
  ACTIONS_RUNNER_DEBUG: true
  ACTIONS_STEP_DEBUG: true
```

## Best Practices

### Security
1. **Never commit secrets** to repository
2. **Rotate credentials** regularly
3. **Use least privilege** for API tokens
4. **Enable 2FA** on GitHub account

### Workflow Optimization
1. **Cache dependencies** to speed up builds
2. **Use matrix builds** for multiple environments
3. **Implement proper error handling**
4. **Add comprehensive logging**

### Monitoring
1. **Check workflow runs** regularly
2. **Set up notifications** for failures
3. **Monitor server resources**
4. **Review deployment logs**

## Quick Reference

### Manual Deployment
```bash
# Trigger deployment manually
gh workflow run deploy.yml

# Check workflow status
gh run list --workflow=deploy.yml

# View workflow logs
gh run view <run-id> --log
```

### Emergency Procedures
```bash
# Cancel running workflow
gh run cancel <run-id>

# Rollback deployment
git revert HEAD
git push origin main

# Access server directly
ssh -i ~/.ssh/deploy_key deploy@<server-ip>
```

## Maintenance

### Regular Tasks
- Review and update dependencies monthly
- Check for security vulnerabilities
- Update GitHub Actions versions
- Clean up old deployment artifacts

### Workflow Updates
1. Test changes in a feature branch first
2. Use workflow dispatch for testing
3. Monitor first deployment after changes
4. Document any modifications

## Additional Resources
- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Linode API Documentation](https://www.linode.com/api/v4)
- [Docker Documentation](https://docs.docker.com)
- [Tailscale Documentation](https://tailscale.com/kb)
