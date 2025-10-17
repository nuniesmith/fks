# Nginx Reverse Proxy Setup for FKS Trading Platform

## Overview

This directory contains the Nginx configuration for the FKS Trading Platform, providing:
- HTTPS reverse proxy to Django application
- SSL/TLS encryption
- Static and media file serving
- Rate limiting and security headers
- WebSocket support
- Celery Flower monitoring proxy

## Domain Configuration

**Domain:** fkstrading.xyz  
**DNS Records:**
```
A     fkstrading.xyz     → 100.114.87.27
A     www                → 100.114.87.27
```

## Quick Start

### Option 1: Self-Signed Certificate (Development/Testing)

For quick testing with self-signed certificates:

```bash
# Generate self-signed certificate
bash scripts/generate-self-signed-cert.sh

# Start all services
docker compose up -d

# Access the application
https://fkstrading.xyz
```

**Note:** Browsers will show a security warning. Click "Advanced" → "Proceed to site (unsafe)"

### Option 2: Let's Encrypt Certificate (Production)

For production with trusted certificates:

```bash
# Ensure DNS is configured and pointing to your server
# Run the setup script (requires root)
sudo bash scripts/setup-nginx-ssl.sh

# Select option 2 for Let's Encrypt
```

### All-in-One Setup Script

```bash
bash scripts/setup-nginx-ssl.sh
```

Interactive menu with options:
1. Generate self-signed SSL certificate
2. Setup Let's Encrypt SSL certificate
3. Start services (if certificates exist)
4. View current status

## Directory Structure

```
nginx/
├── nginx.conf              # Main Nginx configuration
├── conf.d/
│   └── fkstrading.xyz.conf # Site-specific configuration
└── ssl/
    ├── fkstrading.xyz.crt  # SSL certificate
    └── fkstrading.xyz.key  # SSL private key
```

## URL Routes

| Path | Backend | Description |
|------|---------|-------------|
| `/` | Django | Main application |
| `/api/` | Django | REST API endpoints |
| `/admin/` | Django | Django admin panel |
| `/static/` | Nginx | Static files (cached 30 days) |
| `/media/` | Nginx | User uploaded media (cached 7 days) |
| `/flower/` | Flower | Celery task monitoring |
| `/health` | Django | Health check endpoint |

## SSL Certificate Management

### Self-Signed Certificate

**Generate:**
```bash
bash scripts/generate-self-signed-cert.sh
```

**Valid for:** 365 days  
**Browser warning:** Yes (expected)

### Let's Encrypt Certificate

**Initial setup:**
```bash
sudo bash scripts/upgrade-to-letsencrypt.sh
```

**Valid for:** 90 days  
**Auto-renewal:** Configured via cron  
**Browser warning:** No (trusted by all browsers)

**Manual renewal:**
```bash
sudo certbot renew
docker compose exec nginx nginx -s reload
```

## Security Features

### HTTP to HTTPS Redirect
All HTTP traffic is automatically redirected to HTTPS.

### Security Headers
- `Strict-Transport-Security`: Force HTTPS for 1 year
- `X-Frame-Options`: Prevent clickjacking
- `X-Content-Type-Options`: Prevent MIME sniffing
- `X-XSS-Protection`: XSS protection
- `Content-Security-Policy`: Restrict resource loading
- `Referrer-Policy`: Control referrer information

### Rate Limiting
- General requests: 10 req/s (burst 20)
- API requests: 30 req/s (burst 50)
- Static files: 100 req/s (burst 50)
- Concurrent connections: 20 per IP

### SSL/TLS Configuration
- Protocols: TLSv1.2, TLSv1.3
- Strong cipher suites only
- Session caching enabled
- OCSP stapling (with Let's Encrypt)

## Performance Optimization

### Compression
- Gzip enabled for text/HTML/CSS/JS/JSON
- Compression level: 6
- Static gzip enabled

### Caching
- Static files: 30 days
- Media files: 7 days
- Browser caching headers

### Connection Management
- Keep-alive connections
- Upstream keep-alive pool
- Connection reuse

## Monitoring & Logs

### View Logs
```bash
# All Nginx logs
docker compose logs -f nginx

# Access log only
tail -f logs/nginx/fkstrading.xyz.access.log

# Error log only
tail -f logs/nginx/fkstrading.xyz.error.log
```

### Health Check
```bash
# Check Nginx status
curl -I https://fkstrading.xyz/health

# Test Nginx configuration
docker compose exec nginx nginx -t
```

### SSL Test
```bash
# Check certificate expiration
openssl x509 -in nginx/ssl/fkstrading.xyz.crt -noout -dates

# Full SSL test
curl -vI https://fkstrading.xyz

# Online SSL test
# Visit: https://www.ssllabs.com/ssltest/analyze.html?d=fkstrading.xyz
```

## Common Operations

### Reload Nginx Configuration
```bash
# Test configuration first
docker compose exec nginx nginx -t

# Reload if test passes
docker compose exec nginx nginx -s reload
```

### Restart Nginx
```bash
docker compose restart nginx
```

### Update SSL Certificates
```bash
# For self-signed
bash scripts/generate-self-signed-cert.sh
docker compose restart nginx

# For Let's Encrypt
sudo certbot renew
docker compose exec nginx nginx -s reload
```

### Add Basic Auth to Flower
```bash
# Generate password file
docker compose exec nginx sh -c "echo -n 'admin:' > /etc/nginx/.htpasswd"
docker compose exec nginx sh -c "openssl passwd -apr1 >> /etc/nginx/.htpasswd"

# Uncomment auth_basic lines in fkstrading.xyz.conf
# Reload Nginx
docker compose exec nginx nginx -s reload
```

## Troubleshooting

### Certificate Issues

**Problem:** "Certificate not trusted" error  
**Solution:** 
- Self-signed: Expected, accept the browser warning
- Let's Encrypt: Check if certificate was issued correctly
```bash
sudo certbot certificates
```

### 502 Bad Gateway

**Problem:** Nginx can't reach Django  
**Solution:**
```bash
# Check if web service is running
docker compose ps web

# Check web service logs
docker compose logs web

# Verify network connectivity
docker compose exec nginx ping web
```

### 404 Not Found for Static Files

**Problem:** Static files not loading  
**Solution:**
```bash
# Collect static files
docker compose exec web python manage.py collectstatic --noinput

# Check volume mounts
docker compose exec nginx ls -la /app/staticfiles
```

### Rate Limit Exceeded

**Problem:** "503 Service Temporarily Unavailable"  
**Solution:** Adjust rate limits in `nginx.conf`:
```nginx
limit_req_zone $binary_remote_addr zone=general:10m rate=20r/s;  # Increase rate
```

## Production Checklist

Before going live:

- [ ] DNS configured and propagated
- [ ] Let's Encrypt certificate installed
- [ ] Auto-renewal cron job configured
- [ ] Django `DEBUG = False`
- [ ] Strong `SECRET_KEY` in production
- [ ] Rate limits tested
- [ ] SSL Labs test: A+ rating
- [ ] Backup strategy for certificates
- [ ] Monitoring alerts configured
- [ ] Log rotation configured
- [ ] Firewall rules configured (allow 80, 443)
- [ ] DDoS protection (Cloudflare proxy optional)

## Cloudflare Integration (Optional)

To add Cloudflare proxy in front of Nginx:

1. **Enable Cloudflare proxy on DNS records** (orange cloud)
2. **Update Nginx to get real IP:**

```nginx
# Add to nginx.conf http block
set_real_ip_from 173.245.48.0/20;
set_real_ip_from 103.21.244.0/22;
# ... (add all Cloudflare IPs)
real_ip_header CF-Connecting-IP;
```

3. **Enable Cloudflare SSL/TLS:**
   - Set to "Full (strict)" mode
   - Upload origin certificate to Cloudflare

## Support

For issues or questions:
- Check logs: `docker compose logs nginx`
- Test config: `docker compose exec nginx nginx -t`
- Review docs: `/docs/`
- Create issue on GitHub

## Files Reference

- `nginx/nginx.conf` - Main Nginx configuration
- `nginx/conf.d/fkstrading.xyz.conf` - Site configuration
- `scripts/generate-self-signed-cert.sh` - Self-signed cert generator
- `scripts/upgrade-to-letsencrypt.sh` - Let's Encrypt setup
- `scripts/setup-nginx-ssl.sh` - Interactive setup script
- `docker-compose.yml` - Nginx service definition

---

**Last Updated:** October 17, 2025  
**Domain:** fkstrading.xyz  
**Server IP:** 100.114.87.27
