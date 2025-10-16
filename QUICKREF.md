# FKS Trading Platform - Quick Reference

## 🚀 Quick Start

```bash
# Standard startup
make up

# With GPU support (for RAG/LLM)
make gpu-up

# Or using enhanced script
./start-enhanced.sh start --gpu
```

## 📦 Common Commands

### Docker Operations
```bash
make build          # Build containers
make up             # Start services
make gpu-up         # Start with GPU
make down           # Stop services
make restart        # Restart all
make logs           # View all logs
make status         # Show service status
```

### Development
```bash
make test           # Run all tests
make test-unit      # Unit tests only
make test-rag       # RAG tests only
make lint           # Run linters
make format         # Format code
make install-dev    # Install dev dependencies
```

### Database
```bash
make migrate        # Run migrations
make shell          # Django shell
make db-shell       # PostgreSQL shell
make backup-db      # Backup database
```

### RAG Operations
```bash
make setup-rag      # Setup RAG system
make test-local-llm # Test local LLM
make ingest-data    # Ingest trading data
make query-rag      # Test RAG query
```

## 🌐 Access URLs

| Service | URL | Description |
|---------|-----|-------------|
| Web App | http://localhost:8000 | Main trading platform |
| PgAdmin | http://localhost:5050 | Database admin |
| Flower | http://localhost:5555 | Celery monitoring |
| RAG API | http://localhost:8001 | RAG/LLM service (GPU only) |
| Ollama | http://localhost:11434 | Ollama API (GPU only) |

## 🧪 Testing

```bash
# Run all tests with coverage
pytest src/tests/ -v --cov=src

# Run specific test file
pytest src/tests/test_assets.py -v

# Run specific test class
pytest src/tests/test_assets.py::TestTradingAsset -v

# Run specific test
pytest src/tests/test_assets.py::TestTradingAsset::test_create_asset -v

# Skip slow tests
pytest src/tests/ -m "not slow"

# Run with verbose output
pytest src/tests/ -vv
```

## 🐳 Docker Commands

```bash
# View logs
docker-compose logs -f web          # Web service
docker-compose logs -f celery_worker # Celery worker
docker-compose logs -f db           # Database

# Execute commands in container
docker-compose exec web python manage.py shell
docker-compose exec web python manage.py migrate
docker-compose exec db psql -U postgres -d trading_db

# Check service health
docker-compose ps
docker-compose exec web curl http://localhost:8000/health

# Clean up
docker-compose down -v              # Remove volumes
docker system prune -f              # Clean up unused resources
```

## 🎨 Code Quality

```bash
# Format code
black src/
isort src/
ruff check src/ --fix

# Type checking
mypy src/ --ignore-missing-imports

# Security scan
bandit -r src/
safety check
```

## 📊 Monitoring

```bash
# Service status
make status

# Health check
make health

# Container stats
docker stats

# GPU monitoring (if available)
nvidia-smi
watch -n 1 nvidia-smi
```

## 🔧 Troubleshooting

### Database Issues
```bash
# Reset database
docker-compose down -v
docker-compose up -d db
docker-compose exec db psql -U postgres -c "CREATE EXTENSION IF NOT EXISTS vector;"
make migrate
```

### Redis Issues
```bash
# Flush Redis cache
docker-compose exec redis redis-cli FLUSHALL

# Check Redis
docker-compose exec redis redis-cli ping
```

### Celery Issues
```bash
# Restart Celery workers
docker-compose restart celery_worker celery_beat

# Check Celery status
docker-compose exec celery_worker celery -A fks_project inspect active

# Purge tasks
docker-compose exec celery_worker celery -A fks_project purge
```

### GPU/RAG Issues
```bash
# Check GPU
nvidia-smi

# Check CUDA in container
docker run --rm --gpus all nvidia/cuda:12.1.0-base-ubuntu22.04 nvidia-smi

# Test Ollama
curl http://localhost:11434/api/tags

# Pull model
docker-compose exec rag_service ollama pull llama3.2:3b
```

## 📝 Environment Variables

Create `.env` file:
```bash
# Database
POSTGRES_DB=trading_db
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_secure_password

# Django
DJANGO_SECRET_KEY=your_secret_key
DEBUG=False

# Discord (optional)
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...

# RAG (optional)
USE_LOCAL_LLM=true
OLLAMA_HOST=http://localhost:11434
```

## 🔐 Security

```bash
# Change default passwords
POSTGRES_PASSWORD=new_secure_password
PGADMIN_PASSWORD=new_secure_password

# Generate Django secret key
python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'

# Check for vulnerabilities
make security
```

## 📚 Documentation

```bash
# View documentation
cat docs/*.md

# Key documents
docs/RAG_SETUP_GUIDE.md              # RAG setup
docs/LOCAL_LLM_SETUP.md              # Local LLM guide
docs/LOCAL_LLM_IMPLEMENTATION_SUMMARY.md  # Implementation summary
docs/PHASE1_COMPLETE.md              # Phase 1 completion
```

## 🚢 Deployment

```bash
# Deploy to staging
make deploy-staging

# Deploy to production (with confirmation)
make deploy-prod

# Manual deployment
git push production main
ssh user@server "cd /path/to/app && docker-compose pull && docker-compose up -d"
```

## 🆘 Help

```bash
# Show available make commands
make help

# Show start script help
./start-enhanced.sh --help

# Django management commands
docker-compose exec web python manage.py help
```

## 📞 Support

- **Documentation**: `docs/` directory
- **Issues**: GitHub Issues
- **Logs**: `logs/` directory
- **Tests**: `src/tests/` directory

## ⚡ Pro Tips

1. **Use Makefile**: `make <command>` is faster than typing docker-compose commands
2. **Check logs first**: `make logs` often reveals the issue
3. **Health checks**: `make health` verifies all services
4. **Format before commit**: `make format` + `make lint`
5. **Test locally**: `make test` before pushing
6. **Backup regularly**: `make backup-db` before major changes
7. **Monitor GPU**: `watch -n 1 nvidia-smi` when using RAG
8. **Use GPU wisely**: Only start GPU services when needed to save resources

## 🎯 Workflow Example

```bash
# 1. Start development
make up

# 2. Make changes
vim src/rag/intelligence.py

# 3. Format and test
make format
make test-rag

# 4. Check everything
make lint
make test

# 5. Commit and push
git add .
git commit -m "feat: improve RAG response quality"
git push origin main

# 6. Monitor CI
# GitHub Actions will run tests, build Docker, and deploy
```

## 📈 Performance Optimization

```bash
# Check resource usage
docker stats

# Optimize images
docker image prune -a

# Clean build cache
docker builder prune

# Optimize database
docker-compose exec db vacuumdb -U postgres -d trading_db

# Monitor query performance
docker-compose exec db psql -U postgres -d trading_db -c "\timing on"
```

---

**Last Updated**: Phase 1 Complete
**Version**: 1.0.0
**Status**: Production Ready ✅
