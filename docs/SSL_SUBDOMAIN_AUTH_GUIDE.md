# SSL, Subdomain, and Authentication Setup Guide

This guide covers setting up SSL certificates with Let's Encrypt, configuring Cloudflare subdomains for Docker services, and adding basic authentication to nginx.

## Overview

The enhanced workflow will:
1. Create subdomains for each Docker service (api.fkstrading.xyz, web.fkstrading.xyz, etc.)
2. Generate SSL certificates using Let's Encrypt with Cloudflare DNS challenge
3. Configure nginx with SSL and basic authentication
4. Automatically manage certificate renewals

## Required Secrets

Add these to your GitHub repository secrets:

```bash
# Existing secrets you should have:
CLOUDFLARE_API_TOKEN    # Cloudflare API token with DNS edit permissions
CLOUDFLARE_ZONE_ID      # Your Cloudflare zone ID for fkstrading.xyz
DOMAIN_NAME             # fkstrading.xyz
ADMIN_EMAIL             # Your email for Let's Encrypt notifications

# New secrets to add:
NGINX_AUTH_USER         # Username for basic auth (e.g., "admin")
NGINX_AUTH_PASS         # Password for basic auth (generate a strong one)
```

## Subdomain Structure

The workflow will create these subdomains:

```
fkstrading.xyz          # Main domain (React web app)
www.fkstrading.xyz      # WWW subdomain (redirects to main)
api.fkstrading.xyz      # Python FastAPI backend
web.fkstrading.xyz      # React web app (alternative)
docs.fkstrading.xyz     # Documentation viewer
ws.fkstrading.xyz       # WebSocket connections
grafana.fkstrading.xyz  # Grafana monitoring (if enabled)
netdata.fkstrading.xyz  # Netdata monitoring (if enabled)
```

## SSL Certificate Strategy

1. **Wildcard Certificate**: Generate a single wildcard certificate for `*.fkstrading.xyz` and `fkstrading.xyz`
2. **DNS Challenge**: Use Cloudflare DNS challenge for domain validation (works without port 80 access)
3. **Auto-renewal**: Set up automatic renewal with certbot

## Basic Authentication

All services except the health check endpoints will be protected with basic authentication.

## Nginx Configuration

The enhanced nginx configuration will include:
- SSL termination for all subdomains
- Basic authentication (except health checks)
- Proper proxy headers for each service
- WebSocket support for real-time connections
- Security headers (HSTS, CSP, etc.)

## Workflow Enhancement Steps

### 1. Add DNS Management Job

This job creates all necessary DNS records:

```yaml
  setup-dns-records:
    name: 🌐 Setup DNS Records
    runs-on: self-hosted
    needs: [provision-infrastructure]
    if: needs.provision-infrastructure.outputs.server_ip != ''
    steps:
      - name: 📥 Checkout repository
        uses: actions/checkout@v4
      
      - name: 🔄 Update Cloudflare DNS Records
        env:
          SERVER_IP: ${{ needs.provision-infrastructure.outputs.server_ip }}
          CLOUDFLARE_API_TOKEN: ${{ secrets.CLOUDFLARE_API_TOKEN }}
          CLOUDFLARE_ZONE_ID: ${{ secrets.CLOUDFLARE_ZONE_ID }}
          DOMAIN_NAME: ${{ secrets.DOMAIN_NAME }}
        run: |
          # Script to create/update all subdomain records
          chmod +x scripts/deployment/setup-dns-subdomains.sh
          ./scripts/deployment/setup-dns-subdomains.sh \
            --domain "$DOMAIN_NAME" \
            --server-ip "$SERVER_IP" \
            --api-token "$CLOUDFLARE_API_TOKEN" \
            --zone-id "$CLOUDFLARE_ZONE_ID"
```

### 2. Add SSL Certificate Generation Job

This job generates wildcard SSL certificate:

```yaml
  generate-ssl-certificates:
    name: 🔐 Generate SSL Certificates
    runs-on: self-hosted
    needs: [setup-dns-records]
    steps:
      - name: 📥 Checkout repository
        uses: actions/checkout@v4
      
      - name: 🔐 Generate Wildcard SSL Certificate
        env:
          DOMAIN_NAME: ${{ secrets.DOMAIN_NAME }}
          ADMIN_EMAIL: ${{ secrets.ADMIN_EMAIL }}
          CLOUDFLARE_API_TOKEN: ${{ secrets.CLOUDFLARE_API_TOKEN }}
        run: |
          # Script to generate wildcard certificate
          chmod +x scripts/deployment/generate-wildcard-ssl.sh
          ./scripts/deployment/generate-wildcard-ssl.sh \
            --domain "$DOMAIN_NAME" \
            --email "$ADMIN_EMAIL" \
            --api-token "$CLOUDFLARE_API_TOKEN"
```

### 3. Enhanced Nginx Build

Update the nginx build to include authentication:

```yaml
  - service: nginx
    build_args: |
      BUILD_ENV=${{ github.event.inputs.environment || 'development' }}
      ENABLE_SSL=true
      ENABLE_AUTH=true
      AUTH_USER=${{ secrets.NGINX_AUTH_USER }}
      AUTH_PASS=${{ secrets.NGINX_AUTH_PASS }}
```

### 4. Deploy with SSL Job

Enhanced deployment job that configures SSL:

```yaml
  deploy-with-ssl:
    name: 🚀 Deploy with SSL
    runs-on: self-hosted
    needs: [generate-ssl-certificates, docker-builds-cpu]
    steps:
      - name: 🚀 Deploy Application with SSL
        run: |
          # Deploy with SSL configuration
          chmod +x scripts/deployment/deploy-with-ssl-auth.sh
          ./scripts/deployment/deploy-with-ssl-auth.sh \
            --target-host "$SERVER_IP" \
            --domain "$DOMAIN_NAME" \
            --ssl-cert-path "/etc/letsencrypt/live/$DOMAIN_NAME" \
            --enable-auth true
```

## New Script Files

### 1. setup-dns-subdomains.sh

Creates all necessary DNS records for subdomains.

### 2. generate-wildcard-ssl.sh

Generates wildcard SSL certificate using Cloudflare DNS challenge.

### 3. nginx-ssl-auth.conf.template

Enhanced nginx configuration template with SSL and authentication.

### 4. deploy-with-ssl-auth.sh

Deployment script that configures SSL and authentication.

## Security Considerations

1. **Basic Auth Limitations**: Basic authentication is simple but not ideal for production. Consider upgrading to OAuth2/JWT.
2. **Password Storage**: Store hashed passwords in nginx, not plaintext.
3. **SSL Configuration**: Use strong ciphers and enable HSTS.
4. **Rate Limiting**: Add rate limiting to prevent brute force attacks.
5. **Fail2ban**: Consider adding fail2ban for additional protection.

## Testing

After deployment, test each subdomain:

```bash
# Test main domain
curl -u admin:password https://fkstrading.xyz

# Test API
curl -u admin:password https://api.fkstrading.xyz/health

# Test WebSocket
wscat -c wss://ws.fkstrading.xyz -H "Authorization: Basic $(echo -n 'admin:password' | base64)"
```

## Monitoring

1. **Certificate Expiry**: Monitor certificate expiration with:
   ```bash
   certbot certificates
   ```

2. **DNS Propagation**: Verify DNS records:
   ```bash
   dig +short api.fkstrading.xyz
   ```

3. **Auth Logs**: Monitor authentication attempts:
   ```bash
   tail -f /var/log/nginx/access.log | grep 401
   ```

## Troubleshooting

### DNS Issues
- Ensure Cloudflare API token has DNS edit permissions
- Wait for DNS propagation (can take up to 48 hours)
- Use Cloudflare's DNS checker tool

### SSL Issues
- Check certbot logs: `/var/log/letsencrypt/letsencrypt.log`
- Verify DNS challenge records are created
- Ensure port 443 is open in firewall

### Authentication Issues
- Verify htpasswd file exists and has correct permissions
- Check nginx error logs for auth failures
- Test with curl using -u flag

## Next Steps

1. Implement the enhanced workflow in your 00-complete.yml
2. Add the required scripts to your repository
3. Configure the new GitHub secrets
4. Test in staging environment first
5. Consider upgrading to more sophisticated authentication (OAuth2, JWT)
