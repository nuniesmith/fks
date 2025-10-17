# Cloudflare DNS Management with GitHub Actions

This guide explains how to set up automated Cloudflare DNS record management through GitHub Actions CI/CD pipeline.

## Overview

The CI/CD pipeline now includes a `update-dns` job that automatically updates Cloudflare DNS records when code is pushed to `main` (production) or `develop` (staging) branches. This ensures your DNS always points to the correct server IP address.

## Features

- **Automatic DNS Updates**: Updates A records for your domain when deploying
- **Multi-Environment Support**: Separate DNS records for staging and production
- **Create or Update**: Intelligently creates new records or updates existing ones
- **WWW Subdomain**: Automatically manages www.fkstrading.xyz for production
- **DNS Verification**: Validates DNS propagation after updates
- **Cloudflare Proxy**: Records are proxied through Cloudflare for DDoS protection and CDN benefits

## Required GitHub Secrets

You need to configure the following secrets in your GitHub repository settings:

### Cloudflare Secrets

1. **`CLOUDFLARE_API_TOKEN`** (Required)
   - Cloudflare API token with DNS edit permissions
   - Create at: https://dash.cloudflare.com/profile/api-tokens
   - Permissions needed:
     - Zone.DNS (Edit)
     - Zone.Zone (Read)
   - Zone Resources: Include specific zone (fkstrading.xyz)

2. **`CLOUDFLARE_ZONE_ID`** (Required)
   - Your Cloudflare Zone ID for fkstrading.xyz
   - Find it in: Cloudflare Dashboard → Select your domain → Overview → Zone ID (right sidebar)
   - Example: `a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6`

### Server IP Secrets

3. **`PRODUCTION_IP`** (Required for main branch)
   - Your production server's public IP address
   - Example: `203.0.113.42` (replace with your actual IP)
   - Currently using: `100.114.87.27` (Tailscale IP for desktop-win)

4. **`STAGING_IP`** (Optional - only if using staging environment)
   - Your staging server's IP address
   - Example: `198.51.100.42`

### Existing Deployment Secrets

5. **`SSH_PRIVATE_KEY`** (Required for deployment)
   - SSH private key for server access
   - Already configured if you're using the deploy job

6. **`DEPLOY_HOST`** (Required for deployment)
   - Your server hostname or IP
   - Already configured if you're using the deploy job

7. **`DEPLOY_USER`** (Required for deployment)
   - SSH username for server access
   - Already configured if you're using the deploy job

8. **`DEPLOY_PATH`** (Required for deployment)
   - Path to your project on the server
   - Already configured if you're using the deploy job

9. **`DOCKER_USERNAME`** (Required for Docker Hub)
   - Docker Hub username for authentication
   - Already configured if you're building Docker images

10. **`DOCKER_API_TOKEN`** (Required for Docker Hub)
    - Docker Hub Personal Access Token (PAT)
    - More secure than password authentication
    - Create at: https://hub.docker.com/settings/security
    - Already configured if you're building Docker images

11. **`DOCKER_REPOSITORY`** (Required for Docker Hub)
    - Full Docker repository path
    - Format: `username/repository-name`
    - Example: `yourusername/fks-trading`
    - Already configured if you're building Docker images

12. **`SLACK_WEBHOOK`** (Optional)
    - Slack webhook URL for deployment notifications
    - Already configured if you're using Slack notifications

## How to Create Cloudflare API Token

1. **Go to Cloudflare Dashboard**
   - Visit: https://dash.cloudflare.com/profile/api-tokens
   - Click "Create Token"

2. **Use Custom Token Template**
   - Click "Use template" next to "Edit zone DNS"
   - Or click "Create Custom Token"

3. **Configure Permissions**
   ```
   Zone → DNS → Edit
   Zone → Zone → Read
   ```

4. **Configure Zone Resources**
   ```
   Include → Specific zone → fkstrading.xyz
   ```

5. **Configure IP Filtering** (Optional but recommended)
   - Add GitHub Actions IP ranges if you want to restrict access
   - Or leave it open to all IPs for simplicity

6. **Create and Copy Token**
   - Click "Continue to summary"
   - Click "Create Token"
   - **IMPORTANT**: Copy the token immediately - you won't see it again!

7. **Test Your Token**
   ```bash
   curl -X GET "https://api.cloudflare.com/client/v4/user/tokens/verify" \
     -H "Authorization: Bearer YOUR_TOKEN_HERE" \
     -H "Content-Type: application/json"
   ```

## How to Find Your Zone ID

1. **Go to Cloudflare Dashboard**
   - Visit: https://dash.cloudflare.com/
   - Select your domain (fkstrading.xyz)

2. **Find Zone ID**
   - Look at the right sidebar under "API" section
   - Copy the "Zone ID" value
   - It's a 32-character hexadecimal string

## Adding Secrets to GitHub

1. **Navigate to Repository Settings**
   - Go to your GitHub repository
   - Click "Settings" tab
   - Click "Secrets and variables" → "Actions"

2. **Add New Secret**
   - Click "New repository secret"
   - Enter the secret name (e.g., `CLOUDFLARE_API_TOKEN`)
   - Paste the secret value
   - Click "Add secret"

3. **Repeat for All Secrets**
   - Add all required secrets listed above

## Workflow Behavior

### Production Deployment (main branch)

When you push to `main`:
1. Tests run
2. Docker image builds
3. **DNS records update**:
   - `fkstrading.xyz` → Production IP
   - `www.fkstrading.xyz` → Production IP
4. Deploy job runs
5. Health check validates deployment

### Staging Deployment (develop branch)

When you push to `develop`:
1. Tests run
2. Docker image builds
3. **DNS records update**:
   - `staging.fkstrading.xyz` → Staging IP
4. Deploy job is skipped (only runs on main)

## DNS Record Configuration

All DNS records are created/updated with these settings:

- **Type**: A record
- **TTL**: 300 seconds (5 minutes)
- **Proxied**: Yes (through Cloudflare CDN)
- **Comment**: "Managed by GitHub Actions - {environment}"

Cloudflare proxy provides:
- DDoS protection
- SSL/TLS encryption
- CDN caching
- Bot mitigation

## Verification Steps

After a deployment, the workflow:

1. **Updates DNS via API**: Creates or updates A records
2. **Waits for propagation**: 15-second delay
3. **Checks DNS resolution**: Queries Cloudflare's DNS (1.1.1.1)
4. **Verifies via API**: Confirms record is correct in Cloudflare
5. **Generates summary**: Shows update status in GitHub Actions UI

## Manual Testing

You can trigger the workflow manually:

1. Go to "Actions" tab in GitHub
2. Select "CI/CD Pipeline"
3. Click "Run workflow"
4. Select branch (main or develop)
5. Click "Run workflow"

## Troubleshooting

### DNS Not Updating

**Problem**: DNS records aren't being updated

**Solutions**:
1. Check that `CLOUDFLARE_API_TOKEN` is valid
2. Verify token has correct permissions (Zone.DNS Edit)
3. Confirm `CLOUDFLARE_ZONE_ID` matches your domain
4. Check GitHub Actions logs for API errors

### Token Verification Failed

**Problem**: Cloudflare API returns authentication error

**Solutions**:
1. Regenerate API token with correct permissions
2. Make sure token is for the correct Cloudflare account
3. Verify token hasn't expired (tokens don't expire by default)

### DNS Propagation Issues

**Problem**: DNS shows old IP address

**Solutions**:
1. Wait for DNS propagation (can take up to 5 minutes)
2. Clear your DNS cache: `ipconfig /flushdns` (Windows) or `sudo dscacheutil -flushcache` (macOS)
3. Check Cloudflare dashboard to verify record is correct
4. For proxied records, resolution may show Cloudflare IPs (this is normal)

### Job Skipped

**Problem**: `update-dns` job doesn't run

**Solutions**:
1. Make sure you pushed to `main` or `develop` branch
2. Verify it's a push event (not a PR)
3. Check that `docker` job completed successfully
4. Review GitHub Actions logs for conditions

## Current Configuration

Based on your setup:

- **Domain**: fkstrading.xyz
- **Current IP**: 100.114.87.27 (Tailscale IP for desktop-win)
- **Environment**: Development with Nginx reverse proxy
- **SSL**: Self-signed certificates (ready for Let's Encrypt upgrade)

## Next Steps

1. **Create Cloudflare API Token**
   - Follow instructions above
   - Save token securely

2. **Get Zone ID**
   - Find in Cloudflare dashboard
   - Copy the 32-character ID

3. **Add GitHub Secrets**
   - Add both `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ZONE_ID`
   - Add `PRODUCTION_IP` (your server IP)

4. **Test the Workflow**
   - Push to `develop` branch first (if you have staging)
   - Verify DNS updates correctly
   - Then push to `main` for production

5. **Monitor First Deployment**
   - Watch GitHub Actions logs
   - Check Cloudflare dashboard
   - Verify DNS resolution with `dig fkstrading.xyz`

## Security Best Practices

1. **Use Scoped Tokens**: Only grant minimum required permissions
2. **Rotate Tokens**: Periodically regenerate API tokens
3. **Monitor Access**: Check Cloudflare audit logs for API usage
4. **Restrict IPs**: Consider IP filtering on API tokens if possible
5. **Separate Environments**: Use different tokens for staging/production if needed

## API Rate Limits

Cloudflare API rate limits:
- **Free Plan**: 1,200 requests per 5 minutes
- **Per Token**: Rate limit applies per API token

The workflow makes 2-4 API calls per deployment:
- List existing records (1-2 calls)
- Update/create records (1-2 calls)
- Verification (1 call)

You can safely run the workflow many times without hitting limits.

## Monitoring and Alerts

Consider setting up:
1. **GitHub Actions notifications**: Enable email notifications for failed workflows
2. **Cloudflare email alerts**: Get notified when DNS records change
3. **Health check monitoring**: Use a service like UptimeRobot to monitor your domain
4. **Slack/Discord webhooks**: Add workflow notifications to your team chat

## Additional Resources

- [Cloudflare API Documentation](https://developers.cloudflare.com/api/)
- [GitHub Actions Secrets](https://docs.github.com/en/actions/security-guides/encrypted-secrets)
- [DNS Propagation Checker](https://dnschecker.org/)
- [Cloudflare DNS Records](https://developers.cloudflare.com/dns/manage-dns-records/how-to/create-dns-records/)

## Support

If you encounter issues:
1. Check GitHub Actions logs for detailed error messages
2. Review Cloudflare dashboard for DNS record status
3. Test API token manually using curl commands
4. Verify all required secrets are configured
5. Check this documentation for troubleshooting steps

---

**Last Updated**: January 2025
**Workflow Version**: v1.0
**Tested With**: Cloudflare Free Plan, GitHub Actions
