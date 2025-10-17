# Cloudflare + GitHub Actions Setup Checklist

Use this checklist to set up Cloudflare DNS management in your GitHub Actions workflow.

## Prerequisites

- [ ] GitHub repository access with admin permissions
- [ ] Cloudflare account with access to fkstrading.xyz domain
- [ ] Domain currently managed by Cloudflare DNS

## Step 1: Create Cloudflare API Token

### 1.1 Navigate to API Tokens Page

- [ ] Go to: https://dash.cloudflare.com/profile/api-tokens
- [ ] Click the "Create Token" button

### 1.2 Create Custom Token

- [ ] Click "Use template" next to "Edit zone DNS"
- [ ] Or click "Create Custom Token" for manual setup

### 1.3 Configure Permissions

- [ ] Add permission: **Zone** → **DNS** → **Edit**
- [ ] Add permission: **Zone** → **Zone** → **Read**

### 1.4 Configure Zone Resources

- [ ] Select: **Include** → **Specific zone** → **fkstrading.xyz**

### 1.5 Configure Client IP Address Filtering (Optional)

- [ ] Add GitHub Actions IP ranges (optional but recommended)
- [ ] Or leave as "All IPs" for simplicity

### 1.6 Set Token TTL (Optional)

- [ ] Leave as default (no expiration)
- [ ] Or set custom expiration date

### 1.7 Create and Save Token

- [ ] Click "Continue to summary"
- [ ] Review permissions and zones
- [ ] Click "Create Token"
- [ ] **IMPORTANT**: Copy the token immediately
  ```
  Token: ________________________________
  ```
- [ ] Save token in password manager or secure location
- [ ] **Note**: You won't be able to see this token again!

### 1.8 Verify Token Works

```bash
curl -X GET "https://api.cloudflare.com/client/v4/user/tokens/verify" \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  -H "Content-Type: application/json"
```

- [ ] Response shows `"success": true`
- [ ] Response shows `"status": "active"`

## Step 2: Get Cloudflare Zone ID

### 2.1 Navigate to Domain Overview

- [ ] Go to: https://dash.cloudflare.com/
- [ ] Click on **fkstrading.xyz** domain

### 2.2 Find Zone ID

- [ ] Scroll to right sidebar
- [ ] Look for "API" section
- [ ] Copy the **Zone ID** (32-character hex string)
  ```
  Zone ID: ________________________________
  ```

### 2.3 Verify Zone ID Format

- [ ] Zone ID is exactly 32 characters
- [ ] Contains only lowercase letters (a-f) and numbers (0-9)
- [ ] Example: `a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6`

## Step 3: Determine Server IP Addresses

### 3.1 Production IP

- [ ] Identify your production server IP address
- [ ] Current IP: `100.114.87.27` (Tailscale IP for desktop-win)
- [ ] Verify this is the correct production IP
  ```
  Production IP: ________________________________
  ```

### 3.2 Staging IP (Optional)

- [ ] Identify staging server IP (if using develop branch)
- [ ] Leave blank if not using staging environment
  ```
  Staging IP: ________________________________ (or N/A)
  ```

## Step 4: Add Secrets to GitHub Repository

### 4.1 Navigate to Repository Secrets

- [ ] Go to your GitHub repository
- [ ] Click **Settings** tab
- [ ] Click **Secrets and variables** → **Actions**
- [ ] You should see the "New repository secret" button

### 4.2 Add CLOUDFLARE_API_TOKEN

- [ ] Click "New repository secret"
- [ ] Name: `CLOUDFLARE_API_TOKEN`
- [ ] Value: Paste your Cloudflare API token from Step 1.7
- [ ] Click "Add secret"
- [ ] Verify secret appears in list

### 4.3 Add CLOUDFLARE_ZONE_ID

- [ ] Click "New repository secret"
- [ ] Name: `CLOUDFLARE_ZONE_ID`
- [ ] Value: Paste your Zone ID from Step 2.2
- [ ] Click "Add secret"
- [ ] Verify secret appears in list

### 4.4 Add PRODUCTION_IP

- [ ] Click "New repository secret"
- [ ] Name: `PRODUCTION_IP`
- [ ] Value: Enter your production server IP from Step 3.1
- [ ] Click "Add secret"
- [ ] Verify secret appears in list

### 4.5 Add STAGING_IP (Optional)

- [ ] Skip if not using staging environment
- [ ] Click "New repository secret"
- [ ] Name: `STAGING_IP`
- [ ] Value: Enter your staging server IP from Step 3.2
- [ ] Click "Add secret"
- [ ] Verify secret appears in list

## Step 5: Verify Existing Deployment Secrets

These should already be configured if you're using the deploy job:

- [ ] `SSH_PRIVATE_KEY` - Exists
- [ ] `DEPLOY_HOST` - Exists
- [ ] `DEPLOY_USER` - Exists
- [ ] `DEPLOY_PATH` - Exists
- [ ] `DOCKER_USERNAME` - Exists
- [ ] `DOCKER_API_TOKEN` - Exists (Docker Hub Personal Access Token)
- [ ] `DOCKER_REPOSITORY` - Exists (e.g., username/fks-trading)
- [ ] `SLACK_WEBHOOK` - Exists (or N/A if not using Slack)

## Step 6: Test the Workflow

### 6.1 Manual Trigger Test

- [ ] Go to **Actions** tab in GitHub
- [ ] Select **CI/CD Pipeline** workflow
- [ ] Click **Run workflow** button
- [ ] Select branch: **develop** (if available) or **main**
- [ ] Click **Run workflow**
- [ ] Wait for workflow to start

### 6.2 Monitor Workflow Execution

- [ ] Click on the running workflow
- [ ] Watch the `update-dns` job
- [ ] Verify it completes successfully
- [ ] Check job summary for DNS update details

### 6.3 Verify DNS in Cloudflare

- [ ] Go to Cloudflare dashboard
- [ ] Select fkstrading.xyz domain
- [ ] Click **DNS** → **Records**
- [ ] Verify A record for your domain exists
- [ ] Verify IP address matches your secret
- [ ] Check comment: "Managed by GitHub Actions - {environment}"

### 6.4 Test DNS Resolution

```bash
# Check DNS resolution
dig fkstrading.xyz +short

# Check with Cloudflare DNS
dig @1.1.1.1 fkstrading.xyz +short

# Should return your production IP (100.114.87.27 or your configured IP)
```

- [ ] DNS resolves to correct IP (may show Cloudflare proxy IP if proxied)
- [ ] No DNS errors

### 6.5 Test HTTPS Access

```bash
# Test HTTPS endpoint
curl -I https://fkstrading.xyz

# Verify Cloudflare proxy
curl -I https://fkstrading.xyz | grep -i cf-ray
```

- [ ] HTTPS responds (200 OK or redirect)
- [ ] Shows `cf-ray` header (confirms Cloudflare proxy)

## Step 7: Test Automatic Deployment

### 7.1 Test with Develop Branch (Staging)

If using staging:

```bash
git checkout develop
echo "# Test" >> README.md
git add README.md
git commit -m "Test Cloudflare DNS integration"
git push origin develop
```

- [ ] Push triggers workflow automatically
- [ ] `update-dns` job runs
- [ ] staging.fkstrading.xyz DNS updates
- [ ] Verify in Cloudflare dashboard

### 7.2 Test with Main Branch (Production)

When ready for production:

```bash
git checkout main
git merge develop
git push origin main
```

- [ ] Push triggers workflow automatically
- [ ] `update-dns` job runs
- [ ] Both fkstrading.xyz and www.fkstrading.xyz update
- [ ] `deploy` job runs after DNS updates
- [ ] Verify in Cloudflare dashboard

## Step 8: Monitoring and Alerts

### 8.1 Enable GitHub Notifications

- [ ] Go to GitHub profile → Settings → Notifications
- [ ] Enable "Actions" notifications
- [ ] Choose email or web notifications

### 8.2 Set Up Cloudflare Email Alerts (Optional)

- [ ] Go to Cloudflare dashboard
- [ ] Navigate to Notifications
- [ ] Enable "DNS record changes" alerts
- [ ] Add your email address

### 8.3 Set Up External Monitoring (Optional)

- [ ] Sign up for UptimeRobot or similar service
- [ ] Add monitor for https://fkstrading.xyz
- [ ] Set alert threshold (e.g., 5 minutes downtime)
- [ ] Configure notification method (email, SMS, Slack)

## Step 9: Documentation Review

- [ ] Read: `docs/CLOUDFLARE_GITHUB_ACTIONS_SETUP.md` (full guide)
- [ ] Read: `GITHUB_SECRETS_QUICKREF.md` (quick reference)
- [ ] Read: `docs/GITHUB_ACTIONS_CLOUDFLARE_COMPLETE.md` (summary)
- [ ] Bookmark documentation for future reference

## Step 10: Security Best Practices

- [ ] Store API token in password manager
- [ ] Never commit tokens to git
- [ ] Rotate API token every 90 days
- [ ] Review Cloudflare audit logs monthly
- [ ] Monitor GitHub Actions logs for anomalies
- [ ] Enable 2FA on Cloudflare account
- [ ] Enable 2FA on GitHub account

## Troubleshooting Checklist

If something goes wrong:

### DNS Not Updating

- [ ] Check `CLOUDFLARE_API_TOKEN` is correct
- [ ] Verify token has correct permissions
- [ ] Confirm token is active (not expired)
- [ ] Check `CLOUDFLARE_ZONE_ID` matches your domain
- [ ] Review GitHub Actions logs for errors

### Authentication Errors

- [ ] Regenerate Cloudflare API token
- [ ] Update GitHub secret with new token
- [ ] Verify token permissions include DNS edit
- [ ] Check token is for correct Cloudflare account

### Job Not Running

- [ ] Verify push was to `main` or `develop` branch
- [ ] Check it's not a pull request (job only runs on push)
- [ ] Ensure `docker` job completed successfully
- [ ] Review workflow conditions in `.github/staging/ci-cd.yml`

### Wrong IP Address

- [ ] Verify `PRODUCTION_IP` secret is correct
- [ ] Check `STAGING_IP` if using develop branch
- [ ] Ensure no typos in IP address
- [ ] Confirm IP format is valid (e.g., 203.0.113.42)

### DNS Propagation Issues

- [ ] Wait 5-10 minutes for propagation
- [ ] Clear local DNS cache
- [ ] Check Cloudflare dashboard for record
- [ ] Query Cloudflare DNS directly: `dig @1.1.1.1 fkstrading.xyz`
- [ ] Use https://dnschecker.org/ to check global propagation

## Completion Summary

- [ ] All secrets added to GitHub
- [ ] Cloudflare API token created and verified
- [ ] Zone ID confirmed correct
- [ ] Manual workflow test passed
- [ ] Automatic workflow test passed (develop or main)
- [ ] DNS resolution verified
- [ ] HTTPS access confirmed
- [ ] Cloudflare dashboard shows correct records
- [ ] Documentation reviewed
- [ ] Monitoring set up (optional)
- [ ] Security best practices implemented

## Next Steps

After completing this checklist:

1. **Monitor First Few Deployments**
   - Watch GitHub Actions logs closely
   - Verify DNS updates work correctly
   - Check for any errors or warnings

2. **Set Up Staging Environment** (Optional)
   - Configure staging server
   - Add STAGING_IP secret
   - Test with develop branch

3. **Upgrade to Let's Encrypt** (Recommended)
   - Replace self-signed certificates
   - Use included upgrade script
   - Enable auto-renewal

4. **Configure Additional Domains** (Optional)
   - Add more DNS records if needed
   - Configure additional subdomains
   - Update Nginx configuration

## Support and Resources

- **Full Documentation**: `docs/CLOUDFLARE_GITHUB_ACTIONS_SETUP.md`
- **Quick Reference**: `GITHUB_SECRETS_QUICKREF.md`
- **Summary**: `docs/GITHUB_ACTIONS_CLOUDFLARE_COMPLETE.md`
- **Cloudflare API Docs**: https://developers.cloudflare.com/api/
- **GitHub Actions Docs**: https://docs.github.com/en/actions

---

**Checklist Version**: 1.0  
**Last Updated**: January 2025  
**Status**: Ready to Use

**Tips**:
- Print this checklist and check off items as you complete them
- Keep your token and Zone ID in a secure password manager
- Test with staging first before production
- Monitor the first few deployments closely
- Set up alerts so you know when things change

Good luck! 🚀
