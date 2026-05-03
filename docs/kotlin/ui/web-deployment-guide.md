# Web Deployment Guide for fkstrading.xyz

**Last Updated:** 2025-01-05  
**Target Domain:** fkstrading.xyz  
**Platform:** Docker + Nginx + Kotlin Multiplatform Web Client

---

## Overview

This guide walks you through deploying the FKS Trading Platform web interface to your domain **fkstrading.xyz** using Docker and nginx. The web client is a Kotlin Multiplatform (KMP) application compiled to JavaScript/WebAssembly.

---

## Architecture

```
Internet (fkstrading.xyz)
         ↓
    [Nginx Container]  ← Main reverse proxy (port 443/80)
         ↓
    [Web Container]    ← KMP Web UI served by nginx (port 3001)
         ↓
   [Gateway Container] ← API endpoints (port 8000)
         ↓
   [Backend Services]  ← Forward, Backward, QuestDB, etc.
```

**Key Components:**
- **Nginx (Main)**: Reverse proxy handling SSL, routing, and security
- **Web Service**: Static nginx serving compiled KMP web app
- **Gateway**: Python API orchestration layer
- **Backend**: Rust trading engines + databases

---

## Prerequisites

### Required Software
- [x] Docker & Docker Compose (v2.0+)
- [x] JDK 21 (for building Kotlin web app)
- [x] Gradle 8.5+ (wrapper included)
- [x] Domain pointing to your server (fkstrading.xyz)

### Optional (Recommended)
- SSL certificate (Let's Encrypt or self-signed)
- Cloudflare for DNS + DDoS protection
- Tailscale for secure access

---

## Quick Start (5 Steps)

### Step 1: Build the Web Application

```bash
# Navigate to project root
cd /home/jordan/github/fks

# Build the KMP web app (compiles Kotlin → JavaScript)
./scripts/deployment/build_web.sh
```

**What this does:**
- Compiles Kotlin code to JavaScript (IR backend)
- Bundles dependencies with webpack
- Outputs to `src/clients/web/dist/`
- Creates `index.html`, `fks-web-kmp.js`, and assets

**Verify build:**
```bash
ls -lh src/clients/web/dist/
# Should see: index.html, *.js, *.js.map, etc.
```

### Step 2: Configure SSL Certificates

#### Option A: Self-Signed Certificates (Development)

```bash
# Create SSL directory
mkdir -p config/ssl

# Generate self-signed certificate
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout config/ssl/fkstrading.xyz.key \
  -out config/ssl/fkstrading.xyz.crt \
  -subj "/C=US/ST=State/L=City/O=FKS/CN=fkstrading.xyz"

# Set permissions
chmod 600 config/ssl/fkstrading.xyz.key
chmod 644 config/ssl/fkstrading.xyz.crt
```

#### Option B: Let's Encrypt (Production)

```bash
# Using Certbot with Docker
docker run -it --rm --name certbot \
  -v "$(pwd)/config/ssl:/etc/letsencrypt" \
  -v "$(pwd)/data/certbot:/var/www/certbot" \
  certbot/certbot certonly --webroot \
  -w /var/www/certbot \
  -d fkstrading.xyz \
  -d www.fkstrading.xyz \
  --email your@email.com \
  --agree-tos \
  --no-eff-email

# Copy certificates to nginx location
cp config/ssl/live/fkstrading.xyz/fullchain.pem config/ssl/fkstrading.xyz.crt
cp config/ssl/live/fkstrading.xyz/privkey.pem config/ssl/fkstrading.xyz.key
```

### Step 3: Configure Environment Variables

```bash
# Copy example env file
cp .env.example .env

# Edit .env with your settings
nano .env
```

**Key variables for web deployment:**
```bash
# Trading Mode
TRADING_MODE=paper  # or 'live' for production
REAL_ORDERS_ENABLED=false  # Set to true only when ready

# Bybit API (if using live trading)
BYBIT_API_KEY=your_api_key_here
BYBIT_API_SECRET=your_api_secret_here
BYBIT_TESTNET=true  # false for mainnet

# Domain (optional, defaults to localhost)
DOMAIN=fkstrading.xyz
```

### Step 4: Start Docker Services

```bash
# Start all services
docker compose up -d

# Or start specific services
docker compose up -d web gateway nginx

# View logs
docker compose logs -f web nginx
```

**Service startup order:**
1. Redis, QuestDB (dependencies)
2. Gateway (API layer)
3. Web (KMP web app)
4. Nginx (reverse proxy)

### Step 5: Verify Deployment

```bash
# Check service health
docker compose ps

# Test web service directly
curl http://localhost:3002

# Test via nginx
curl -k https://localhost/health
curl -k https://fkstrading.xyz/health

# View nginx logs
docker compose logs nginx
```

**Expected Output:**
```json
{
  "status": "healthy",
  "services": {
    "gateway": "running",
    "forward": "running",
    "backward": "running"
  }
}
```

---

## Accessing the Web Interface

### Local Access (Development)

```bash
# HTTP (redirects to HTTPS)
http://localhost

# HTTPS (with self-signed cert warning)
https://localhost

# Direct web service access
http://localhost:3002
```

### Remote Access (Production)

```bash
# Via domain (requires DNS setup)
https://fkstrading.xyz

# Via IP (if DNS not configured)
https://YOUR_SERVER_IP
```

**Browser Setup:**
- For self-signed certificates, you'll see a security warning
- Click "Advanced" → "Proceed to fkstrading.xyz"
- Or add certificate to browser trust store

---

## DNS Configuration

### Cloudflare Setup (Recommended)

1. **Add A Record:**
   ```
   Type: A
   Name: @
   Content: YOUR_SERVER_IP
   Proxy: Enabled (orange cloud)
   TTL: Auto
   ```

2. **Add CNAME for www:**
   ```
   Type: CNAME
   Name: www
   Content: fkstrading.xyz
   Proxy: Enabled
   TTL: Auto
   ```

3. **SSL/TLS Settings:**
   - SSL/TLS encryption mode: **Full** (or Full Strict with valid cert)
   - Always Use HTTPS: **On**
   - Minimum TLS Version: **1.2**

### Without Cloudflare

Update your domain registrar's DNS settings:
```
Type: A
Host: @
Value: YOUR_SERVER_IP
TTL: 3600
```

**DNS Propagation:**
- Can take 1-48 hours
- Check status: `dig fkstrading.xyz` or `nslookup fkstrading.xyz`

---

## Web Client Architecture

### Technology Stack

- **Frontend:** Kotlin Multiplatform (JS target)
- **Build System:** Gradle with Kotlin/JS plugin
- **Bundler:** Webpack 5
- **Rendering:** DOM manipulation (Compose HTML)
- **Networking:** Ktor Client (HTTP + WebSocket)
- **State Management:** Kotlin Flows

### File Structure

```
src/clients/web/
├── build.gradle.kts          # Build configuration
├── src/
│   ├── jsMain/
│   │   ├── kotlin/
│   │   │   └── xyz/fkstrading/clients/web/
│   │   │       ├── Main.kt             # Entry point
│   │   │       ├── SetupScreen.kt      # Configuration UI
│   │   │       ├── HealthContent.kt    # Health dashboard
│   │   │       ├── SignalMatrixFull.kt # Full signal view
│   │   │       ├── SignalMatrixWebSocket.kt  # Real-time signals
│   │   │       └── WebSocketClient.kt  # WebSocket handler
│   │   └── resources/
│   │       └── index.html              # HTML template
│   └── wasmJsMain/              # Future: WASM target
│       └── kotlin/
│           └── xyz/fkstrading/clients/web/
│               ├── Chart.kt
│               ├── ChartWithStream.kt
│               └── DataStream.kt
└── dist/                        # Compiled output (generated)
    ├── index.html
    ├── fks-web-kmp.js
    └── fks-web-kmp.js.map
```

### Current Features

**Implemented:**
- ✅ Health monitoring dashboard
- ✅ Real-time signal matrix (WebSocket)
- ✅ Full signal history view
- ✅ Setup/configuration screen
- ✅ API connectivity status

**Planned:**
- 🚧 Strategy configuration UI (from composeApp)
- 🚧 Live trading controls
- 🚧 Portfolio management
- 🚧 Performance charts (WASM)
- 🚧 Risk dashboard

---

## Customization

### Update Web Client Content

1. **Edit Kotlin source files:**
   ```bash
   cd src/clients/web/src/jsMain/kotlin/xyz/fkstrading/clients/web/
   nano Main.kt
   ```

2. **Rebuild:**
   ```bash
   ./scripts/deployment/build_web.sh
   ```

3. **Restart web service:**
   ```bash
   docker compose restart web
   # Or rebuild image
   docker compose up -d --build web
   ```

### Customize Nginx Configuration

**Edit main config:**
```bash
nano config/nginx/conf.d/fkstrading.xyz.conf
```

**Common customizations:**

1. **Add custom error pages:**
   ```nginx
   error_page 404 /custom_404.html;
   location = /custom_404.html {
       root /usr/share/nginx/html;
       internal;
   }
   ```

2. **Add security headers:**
   ```nginx
   add_header X-Custom-Header "FKS Trading Platform" always;
   ```

3. **Configure caching:**
   ```nginx
   location ~* \.(js|css|png|jpg|jpeg|gif|ico)$ {
       expires 1y;
       add_header Cache-Control "public, immutable";
   }
   ```

**Reload nginx:**
```bash
docker compose exec nginx nginx -s reload
```

---

## Troubleshooting

### Web Service Not Starting

**Check build output:**
```bash
ls -la src/clients/web/dist/
# Should contain index.html and .js files
```

**Solution if empty:**
```bash
# Rebuild web app
./scripts/deployment/build_web.sh

# Rebuild Docker image
docker compose build web
docker compose up -d web
```

### 502 Bad Gateway

**Cause:** Web service container is down or unhealthy

**Check:**
```bash
docker compose ps web
docker compose logs web
```

**Solution:**
```bash
# Restart web service
docker compose restart web

# Check health
docker compose exec web wget -O- http://localhost:3001/health
```

### SSL Certificate Errors

**Self-signed certificate warning:**
- Expected for development
- Browser will show "Not Secure"
- Click through warning to proceed

**Let's Encrypt renewal:**
```bash
# Renew certificates
docker run -it --rm --name certbot \
  -v "$(pwd)/config/ssl:/etc/letsencrypt" \
  -v "$(pwd)/data/certbot:/var/www/certbot" \
  certbot/certbot renew

# Reload nginx
docker compose exec nginx nginx -s reload
```

### WebSocket Connection Fails

**Check browser console:**
```javascript
// Should see:
WebSocket connection to 'wss://fkstrading.xyz/ws/' established
```

**If fails:**
1. Check nginx WebSocket config in `fkstrading.xyz.conf`
2. Verify gateway service is running: `docker compose ps gateway`
3. Check firewall allows WebSocket (ports 80/443)

### API Endpoints Return 503

**Cause:** Backend services not ready

**Check all services:**
```bash
docker compose ps
docker compose logs gateway forward backward
```

**Solution:**
```bash
# Restart in order
docker compose restart redis questdb
sleep 5
docker compose restart gateway
sleep 5
docker compose restart web nginx
```

### Build Fails with Gradle Errors

**Clear Gradle cache:**
```bash
cd src/clients
./gradlew clean
rm -rf ~/.gradle/caches/
./gradlew :web:jsBrowserDistribution --no-daemon
```

**Check JDK version:**
```bash
java -version  # Should be 21+
```

**Update Gradle wrapper:**
```bash
cd src/clients
./gradlew wrapper --gradle-version=8.5
```

---

## Performance Optimization

### Enable Gzip Compression

Already configured in `nginx.conf`:
```nginx
gzip on;
gzip_types text/javascript application/javascript;
gzip_comp_level 6;
```

### Add Browser Caching

Edit `config/nginx/conf.d/fkstrading.xyz.conf`:
```nginx
location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2)$ {
    expires 1y;
    add_header Cache-Control "public, immutable";
    access_log off;
}
```

### Enable HTTP/2

Already enabled in nginx config:
```nginx
listen 443 ssl;
http2 on;
```

### Minify JavaScript (Production Build)

Edit `src/clients/web/build.gradle.kts`:
```kotlin
js(IR) {
    browser {
        webpackTask {
            mode = org.jetbrains.kotlin.gradle.targets.js.webpack.KotlinWebpackConfig.Mode.PRODUCTION
            sourceMaps = false  // Disable in production
        }
    }
}
```

---

## Security Best Practices

### 1. Firewall Configuration

```bash
# Allow only necessary ports
sudo ufw allow 80/tcp   # HTTP
sudo ufw allow 443/tcp  # HTTPS
sudo ufw allow 22/tcp   # SSH (if needed)
sudo ufw enable
```

### 2. Rate Limiting

Already configured in nginx:
```nginx
limit_req zone=general burst=20 nodelay;
limit_conn conn_limit 20;
```

### 3. Security Headers

Verify headers:
```bash
curl -I https://fkstrading.xyz | grep -E "(X-|Strict-Transport|Content-Security)"
```

Expected:
- `Strict-Transport-Security`
- `X-Frame-Options: SAMEORIGIN`
- `X-Content-Type-Options: nosniff`
- `Content-Security-Policy`

### 4. API Key Protection

**Never commit API keys to git:**
```bash
# Ensure .env is in .gitignore
grep "^\.env$" .gitignore || echo ".env" >> .gitignore
```

**Use environment variables:**
```bash
# Set in .env (not tracked by git)
BYBIT_API_KEY=your_secret_key
BYBIT_API_SECRET=your_secret_secret
```

### 5. CORS Configuration

Gateway already handles CORS. To customize:
```python
# src/janus/gateway/main.py
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://fkstrading.xyz"],  # Restrict to your domain
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
```

---

## Monitoring & Logs

### View Logs

```bash
# All services
docker compose logs -f

# Web service only
docker compose logs -f web

# Nginx only
docker compose logs -f nginx

# Filter for errors
docker compose logs web | grep ERROR
```

### Access Grafana

```bash
# Default: http://localhost:3000
# Credentials: admin/admin (change on first login)
```

**Add Web Service Dashboard:**
1. Open Grafana → Dashboards → Import
2. Use template ID: 12708 (nginx)
3. Configure Prometheus data source

### Prometheus Metrics

```bash
# Web service metrics (if implemented)
curl http://localhost:9100/metrics

# Gateway metrics
curl http://localhost:8000/metrics
```

### Health Checks

```bash
# Overall system health
curl https://fkstrading.xyz/health

# Specific service health
curl https://fkstrading.xyz/audit/health
curl https://fkstrading.xyz/monitor/health
```

---

## Updating the Web Client

### Development Workflow

```bash
# 1. Make changes to Kotlin code
nano src/clients/web/src/jsMain/kotlin/xyz/fkstrading/clients/web/Main.kt

# 2. Rebuild
./scripts/deployment/build_web.sh

# 3. Restart web service (picks up new files from volume mount)
docker compose restart web

# 4. Clear browser cache and refresh
# Ctrl+Shift+R (hard refresh)
```

### Production Deployment

```bash
# 1. Build web app
./scripts/deployment/build_web.sh

# 2. Rebuild Docker image (includes new dist files)
docker compose build web

# 3. Deploy with zero-downtime
docker compose up -d web

# 4. Verify
curl https://fkstrading.xyz/health
```

---

## Backup & Disaster Recovery

### Backup Configuration

```bash
# Backup script
tar -czf fks-backup-$(date +%Y%m%d).tar.gz \
  config/ \
  .env \
  docker-compose.yml \
  src/clients/web/dist/

# Upload to remote storage
scp fks-backup-*.tar.gz user@backup-server:/backups/
```

### Restore from Backup

```bash
# Extract backup
tar -xzf fks-backup-20250105.tar.gz

# Rebuild web service
docker compose build web
docker compose up -d
```

---

## Advanced: Multi-Domain Setup

### Serve Multiple Domains

Create additional nginx configs:

**`config/nginx/conf.d/trading.fkstrading.xyz.conf`:**
```nginx
server {
    listen 443 ssl http2;
    server_name trading.fkstrading.xyz;

    ssl_certificate /etc/nginx/ssl/trading.fkstrading.xyz.crt;
    ssl_certificate_key /etc/nginx/ssl/trading.fkstrading.xyz.key;

    location / {
        proxy_pass http://web:3001;
        # ... same proxy settings
    }
}
```

**Build separate web apps:**
```bash
# Main app
./scripts/deployment/build_web.sh

# Trading-specific app (if different)
cd src/clients/web-trading
./gradlew jsBrowserDistribution
```

---

## Migration from Development to Production

### Checklist

- [ ] SSL certificate obtained (Let's Encrypt)
- [ ] DNS pointing to production server
- [ ] `.env` configured with production API keys
- [ ] `TRADING_MODE=live` (if ready for live trading)
- [ ] Firewall configured (only 80/443 exposed)
- [ ] Monitoring setup (Grafana, Prometheus)
- [ ] Backup system in place
- [ ] Rate limiting tested
- [ ] Load testing completed
- [ ] Security headers verified
- [ ] CORS configured for production domain
- [ ] Logs rotation configured

### Production Deployment

```bash
# Use production compose file
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Verify all services healthy
docker compose ps

# Monitor logs for issues
docker compose logs -f | grep ERROR
```

---

## Support & Resources

### Documentation
- Main README: `/home/jordan/github/fks/README.md`
- Web Client Docs: `/home/jordan/github/fks/src/clients/README.md`
- API Documentation: `https://fkstrading.xyz/api/docs`

### Logs Location
- Nginx access: `docker compose logs nginx`
- Web service: `docker compose logs web`
- Gateway API: `docker compose logs gateway`

### Common Commands

```bash
# View all running services
docker compose ps

# Restart specific service
docker compose restart web

# View resource usage
docker stats

# Clean up unused resources
docker system prune -a

# Export logs
docker compose logs > fks-logs-$(date +%Y%m%d).txt
```

---

## Next Steps

1. **Add Settings UI to Web Client**
   - Port Settings UI from composeApp to web
   - See: `docs/settings-ui-integration.md`

2. **Implement Real-Time Trading UI**
   - Strategy execution controls
   - Order management interface
   - Position monitoring

3. **Add Performance Dashboards**
   - WASM-based high-performance charts
   - Real-time P&L tracking
   - Risk metrics visualization

4. **Setup CI/CD**
   - Automated web builds on git push
   - Docker image publishing
   - Automated testing

---

**Deployment completed! Your web interface is now live at https://fkstrading.xyz** 🚀