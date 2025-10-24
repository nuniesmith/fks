# Nginx Quick Reference Card

## Instant Commands

```bash
# Start all services
docker compose up -d

# View Nginx logs
docker compose logs -f nginx

# Test configuration
docker compose exec nginx nginx -t

# Reload configuration
docker compose exec nginx nginx -s reload

# Restart Nginx
docker compose restart nginx

# Check all services
docker compose ps

# Check certificate
openssl x509 -in nginx/ssl/fkstrading.xyz.crt -text -noout
```

## URLs (Local Testing)

First, add to `/etc/hosts`:
```
127.0.0.1  fkstrading.xyz
127.0.0.1  www.fkstrading.xyz
```

Then access:
- **Homepage:** https://fkstrading.xyz/
- **Login:** https://fkstrading.xyz/login/
- **Dashboard:** https://fkstrading.xyz/dashboard/
- **Admin:** https://fkstrading.xyz/admin/
- **API:** https://fkstrading.xyz/api/
- **Flower:** https://fkstrading.xyz/flower/

## Production Upgrade

```bash
# On server (100.114.87.27)
sudo bash scripts/upgrade-to-letsencrypt.sh
```

## Troubleshooting

**502 Bad Gateway?**
```bash
docker compose ps web
docker compose logs web
```

**Static files not loading?**
```bash
docker compose exec web python manage.py collectstatic --noinput
```

**Certificate issues?**
```bash
bash scripts/generate-self-signed-cert.sh
docker compose restart nginx
```

## Key Files

- `nginx/nginx.conf` - Main configuration
- `nginx/conf.d/fkstrading.xyz.conf` - Site config
- `nginx/ssl/` - Certificates
- `nginx/README.md` - Full documentation
- `docs/NGINX_SETUP_COMPLETE.md` - Setup guide

## Status: All Systems Operational ✅
