# 🔐 Cloudflare API & SSL Secrets Setup Guide

## 📋 Quick Setup Checklist

- [ ] Create Cloudflare API Token
- [ ] Get Cloudflare Zone ID
- [ ] Add 4 new GitHub secrets
- [ ] Test workflow with new secrets
- [ ] Verify SSL certificate generation

## 🔑 Required New Secrets

You need to add these **4 new secrets** to your GitHub repository:

| Secret Name | Description | Required |
|-------------|-------------|----------|
| `CLOUDFLARE_API_TOKEN` | API token for DNS management | ✅ **Required** |
| `CLOUDFLARE_ZONE_ID` | Zone ID for fkstrading.xyz | ✅ **Required** |
| `DOMAIN_NAME` | Domain name (fkstrading.xyz) | ⚠️ Optional (has default) |
| `ADMIN_EMAIL` | Email for Let's Encrypt registration | ✅ **Required** |

## 🎯 Step-by-Step Setup

### Step 1: Create Cloudflare API Token

1. **Go to Cloudflare Dashboard**
   ```
   https://dash.cloudflare.com/profile/api-tokens
   ```

2. **Click "Create Token"**

3. **Use "Custom token" template** with these exact permissions:
   ```
   🔧 Permissions:
   - Zone : Zone : Read (for all zones)
   - Zone : DNS : Edit (for fkstrading.xyz)
   - Zone : Zone Settings : Edit (for fkstrading.xyz)
   
   🎯 Zone Resources:
   - Include : Specific zone : fkstrading.xyz
   
   🔒 Client IP filtering: (optional but recommended)
   - Add GitHub Actions IP ranges if desired
   ```

4. **Create and copy the token immediately** (you won't see it again!)

### Step 2: Get Zone ID

1. **Go to your domain overview**
   ```
   https://dash.cloudflare.com/
   ```

2. **Click on "fkstrading.xyz"**

3. **Copy the Zone ID** from the right sidebar under "API" section
   - Format: `abc123def456...` (32-character string)

### Step 3: Add Secrets to GitHub

1. **Go to your repository settings**
   ```
   https://github.com/[username]/fks/settings/secrets/actions
   ```

2. **Click "New repository secret"** and add each secret:

#### Secret #1: CLOUDFLARE_API_TOKEN
```
Name: CLOUDFLARE_API_TOKEN
Value: [Paste your API token from Step 1]
```

#### Secret #2: CLOUDFLARE_ZONE_ID
```
Name: CLOUDFLARE_ZONE_ID
Value: [Paste your Zone ID from Step 2]
```

#### Secret #3: DOMAIN_NAME (Optional)
```
Name: DOMAIN_NAME
Value: fkstrading.xyz
```
*Note: This has a default value in the workflow, but setting it ensures consistency*

#### Secret #4: ADMIN_EMAIL
```
Name: ADMIN_EMAIL
Value: your-email@example.com
```
*Use a real email - Let's Encrypt will send renewal notifications here*

## ✅ Verification

After adding the secrets, you can verify they're set up correctly:

1. **Check the secrets are listed** in GitHub Settings > Secrets
2. **Run the workflow** manually to test
3. **Check the workflow logs** for SSL setup progress

## 🚀 What This Enables

With these secrets configured, your deployment will automatically:

1. **🌐 Update DNS**: Create/update A record pointing fkstrading.xyz to server IP
2. **🔒 Generate SSL Certificate**: Use Let's Encrypt with Cloudflare DNS challenge
3. **⚙️ Configure Nginx**: Set up HTTPS with automatic HTTP→HTTPS redirects
4. **🔄 Auto-Renewal**: Set up automatic certificate renewal every 60 days
5. **📢 Notifications**: Send Discord updates when SSL setup completes

## 🔧 Workflow Integration

The secrets are used in the `setup-ssl-domain` job:

```yaml
env:
  CLOUDFLARE_API_TOKEN: ${{ secrets.CLOUDFLARE_API_TOKEN }}
  CLOUDFLARE_ZONE_ID: ${{ secrets.CLOUDFLARE_ZONE_ID }}
  DOMAIN_NAME: ${{ secrets.DOMAIN_NAME || 'fkstrading.xyz' }}
  ADMIN_EMAIL: ${{ secrets.ADMIN_EMAIL }}
```

## 🚨 Troubleshooting

### Common Issues:

1. **"Invalid API token"**
   - Check token permissions include Zone:Edit for fkstrading.xyz
   - Verify token hasn't expired

2. **"Zone not found"** 
   - Double-check the Zone ID is correct
   - Ensure domain is active in Cloudflare

3. **"DNS challenge failed"**
   - Verify API token has DNS:Edit permission
   - Check domain DNS is managed by Cloudflare

4. **"Email validation failed"**
   - Use a real, accessible email address
   - Check email formatting

### Debug Commands:

```bash
# Test API token (run in workflow or locally)
curl -X GET "https://api.cloudflare.com/client/v4/user/tokens/verify" \
  -H "Authorization: Bearer YOUR_API_TOKEN"

# List zones (verify access)
curl -X GET "https://api.cloudflare.com/client/v4/zones" \
  -H "Authorization: Bearer YOUR_API_TOKEN"
```

## 🔒 Security Best Practices

1. **Use minimal permissions** - Only DNS:Edit and Zone:Read
2. **Rotate tokens regularly** - Every 90 days recommended
3. **Monitor API usage** - Check Cloudflare audit logs
4. **Use IP restrictions** - Limit to GitHub Actions IPs if possible
5. **Never commit tokens** - Only store in GitHub Secrets

## 🎉 Success Indicators

When everything is working correctly, you'll see:

- ✅ DNS A record updated in Cloudflare
- ✅ SSL certificate generated successfully  
- ✅ Nginx configured with HTTPS
- ✅ fkstrading.xyz accessible via HTTPS
- ✅ Auto-renewal cron job installed
- ✅ Discord notification sent

## 📞 Need Help?

If you encounter issues:

1. **Check workflow logs** for specific error messages
2. **Verify secrets** are correctly set in GitHub
3. **Test API token** with Cloudflare API directly
4. **Check domain status** in Cloudflare dashboard

The automated SSL setup will make your deployment production-ready with secure HTTPS access! 🚀
