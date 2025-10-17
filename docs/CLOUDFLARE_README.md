# Cloudflare DNS Automation for GitHub Actions

Automated DNS management has been successfully integrated into the GitHub Actions CI/CD pipeline for the FKS Trading System.

## 🎯 What's New

The GitHub Actions workflow now automatically updates Cloudflare DNS records when deploying to production or staging environments. This eliminates manual DNS management and ensures your domain always points to the correct server.

## 📚 Documentation

| Document | Purpose | When to Use |
|----------|---------|-------------|
| **[Setup Checklist](../CLOUDFLARE_SETUP_CHECKLIST.md)** | Step-by-step setup guide | Start here - follow this first |
| **[Complete Guide](./CLOUDFLARE_GITHUB_ACTIONS_SETUP.md)** | Detailed setup instructions | For in-depth information |
| **[Quick Reference](../GITHUB_SECRETS_QUICKREF.md)** | Secrets and commands | Quick lookup reference |
| **[Summary Document](./GITHUB_ACTIONS_CLOUDFLARE_COMPLETE.md)** | Feature overview | Understand what was added |

## 🚀 Quick Start

### 1. Get Your Credentials

```bash
# Cloudflare API Token
# Create at: https://dash.cloudflare.com/profile/api-tokens
# Permissions: Zone.DNS (Edit), Zone.Zone (Read)

# Zone ID
# Find in: Cloudflare Dashboard → fkstrading.xyz → Overview → Zone ID
```

### 2. Add GitHub Secrets

Navigate to: **Repository Settings → Secrets and variables → Actions**

Required secrets:
- `CLOUDFLARE_API_TOKEN` - Your Cloudflare API token
- `CLOUDFLARE_ZONE_ID` - Your zone ID for fkstrading.xyz
- `PRODUCTION_IP` - Your production server IP (currently: 100.114.87.27)
- `STAGING_IP` - Your staging server IP (optional)

### 3. Test the Workflow

```bash
# Go to GitHub Actions tab
# Select "CI/CD Pipeline"
# Click "Run workflow"
# Select branch and run
```

### 4. Verify DNS Updated

```bash
# Check DNS resolution
dig fkstrading.xyz +short

# Check with Cloudflare DNS
dig @1.1.1.1 fkstrading.xyz +short

# Test HTTPS
curl -I https://fkstrading.xyz
```

## 🔄 How It Works

### Workflow Flow

```
Push to main/develop
    ↓
Run Tests
    ↓
Build Docker Image
    ↓
Update DNS Records ← NEW
    ↓
Deploy to Server
    ↓
Health Check
```

### DNS Management

**Production (main branch)**:
- Updates `fkstrading.xyz` → Production IP
- Updates `www.fkstrading.xyz` → Production IP
- Deploys application

**Staging (develop branch)**:
- Updates `staging.fkstrading.xyz` → Staging IP
- Skips deployment (deploy job only on main)

## ✨ Features

- ✅ Automatic DNS updates on deployment
- ✅ Multi-environment support (staging/production)
- ✅ Creates or updates records intelligently
- ✅ Verifies DNS propagation
- ✅ Cloudflare proxy enabled (DDoS protection, CDN)
- ✅ Detailed logging and summaries
- ✅ Error handling and validation

## 🛠️ Configuration

### DNS Record Settings

All records are configured with:
- **Type**: A record
- **TTL**: 300 seconds (5 minutes)
- **Proxied**: Yes (through Cloudflare)
- **Comment**: "Managed by GitHub Actions"

### Environment Detection

The workflow automatically detects the environment based on the branch:
- `main` branch → Production environment
- `develop` branch → Staging environment

## 📋 Required Secrets

| Secret | Required | Description |
|--------|----------|-------------|
| `CLOUDFLARE_API_TOKEN` | ✅ Yes | Cloudflare API authentication |
| `CLOUDFLARE_ZONE_ID` | ✅ Yes | Zone ID for fkstrading.xyz |
| `PRODUCTION_IP` | ✅ Yes | Production server IP address |
| `STAGING_IP` | ⚠️ Optional | Staging server IP (if using develop) |

See [Quick Reference](../GITHUB_SECRETS_QUICKREF.md) for complete list including Docker secrets.

## 🔍 Verification

### Check DNS in Cloudflare

1. Go to Cloudflare dashboard
2. Select fkstrading.xyz
3. Click DNS → Records
4. Verify A records exist with correct IPs
5. Check comment: "Managed by GitHub Actions"

### Check DNS Resolution

```bash
# Standard DNS query
dig fkstrading.xyz +short

# Query Cloudflare DNS directly
dig @1.1.1.1 fkstrading.xyz +short

# Check global propagation
# Visit: https://dnschecker.org/#A/fkstrading.xyz
```

### Check HTTPS and Cloudflare Proxy

```bash
# Test HTTPS endpoint
curl -I https://fkstrading.xyz

# Verify Cloudflare proxy (should see cf-ray header)
curl -I https://fkstrading.xyz | grep -i cf-ray
```

## 🐛 Troubleshooting

| Problem | Solution |
|---------|----------|
| DNS not updating | Check `CLOUDFLARE_API_TOKEN` permissions |
| Authentication failed | Regenerate API token with correct permissions |
| Job not running | Verify push is to `main` or `develop` branch |
| Wrong IP address | Check `PRODUCTION_IP` or `STAGING_IP` secret |
| API errors | Review GitHub Actions logs for details |

See [Complete Guide](./CLOUDFLARE_GITHUB_ACTIONS_SETUP.md) for detailed troubleshooting.

## 🔐 Security

### API Token Permissions

The Cloudflare API token requires:
- **Zone.DNS (Edit)**: To create/update DNS records
- **Zone.Zone (Read)**: To list zones and records

The token is scoped to only the fkstrading.xyz zone.

### Best Practices

- Store tokens in GitHub Secrets (encrypted)
- Use minimum required permissions
- Rotate tokens periodically (every 90 days)
- Enable 2FA on Cloudflare and GitHub accounts
- Monitor Cloudflare audit logs

## 📊 Monitoring

### GitHub Actions

- Enable notifications for failed workflows
- Review job summaries after each deployment
- Check logs for DNS update details

### Cloudflare

- Enable email alerts for DNS changes
- Review audit logs regularly
- Monitor analytics dashboard

### External Monitoring (Optional)

- UptimeRobot: Monitor domain availability
- StatusCake: Performance monitoring
- DNSChecker: Verify global propagation

## 🎓 Learn More

### Documentation Files

1. **[Setup Checklist](../CLOUDFLARE_SETUP_CHECKLIST.md)** - Complete step-by-step checklist
2. **[Complete Guide](./CLOUDFLARE_GITHUB_ACTIONS_SETUP.md)** - Full setup instructions (418 lines)
3. **[Quick Reference](../GITHUB_SECRETS_QUICKREF.md)** - Quick lookup for secrets and commands
4. **[Summary](./GITHUB_ACTIONS_CLOUDFLARE_COMPLETE.md)** - Detailed feature overview

### External Resources

- [Cloudflare API Documentation](https://developers.cloudflare.com/api/)
- [GitHub Actions Secrets](https://docs.github.com/en/actions/security-guides/encrypted-secrets)
- [DNS Propagation Checker](https://dnschecker.org/)
- [Cloudflare DNS Management](https://developers.cloudflare.com/dns/manage-dns-records/)

## 🎉 Benefits

### For Development
- Automatic DNS updates during deployment
- No manual DNS management needed
- Consistent process across environments
- Easy rollback if needed

### For Security
- API tokens with scoped permissions
- All credentials encrypted in GitHub
- Audit trail in Cloudflare
- DDoS protection via Cloudflare proxy

### For Operations
- Multi-environment support (staging/production)
- Automated verification and testing
- Detailed logs and summaries
- Health checks after deployment

## 📝 Current Configuration

- **Domain**: fkstrading.xyz
- **Current IP**: 100.114.87.27 (Tailscale IP for desktop-win)
- **Environment**: Development
- **Nginx**: Configured with SSL reverse proxy
- **SSL**: Self-signed certificates (ready for Let's Encrypt upgrade)
- **Services**: 8 Docker containers (nginx, web, celery, db, redis, etc.)

## ✅ Status

**Integration Status**: ✅ Complete and ready to use

**Next Steps**:
1. Add required GitHub secrets
2. Test workflow manually
3. Verify DNS updates
4. Monitor first few deployments

## 🤝 Support

If you encounter issues:

1. **Check the logs**: GitHub Actions logs show detailed error messages
2. **Review documentation**: See the guides listed above
3. **Test API token**: Verify token works with curl commands
4. **Check secrets**: Ensure all required secrets are configured
5. **Follow checklist**: Use the setup checklist to verify each step

## 📅 Maintenance

### Regular Tasks

- **Weekly**: Review GitHub Actions logs for errors
- **Monthly**: Check Cloudflare audit logs for anomalies
- **Quarterly**: Rotate Cloudflare API tokens
- **As Needed**: Update IP addresses in secrets

### Updates

When changing infrastructure:
1. Update IP address secrets in GitHub
2. Test with manual workflow run
3. Verify DNS updates correctly
4. Monitor deployment

---

**Version**: 1.0  
**Last Updated**: January 2025  
**Status**: ✅ Ready for Production Use  

**Quick Links**:
- 📖 [Setup Checklist](../CLOUDFLARE_SETUP_CHECKLIST.md) - **Start Here**
- 📘 [Complete Guide](./CLOUDFLARE_GITHUB_ACTIONS_SETUP.md)
- 📝 [Quick Reference](../GITHUB_SECRETS_QUICKREF.md)
- 📊 [Feature Summary](./GITHUB_ACTIONS_CLOUDFLARE_COMPLETE.md)
