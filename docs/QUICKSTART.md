# FKS Trading Platform - Quick Start Guide

## 🚀 Quick Start

### First Time Setup

1. **Test your setup:**
   ```bash
   ./test_setup.sh
   ```

2. **Start all services:**
   ```bash
   ./start.sh rebuild
   ```

3. **Create admin user:**
   ```bash
   ./start.sh createsuperuser
   ```

## 🎯 Common Commands

| Command | Description |
|---------|-------------|
| `./start.sh start` | Start all containers |
| `./start.sh rebuild` | Rebuild and start (use after code changes) |
| `./start.sh stop` | Stop all containers |
| `./start.sh restart` | Restart containers |
| `./start.sh logs` | View logs |
| `./start.sh status` | Show container status |
| `./start.sh shell` | Open Django shell |
| `./start.sh migrate` | Run database migrations |
| `./start.sh celery-status` | Check Celery workers |
| `./start.sh help` | Show all commands |

## 🌐 Service URLs

| Service | URL | Purpose |
|---------|-----|---------|
| **Django App** | http://localhost:8000 | Main application |
| **Admin Panel** | http://localhost:8000/admin | Django admin |
| **Flower** | http://localhost:5555 | Celery task monitoring |
| **pgAdmin** | http://localhost:5050 | Database management |

### pgAdmin Login (if needed)
- **Email:** admin@admin.com (or from .env)
- **Password:** admin (or from .env)

## 📦 Services Overview

### Core Services
- **web** - Django application (port 8000)
- **db** - TimescaleDB/PostgreSQL (port 5432)
- **redis** - Redis cache & Celery broker (port 6379)

### Celery Services
- **celery_worker** - Background task processor
- **celery_beat** - Scheduled task scheduler
- **flower** - Celery monitoring UI (port 5555)

### Management
- **pgadmin** - Database admin UI (port 5050)

## 🔧 Troubleshooting

### Build Fails with Dependency Issues

**Problem:** `resolution-too-deep` or dependency conflicts

**Solution:**
```bash
# The Dockerfile now uses 'uv' instead of 'pip' for faster, better dependency resolution
# Redis version is constrained to work with celery: redis>=5.0.0,<5.1.0
docker compose build --no-cache
```

### Container Won't Start

**Check logs:**
```bash
./start.sh logs
# or for specific service:
docker compose logs web
docker compose logs celery_worker
```

### Database Connection Issues

**Reset database:**
```bash
./start.sh stop
./start.sh clean-volumes  # WARNING: Deletes all data
./start.sh rebuild
```

### Celery Tasks Not Running

**Check Celery status:**
```bash
./start.sh celery-status
# or restart Celery:
docker compose restart celery_worker celery_beat
```

### Port Already in Use

**Check what's using the port:**
```bash
# For port 8000
sudo lsof -i :8000
# or on Windows WSL:
netstat -ano | findstr :8000
```

**Change port in docker-compose.yml:**
```yaml
services:
  web:
    ports:
      - "8001:8000"  # Change 8000 to 8001
```

### Clear Cache and Temp Files

```bash
./start.sh clean
```

### Complete Docker Reset

```bash
./start.sh stop
./start.sh clean-docker
docker compose down -v
docker system prune -a
./start.sh rebuild
```

## 🔄 Development Workflow

### Making Code Changes

1. Edit code in `src/` directory
2. Changes are automatically reflected (mounted volume)
3. For dependency changes:
   ```bash
   ./start.sh rebuild
   ```

### Database Migrations

```bash
# After model changes:
./start.sh migrate

# Or manually:
docker exec -it fks_app python manage.py makemigrations
docker exec -it fks_app python manage.py migrate
```

### Running Tests

```bash
docker exec -it fks_app python manage.py test
# or use pytest:
docker exec -it fks_app pytest
```

### Accessing Django Shell

```bash
./start.sh shell
# Then inside container:
python manage.py shell
```

## 📊 Monitoring

### View All Logs
```bash
./start.sh logs
```

### View Specific Service Logs
```bash
docker compose logs -f web
docker compose logs -f celery_worker
docker compose logs -f celery_beat
```

### Celery Task Monitoring
- Open Flower UI: http://localhost:5555
- View active tasks, failed tasks, task history
- Monitor worker status

### Database Monitoring
- Open pgAdmin: http://localhost:5050
- Add server connection:
  - Host: db
  - Port: 5432
  - Username: postgres (or from .env)
  - Password: postgres (or from .env)

## 🔒 Environment Variables

Create/edit `.env` file for custom configuration:

```bash
# Database
POSTGRES_DB=trading_db
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_secure_password

# Django
DJANGO_SECRET_KEY=your-secret-key
DJANGO_DEBUG=False

# Discord (optional)
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...

# pgAdmin
PGADMIN_EMAIL=admin@admin.com
PGADMIN_PASSWORD=admin
```

## 📝 Key Files

| File | Purpose |
|------|---------|
| `docker-compose.yml` | Service orchestration |
| `docker/Dockerfile` | Container build instructions |
| `requirements.txt` | Python dependencies |
| `start.sh` | Main control script |
| `test_setup.sh` | Setup validation |
| `.env` | Environment configuration |
| `src/django/settings.py` | Django settings |

## 🐛 Debug Mode

### Enable Django Debug Toolbar

In `.env`:
```bash
DJANGO_DEBUG=True
```

Then rebuild:
```bash
./start.sh rebuild
```

### Access Python Debugger

```bash
docker exec -it fks_app python manage.py shell_plus
```

## 🎓 Learn More

- [Django Documentation](https://docs.djangoproject.com/)
- [Celery Documentation](https://docs.celeryq.dev/)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [TimescaleDB Documentation](https://docs.timescale.com/)

## 💡 Tips

1. **Use `./start.sh status` regularly** to check system health
2. **Monitor Flower** (port 5555) to ensure Celery tasks are running
3. **Check logs** when something doesn't work as expected
4. **Run migrations** after pulling new code or changing models
5. **Use `./start.sh clean`** before rebuilding to clear cache issues

## ⚠️ Important Notes

### Dependency Resolution
- The project now uses **uv** instead of pip for faster builds
- Redis version is constrained to `>=5.0.0,<5.1.0` for Celery compatibility
- If you modify `requirements.txt`, test with `./test_setup.sh` first

### Data Persistence
- Database data: Persisted in Docker volume `postgres_data`
- Redis data: Persisted in Docker volume `redis_data`
- Use `./start.sh clean-volumes` to reset (WARNING: deletes all data)

### Resource Usage
- Multiple services run simultaneously (Django, Celery workers, DB, Redis)
- Recommended: 4GB+ RAM, 20GB+ disk space
- Monitor with: `docker stats`

---

**Need Help?** Run `./start.sh help` for command reference
