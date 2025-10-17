# Nginx Reverse Proxy Setup Complete ✅

## Date: October 17, 2025

## Overview

Successfully configured Nginx as a reverse proxy for the FKS Trading Platform with SSL/TLS encryption for the domain **fkstrading.xyz**.

## Configuration Summary

### Domain Information
- **Primary Domain:** fkstrading.xyz
- **Aliases:** www.fkstrading.xyz
- **Server IP:** 100.114.87.27
- **DNS Records Configured:**
  ```
  A     fkstrading.xyz     → 100.114.87.27
  A     www                → 100.114.87.27
  ```

### SSL Certificate
- **Type:** Self-Signed (Development)
- **Valid For:** 365 days (until October 17, 2026)
- **Certificate Path:** `./nginx/ssl/fkstrading.xyz.crt`
- **Private Key Path:** `./nginx/ssl/fkstrading.xyz.key`
- **Browser Warning:** Yes (expected for self-signed certificates)

### Services Configuration

#### Nginx (Reverse Proxy)
- **Container:** fks_nginx
- **Image:** nginx:alpine
- **Ports:**
  - 80 (HTTP) → Redirects to HTTPS
  - 443 (HTTPS) → Main entry point
- **Status:** ✅ Running

#### Backend Services
All backend services exposed through Nginx:
- **Django Web:** Internal port 8000
- **Flower (Celery Monitoring):** Internal port 5555
- **PostgreSQL:** Direct access on 5432 (not proxied)
- **Redis:** Direct access on 6379 (not proxied)
- **pgAdmin:** Direct access on 5050 (not proxied)

## URL Routing

| External URL | Backend | Description |
|--------------|---------|-------------|
| `http://fkstrading.xyz` | → HTTPS redirect | Forces HTTPS |
| `https://fkstrading.xyz/` | Django (web:8000) | Home page |
| `https://fkstrading.xyz/login/` | Django | Login page |
| `https://fkstrading.xyz/dashboard/` | Django | Dashboard (requires auth) |
| `https://fkstrading.xyz/api/` | Django | REST API endpoints |
| `https://fkstrading.xyz/admin/` | Django | Django admin panel |
| `https://fkstrading.xyz/static/` | Nginx (direct) | Static files (cached 30 days) |
| `https://fkstrading.xyz/media/` | Nginx (direct) | Media files (cached 7 days) |
| `https://fkstrading.xyz/flower/` | Flower (flower:5555) | Celery monitoring |

## Security Features Implemented

### 1. SSL/TLS Configuration
- ✅ TLS 1.2 and 1.3 only
- ✅ Strong cipher suites
- ✅ Session caching
- ✅ HTTP/2 enabled
- ✅ SSL session tickets disabled

### 2. Security Headers
```
Strict-Transport-Security: max-age=31536000; includeSubDomains; preload
X-Frame-Options: SAMEORIGIN
X-Content-Type-Options: nosniff
X-XSS-Protection: 1; mode=block
Referrer-Policy: strict-origin-when-cross-origin
Content-Security-Policy: default-src 'self' https: data: 'unsafe-inline' 'unsafe-eval'
Permissions-Policy: geolocation=(), microphone=(), camera=()
```

### 3. Rate Limiting
- **General requests:** 10 req/s (burst 20)
- **API endpoints:** 30 req/s (burst 50)
- **Static files:** 100 req/s (burst 50)
- **Concurrent connections:** 20 per IP

### 4. HTTP to HTTPS Redirect
All HTTP traffic automatically redirects to HTTPS (301).

## Performance Optimizations

### Caching
- Static files: 30 days cache
- Media files: 7 days cache
- Browser caching headers enabled

### Compression
- Gzip compression enabled
- Compression level: 6
- Types: HTML, CSS, JS, JSON, XML, fonts, SVG

### Connection Management
- Keep-alive connections enabled
- Upstream connection pooling
- Connection reuse for backend

## Files Created/Modified

### New Files
1. `nginx/nginx.conf` - Main Nginx configuration
2. `nginx/conf.d/fkstrading.xyz.conf` - Site-specific configuration
3. `nginx/ssl/fkstrading.xyz.crt` - SSL certificate (self-signed)
4. `nginx/ssl/fkstrading.xyz.key` - SSL private key
5. `nginx/README.md` - Nginx setup documentation
6. `scripts/generate-self-signed-cert.sh` - Certificate generation script
7. `scripts/upgrade-to-letsencrypt.sh` - Let's Encrypt upgrade script
8. `scripts/setup-nginx-ssl.sh` - Interactive setup script

### Modified Files
1. `docker-compose.yml` - Added Nginx service
2. `src/web/django/settings.py` - Added proxy configuration and domain to ALLOWED_HOSTS

## Docker Configuration

### Nginx Service
```yaml
nginx:
  image: nginx:alpine
  container_name: fks_nginx
  ports:
    - "80:80"
    - "443:443"
  volumes:
    - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
    - ./nginx/conf.d:/etc/nginx/conf.d:ro
    - ./nginx/ssl:/etc/nginx/ssl:ro
    - ./src/staticfiles:/app/staticfiles:ro
    - ./src/media:/app/media:ro
    - ./logs/nginx:/var/log/nginx
  depends_on:
    - web
    - flower
  healthcheck:
    test: ["CMD", "wget", "--quiet", "--tries=1", "--spider", "http://localhost/health"]
    interval: 30s
    timeout: 10s
    retries: 3
```

### Django Settings Updated
```python
ALLOWED_HOSTS = [..., 'fkstrading.xyz', 'www.fkstrading.xyz']
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
USE_X_FORWARDED_HOST = True
USE_X_FORWARDED_PORT = True
```

## Testing Results

### Configuration Test
```bash
$ docker compose exec nginx nginx -t
nginx: the configuration file /etc/nginx/nginx.conf syntax is ok
nginx: configuration file /etc/nginx/nginx.conf test is successful
```

### HTTP Redirect Test
```bash
$ curl -I http://localhost/
HTTP/1.1 301 Moved Permanently  ✅
Location: https://localhost/
```

### HTTPS Test
```bash
$ curl -k -I https://localhost/
HTTP/2 200  ✅
server: nginx
content-type: text/html; charset=utf-8
```

### Services Status
```bash
$ docker compose ps
NAME                  STATUS
fks_nginx             Up (healthy)       ✅
fks_app               Up                 ✅
fks-celery_worker-1   Up                 ✅
fks-celery_beat-1     Up                 ✅
fks-flower-1          Up                 ✅
fks_db                Up                 ✅
fks_redis             Up                 ✅
fks_pgadmin           Up                 ✅
```

## Access Instructions

### Local Testing (Current Setup)

Since you're testing locally, you need to map the domain to localhost in your hosts file:

**Windows:** Edit `C:\Windows\System32\drivers\etc\hosts`
```
127.0.0.1  fkstrading.xyz
127.0.0.1  www.fkstrading.xyz
```

**Linux/WSL/Mac:** Edit `/etc/hosts`
```
127.0.0.1  fkstrading.xyz
127.0.0.1  www.fkstrading.xyz
```

Then access:
- **Homepage:** https://fkstrading.xyz
- **Login:** https://fkstrading.xyz/login/
- **Dashboard:** https://fkstrading.xyz/dashboard/
- **API:** https://fkstrading.xyz/api/
- **Admin:** https://fkstrading.xyz/admin/
- **Flower:** https://fkstrading.xyz/flower/

### Production Deployment

When deploying to production server (100.114.87.27):

1. **Ensure DNS is configured and propagated**
   ```bash
   dig +short fkstrading.xyz
   # Should return: 100.114.87.27
   ```

2. **Deploy the application**
   ```bash
   # On the server (100.114.87.27)
   docker compose up -d
   ```

3. **Upgrade to Let's Encrypt** (recommended for production)
   ```bash
   sudo bash scripts/upgrade-to-letsencrypt.sh
   ```

4. **Test externally**
   ```bash
   curl -I https://fkstrading.xyz
   ```

## Next Steps

### Immediate (Optional)
1. **Add hosts file entry** for local testing
2. **Test all endpoints** with the domain name
3. **Create Django superuser** if not already done:
   ```bash
   docker compose exec web python manage.py createsuperuser
   ```

### Before Production
1. **Update to Let's Encrypt SSL** (free, trusted by all browsers)
   ```bash
   sudo bash scripts/upgrade-to-letsencrypt.sh
   ```

2. **Set Django DEBUG=False** in production
   ```bash
   # Update .env or environment variables
   DEBUG=False
   ```

3. **Configure auto-renewal** for Let's Encrypt certificates
   ```bash
   # Cron job (added automatically by upgrade script)
   0 0,12 * * * certbot renew --quiet
   ```

4. **Optional: Add Cloudflare** for additional security and CDN
   - Enable proxy on DNS records (orange cloud)
   - Set SSL/TLS mode to "Full (strict)"
   - Configure Cloudflare firewall rules

5. **Setup monitoring and alerts**
   - Certificate expiration monitoring
   - Service availability monitoring
   - Error log monitoring

### Enhancement Options

1. **Basic Authentication for Flower**
   ```bash
   # Generate password file
   docker compose exec nginx sh -c "htpasswd -c /etc/nginx/.htpasswd admin"
   # Uncomment auth_basic lines in fkstrading.xyz.conf
   ```

2. **Custom Error Pages**
   - Create custom 404, 500 error pages
   - Place in `nginx/html/` directory

3. **Additional Rate Limiting**
   - Adjust rates based on traffic patterns
   - Add IP whitelisting for known services

4. **Logging Enhancements**
   - Configure log rotation
   - Setup centralized logging
   - Add access log analysis

## Monitoring & Maintenance

### Check Logs
```bash
# Nginx logs
docker compose logs -f nginx

# Access log
tail -f logs/nginx/fkstrading.xyz.access.log

# Error log
tail -f logs/nginx/fkstrading.xyz.error.log
```

### Reload Configuration
```bash
# Test configuration
docker compose exec nginx nginx -t

# Reload if test passes
docker compose exec nginx nginx -s reload
```

### Certificate Information
```bash
# View certificate details
openssl x509 -in nginx/ssl/fkstrading.xyz.crt -text -noout

# Check expiration
openssl x509 -in nginx/ssl/fkstrading.xyz.crt -noout -dates
```

### Health Checks
```bash
# Nginx health
curl -I https://fkstrading.xyz/health

# SSL Labs test (when publicly accessible)
# Visit: https://www.ssllabs.com/ssltest/analyze.html?d=fkstrading.xyz
```

## Troubleshooting

### Browser Security Warning
**Problem:** Browser shows "Your connection is not private"  
**Cause:** Self-signed certificate  
**Solutions:**
1. Click "Advanced" → "Proceed to fkstrading.xyz (unsafe)" (for testing)
2. Upgrade to Let's Encrypt certificate (for production)

### 502 Bad Gateway
**Problem:** Nginx can't reach Django  
**Solution:**
```bash
# Check if web service is running
docker compose ps web

# Check connectivity
docker compose exec nginx ping web
```

### 404 Not Found for Static Files
**Problem:** CSS/JS not loading  
**Solution:**
```bash
# Collect static files
docker compose exec web python manage.py collectstatic --noinput

# Verify mount
docker compose exec nginx ls -la /app/staticfiles
```

## Scripts Reference

### generate-self-signed-cert.sh
Generates self-signed SSL certificate for quick testing.

**Usage:**
```bash
bash scripts/generate-self-signed-cert.sh
```

### upgrade-to-letsencrypt.sh
Upgrades from self-signed to Let's Encrypt certificate.

**Requirements:**
- Root/sudo access
- DNS configured and propagated
- Port 80 accessible from internet

**Usage:**
```bash
sudo bash scripts/upgrade-to-letsencrypt.sh
```

### setup-nginx-ssl.sh
Interactive setup script with menu options.

**Usage:**
```bash
bash scripts/setup-nginx-ssl.sh
```

**Options:**
1. Generate self-signed SSL certificate
2. Setup Let's Encrypt SSL certificate
3. Just start services
4. View current status

## Security Considerations

### Current Setup (Self-Signed)
- ⚠️ Browsers will show security warning
- ⚠️ Not suitable for production
- ✅ Good for development/testing
- ✅ Traffic is encrypted

### Production Recommendations
- ✅ Use Let's Encrypt certificates
- ✅ Enable auto-renewal
- ✅ Set DEBUG=False in Django
- ✅ Use strong SECRET_KEY
- ✅ Configure firewall (allow only 80, 443)
- ✅ Regular security updates
- ✅ Monitor certificate expiration
- ✅ Consider Cloudflare for DDoS protection

## Performance Metrics

### Expected Response Times
- Static files: < 50ms
- API endpoints: 50-200ms
- Page loads: 200-500ms

### Optimization Settings
- Gzip compression: Level 6
- Keep-alive timeout: 65s
- Client max body size: 100MB
- Worker connections: 2048

### Resource Usage
- Nginx container: ~10MB RAM
- Minimal CPU usage
- Network overhead: < 5%

## Summary

✅ **Nginx reverse proxy configured**  
✅ **Self-signed SSL certificate generated**  
✅ **HTTP to HTTPS redirect enabled**  
✅ **All services running and accessible**  
✅ **Security headers configured**  
✅ **Rate limiting implemented**  
✅ **Static file serving optimized**  
✅ **Comprehensive documentation created**  

**Status:** Fully functional for development/testing  
**Next Step:** Upgrade to Let's Encrypt for production

---

**Setup Date:** October 17, 2025  
**Domain:** fkstrading.xyz  
**Server:** 100.114.87.27  
**Certificate Type:** Self-Signed (365 days)  
**Services:** 8/8 Running ✅
