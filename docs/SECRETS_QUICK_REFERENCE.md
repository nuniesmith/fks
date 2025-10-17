# 🔐 GitHub Secrets Quick Reference

## ⚡ Quick Setup (4 New Secrets)

### 1. CLOUDFLARE_API_TOKEN
```
📍 Source: https://dash.cloudflare.com/profile/api-tokens
🔑 Permissions: Zone:Zone:Read + Zone:DNS:Edit + Zone:Zone Settings:Edit
🎯 Scope: Include specific zone → fkstrading.xyz
📋 Value: Your custom API token
```

### 2. CLOUDFLARE_ZONE_ID  
```
📍 Source: https://dash.cloudflare.com/ → fkstrading.xyz → API section
📋 Value: 32-character hex string from right sidebar
```

### 3. ADMIN_EMAIL
```
📧 Value: your-email@example.com
ℹ️  Used for: Let's Encrypt certificate registration & renewal notifications
```

### 4. DOMAIN_NAME (Optional)
```
🌐 Value: fkstrading.xyz
ℹ️  Optional: Has default value in workflow
```

## 🚀 Add to GitHub

1. Go to: `https://github.com/[username]/fks/settings/secrets/actions`
2. Click "New repository secret"  
3. Add each secret above

## ✅ Test

After adding secrets:
1. Run workflow manually
2. Check logs for SSL setup progress
3. Verify `https://fkstrading.xyz` works

## 🎯 What This Enables

- ✅ Automatic DNS management (A record updates)
- ✅ SSL certificate generation with Let's Encrypt  
- ✅ Nginx HTTPS configuration with redirects
- ✅ Certificate auto-renewal every 60 days
- ✅ Production-ready domain setup

## 🔧 Workflow Integration

The secrets are used in the `setup-ssl-domain` job in `00-complete.yml`:

```yaml
setup-ssl-domain:
  env:
    CLOUDFLARE_API_TOKEN: ${{ secrets.CLOUDFLARE_API_TOKEN }}
    CLOUDFLARE_ZONE_ID: ${{ secrets.CLOUDFLARE_ZONE_ID }}  
    DOMAIN_NAME: ${{ secrets.DOMAIN_NAME || 'fkstrading.xyz' }}
    ADMIN_EMAIL: ${{ secrets.ADMIN_EMAIL }}
```

---
**📚 Full docs:** `docs/CLOUDFLARE_SSL_SETUP_GUIDE.md`
