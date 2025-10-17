# FKS Deployment Secret Integration Guide

## Overview
This guide documents the enhanced secret integration for your FKS deployment workflows. The workflows have been updated to utilize all the new secrets you provided, enabling enhanced security, monitoring, and configuration management.

## Enhanced Features Added

### 🔐 Security Enhancements
- **Service-specific user passwords** for each FKS server
- **Additional SSH public key authorization** for multiple devices
- **Application-level JWT and authentication secrets**
- **Nginx basic authentication** for protected endpoints

### 📊 Monitoring & Notifications
- **Netdata cloud integration** for server monitoring
- **Discord webhook notifications** for deployment status
- **SSL staging environment** support for certificate testing

### 🐳 Container Management
- **Docker Hub authentication** for private registries
- **Environment variable injection** into service containers
- **Enhanced docker-compose deployment** with secrets

### 🌐 DNS & Domain Management
- **Flexible domain configuration** using FQDN and TLD
- **Enhanced Cloudflare integration** for multiple subdomains

## Required GitHub Secrets

### 1. Server Root Passwords
```
FKS_API_ROOT_PASSWORD    # Root password for API server
FKS_WEB_ROOT_PASSWORD    # Root password for web server  
FKS_AUTH_ROOT_PASSWORD   # Root password for auth server
```

### 2. Service User Passwords
```
FKS_API_USER_PASSWORD       # Service user password for API server
FKS_WEB_USER_PASSWORD       # Service user password for web server
FKS_AUTH_USER_PASSWORD      # Service user password for auth server
FKS_API_ACTIONS_PASSWORD    # Actions user password for API server
FKS_WEB_ACTIONS_PASSWORD    # Actions user password for web server
FKS_AUTH_ACTIONS_PASSWORD   # Actions user password for auth server
```

### 3. Infrastructure Secrets
```
LINODE_CLI_TOKEN        # Linode API token for server management
JORDAN_PASSWORD         # Password for jordan user account
TAILSCALE_TAILNET      # Tailscale tailnet name
TS_OAUTH_CLIENT_ID     # Tailscale OAuth client ID
TS_OAUTH_SECRET        # Tailscale OAuth client secret
```

### 4. DNS and SSL Secrets
```
CLOUDFLARE_API_TOKEN           # Cloudflare API token for DNS management
CLOUDFLARE_ZONE_ID            # Cloudflare zone ID
FULLY_QUALIFIED_DOMAIN_NAME   # Primary FQDN (e.g., fkstrading.xyz)
TOP_LEVEL_DOMAIN              # TLD for DNS operations
SSL_STAGING                   # SSL staging environment flag (true/false)
ADMIN_EMAIL                   # Admin email for SSL certificates
```

### 5. Application Configuration
```
JWT_SECRET_KEY         # JWT signing secret for authentication
AUTHELIA_JWT_SECRET   # Authentik JWT validation secret
NGINX_AUTH_USER        # Basic auth username for Nginx
NGINX_AUTH_PASS        # Basic auth password for Nginx
```

### 6. Docker Registry
```
DOCKER_USERNAME        # Docker Hub username
DOCKER_TOKEN          # Docker Hub access token
```

### 7. Monitoring and Notifications
```
NETDATA_CLAIM_ROOM      # Netdata cloud room ID
NETDATA_CLAIM_TOKEN     # Netdata cloud claim token
DISCORD_WEBHOOK_URL     # Discord webhook URL for notifications
```

### 8. SSH Public Keys
```
DESKTOP_SSH_PUB        # Desktop machine public key
FREDDY_SSH_PUB         # Freddy's machine public key
MACBOOK_SSH_PUB        # MacBook public key
ORYX_SSH_PUB           # Oryx machine public key
SULLIVAN_SSH_PUB       # Sullivan machine public key
```

## Workflow Enhancements

### Enhanced Deploy Workflow (`actions/.github/workflows/deploy.yml`)

#### New Capabilities:
1. **Multi-SSH Key Support**: All provided SSH public keys are added to authorized_keys
2. **Environment Variable Injection**: Application secrets are injected into .env files
3. **Docker Hub Authentication**: Automatic login when deploying containers
4. **Netdata Integration**: Monitoring setup with cloud connectivity
5. **Discord Notifications**: Real-time deployment status updates

#### Stage 1 Enhancements:
- Service user password configuration
- SSL staging environment setup
- Additional SSH key authorization
- Enhanced error handling

#### Stage 2 Enhancements:
- Netdata claim token configuration
- FQDN-based domain management
- Enhanced environment variable replacement

#### Service Deployment Enhancements:
- `.env` file creation with application secrets
- Docker Hub authentication before pulls
- Service-specific docker-compose file support

### Enhanced FKS Deploy Workflow (`fks/.github/workflows/fks-deploy.yml`)

#### Service-Specific Secret Passing:
- Each FKS service (API, Web, Auth) receives its specific passwords
- Application configuration secrets shared across services
- SSH keys and monitoring tokens provided to all servers

#### Comprehensive Documentation:
- Updated comments documenting all 40+ secrets
- Clear categorization of secret types
- Usage examples and configuration notes

## Setup Instructions

### 1. Create GitHub Secrets
In your GitHub repository, navigate to Settings → Secrets → Actions and create all the secrets listed above.

### 2. Generate Required Values

#### SSH Public Keys:
```bash
# On each machine, get the public key:
cat ~/.ssh/id_rsa.pub  # or id_ed25519.pub
```

#### JWT Secrets:
```bash
# Generate strong JWT secrets:
openssl rand -base64 64
```

#### Docker Hub Token:
1. Go to Docker Hub → Account Settings → Security
2. Create a new access token
3. Use your Docker Hub username and the generated token

#### Netdata Cloud:
1. Sign up at https://netdata.cloud
2. Create a new space/room
3. Get the claim token from the space settings

#### Discord Webhook:
1. In your Discord server, go to Server Settings → Integrations
2. Create a new webhook
3. Copy the webhook URL

### 3. Update Secret Names (if needed)
If your existing secrets use different names, you have two options:

#### Option A: Rename existing secrets to match the new names
#### Option B: Update the workflow files to use your existing secret names

### 4. Test Deployment
Run a test deployment to verify all secrets are properly integrated:

```bash
# Manual workflow dispatch from GitHub Actions UI
# Or push to trigger automatic deployment
```

## Security Best Practices

### 1. Secret Rotation
- Rotate passwords and tokens regularly
- Update SSH keys when team members change
- Regenerate JWT secrets periodically

### 2. Access Control
- Limit GitHub secret access to necessary team members
- Use least-privilege principles for service accounts
- Monitor secret usage in workflow logs

### 3. Environment Separation
- Use different secrets for staging vs production
- Consider SSL_STAGING=true for test environments
- Separate Netdata rooms for different environments

## Troubleshooting

### Common Issues:

1. **Secret Not Found Errors**
   - Verify secret name matches exactly (case-sensitive)
   - Check that secret is created in the correct repository
   - Ensure secret has a value (not empty)

2. **SSH Key Authentication Failures**
   - Verify public key format (should start with ssh-rsa, ssh-ed25519, etc.)
   - Ensure no line breaks in the secret value
   - Check that corresponding private key is accessible

3. **Docker Hub Authentication Issues**
   - Verify Docker Hub username is correct
   - Ensure Docker token has appropriate permissions
   - Check for special characters in token

4. **Discord Notification Failures**
   - Verify webhook URL is complete and valid
   - Check Discord server permissions
   - Test webhook manually with curl

### Debug Steps:

1. **Check Workflow Logs**
   - Look for secret replacement patterns
   - Verify environment variable values (redacted)
   - Check SSH connection attempts

2. **Test Individual Components**
   - Test SSH keys on created servers
   - Verify Docker Hub login separately
   - Test Discord webhook with curl

3. **Validate Secret Values**
   - Check for trailing whitespace
   - Verify special characters are properly escaped
   - Ensure secrets contain expected content

## Migration Notes

### From Basic to Enhanced Workflow:
1. The old `ACTIONS_USER_PASSWORD` is now service-specific
2. Domain configuration moved from multiple secrets to FQDN-based
3. New monitoring and notification capabilities added

### Backward Compatibility:
- Workflows will fall back gracefully if new secrets are missing
- Core deployment functionality preserved
- Optional features disabled if related secrets unavailable

## Next Steps

1. **Set up all required secrets** in GitHub repository
2. **Test deployment** with a non-production service first
3. **Configure monitoring** in Netdata cloud
4. **Set up Discord notifications** for your team
5. **Document your specific secret values** in your team's secure location

## Support

For issues with the enhanced workflow integration:
1. Check this guide first
2. Review GitHub Actions workflow logs
3. Verify secret configuration
4. Test individual components in isolation

The enhanced workflows provide a robust, secure, and feature-rich deployment system that scales with your infrastructure needs while maintaining strong security practices.
