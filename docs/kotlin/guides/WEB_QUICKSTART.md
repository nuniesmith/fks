# Web Deployment Quick Start 🚀

**Deploy the FKS Trading Platform web interface to fkstrading.xyz in 5 minutes**

---

## Prerequisites

- Docker & Docker Compose installed
- JDK 21+ installed
- Domain pointing to your server (fkstrading.xyz)

---

## Quick Deploy (Automated)

```bash
# One command to deploy everything
./scripts/deployment/deploy-web.sh
```

**What it does:**
1. ✅ Builds the Kotlin/JS web application
2. ✅ Sets up SSL certificates (self-signed or Let's Encrypt)
3. ✅ Configures environment
4. ✅ Starts Docker services (web, gateway, nginx)
5. ✅ Verifies deployment

**Access your site:**
- 🌐 https://fkstrading.xyz
- 🌐 https://localhost (local testing)

---

## Manual Deploy (Step-by-Step)

### Step 1: Build Web App

```bash
cd /home/jordan/github/fks
./scripts/deployment/build_web.sh
```

Verify: `ls src/clients/web/dist/` should show `index.html` and `.js` files

### Step 2: Setup SSL

**Development (self-signed):**
```bash
mkdir -p config/ssl
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout config/ssl/fkstrading.xyz.key \
  -out config/ssl/fkstrading.xyz.crt \
  -subj "/C=US/ST=State/L=City/O=FKS/CN=fkstrading.xyz"
```

**Production (Let's Encrypt):**
```bash
docker run -it --rm --name certbot \
  -v "$(pwd)/config/ssl:/etc/letsencrypt" \
  -v "$(pwd)/data/certbot:/var/www/certbot" \
  -p 80:80 \
  certbot/certbot certonly --standalone \
  -d fkstrading.xyz -d www.fkstrading.xyz \
  --email your@email.com --agree-tos

cp config/ssl/live/fkstrading.xyz/fullchain.pem config/ssl/fkstrading.xyz.crt
cp config/ssl/live/fkstrading.xyz/privkey.pem config/ssl/fkstrading.xyz.key
```

### Step 3: Configure Environment

```bash
cp .env.example .env
nano .env
```

**Key settings:**
```bash
TRADING_MODE=paper
REAL_ORDERS_ENABLED=false
BYBIT_TESTNET=true
```

### Step 4: Start Services

```bash
docker compose up -d
```

### Step 5: Verify

```bash
# Check services
docker compose ps

# Test web service
curl http://localhost:3002

# Test via nginx
curl -k https://localhost/health
```

---

## Common Commands

```bash
# View logs
docker compose logs -f web nginx

# Restart services
docker compose restart web nginx

# Rebuild after code changes
./scripts/deployment/build_web.sh
docker compose restart web

# Stop all services
docker compose down

# View service status
docker compose ps
```

---

## Troubleshooting

### Web service not starting?

```bash
# Check if build succeeded
ls -la src/clients/web/dist/

# If empty, rebuild
./scripts/deployment/build_web.sh

# Restart
docker compose restart web
```

### 502 Bad Gateway?

```bash
# Check web service
docker compose ps web
docker compose logs web

# Restart
docker compose restart web
```

### SSL certificate errors?

- Self-signed certs show browser warnings (expected)
- Click "Advanced" → "Proceed to site"
- Or use Let's Encrypt for production

### Can't build web app?

```bash
# Clear Gradle cache
cd src/clients
./gradlew clean
rm -rf ~/.gradle/caches/
./gradlew :web:jsBrowserDistribution --no-daemon
```

---

## URLs & Endpoints

**Web Interface:**
- Main site: https://fkstrading.xyz
- Local: https://localhost
- Direct: http://localhost:3002

**API Endpoints:**
- Health: https://fkstrading.xyz/health
- API Gateway: https://fkstrading.xyz/api/
- WebSocket: wss://fkstrading.xyz/ws/

**Monitoring:**
- Grafana: http://localhost:3000
- Prometheus: http://localhost:9090

---

## DNS Setup (if needed)

**Cloudflare:**
1. Add A record: `@` → `YOUR_SERVER_IP`
2. Add CNAME: `www` → `fkstrading.xyz`
3. Enable SSL/TLS (Full mode)
4. Enable "Always Use HTTPS"

**Other DNS:**
```
Type: A
Host: @
Value: YOUR_SERVER_IP
TTL: 3600
```

Wait 1-48 hours for propagation.

---

## Production Checklist

Before going live:

- [ ] Let's Encrypt SSL certificate installed
- [ ] DNS pointing to server
- [ ] `.env` configured with production API keys
- [ ] Firewall configured (ports 80, 443 only)
- [ ] `TRADING_MODE=paper` (start with paper trading)
- [ ] Monitoring setup (Grafana)
- [ ] Backup system in place
- [ ] Load testing completed

---

## Next Steps

1. **Add Settings UI** (see `docs/settings-ui-integration.md`)
2. **Setup monitoring** (Grafana dashboards)
3. **Configure real-time features** (WebSocket signals)
4. **Add trading controls** (strategy execution UI)

---

## Support

**Documentation:**
- Full guide: `docs/web-deployment-guide.md`
- Settings UI: `docs/settings-ui-integration.md`
- Main README: `README.md`

**Quick help:**
```bash
# View all logs
docker compose logs

# Check service health
curl https://fkstrading.xyz/health

# Export logs
docker compose logs > logs.txt
```

---

**Your web interface is ready!** 🎉

Access it at: **https://fkstrading.xyz**