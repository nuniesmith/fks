.PHONY: help build up down restart logs test lint format clean gpu-up install-dev migrate shell db-shell security-setup security-check

# Default target
help:
	@echo "FKS Trading Platform - Available Commands:"
	@echo ""
	@echo "  make build          - Build Docker containers"
	@echo "  make up             - Start all services"
	@echo "  make gpu-up         - Start services with GPU support"
	@echo "  make down           - Stop all services"
	@echo "  make restart        - Restart all services"
	@echo "  make logs           - View logs (all services)"
	@echo "  make test           - Run test suite"
	@echo "  make lint           - Run linters (ruff, mypy, black)"
	@echo "  make format         - Format code (black, isort)"
	@echo "  make install-dev    - Install development dependencies"
	@echo "  make migrate        - Run database migrations"
	@echo "  make shell          - Open Django shell"
	@echo "  make db-shell       - Open PostgreSQL shell"
	@echo "  make clean          - Clean up containers, volumes, and caches"
	@echo "  make setup-rag      - Setup RAG system (pgvector, models)"
	@echo "  make test-rag       - Test RAG functionality"
	@echo "  make health         - Open health dashboard"
	@echo "  make monitoring     - Open all monitoring UIs"
	@echo "  make security-setup - Generate secure passwords and setup .env"
	@echo "  make security-check - Verify security configuration"
	@echo ""

# Docker operations
build:
	@echo "Building Docker containers..."
	docker-compose build

up:
	@echo "Starting services..."
	docker-compose up -d
	@echo "Services started. Access:"
	@echo "  - Web App: http://localhost:8000"
	@echo "  - Health Dashboard: http://localhost:8000/health/dashboard/"
	@echo "  - Grafana: http://localhost:3000"
	@echo "  - Prometheus: http://localhost:9090"
	@echo "  - PgAdmin: http://localhost:5050"
	@echo "  - Flower: http://localhost:5555"

gpu-up:
	@echo "Starting services with GPU support..."
	docker-compose -f docker-compose.yml -f docker-compose.gpu.yml up -d
	@echo "Services started with GPU. Access:"
	@echo "  - Web App: http://localhost:8000"
	@echo "  - RAG API: http://localhost:8001"
	@echo "  - Ollama: http://localhost:11434"

down:
	@echo "Stopping services..."
	docker-compose down

restart:
	@echo "Restarting services..."
	docker-compose restart

logs:
	docker-compose logs -f

logs-web:
	docker-compose logs -f web

logs-celery:
	docker-compose logs -f celery_worker

logs-rag:
	docker-compose -f docker-compose.yml -f docker-compose.gpu.yml logs -f rag_service

# Development
install-dev:
	@echo "Installing development dependencies..."
	pip install -r requirements.dev.txt
	pip install pytest pytest-cov pytest-asyncio ruff mypy black isort bandit safety

test:
	@echo "Running tests..."
	pytest src/tests/ -v --cov=src --cov-report=html --cov-report=term

test-unit:
	@echo "Running unit tests..."
	pytest src/tests/test_assets.py -v

test-rag:
	@echo "Running RAG tests..."
	pytest src/tests/test_rag_system.py -v

test-ci:
	@echo "Running CI tests..."
	pytest src/tests/ -v --cov=src --cov-report=xml

lint:
	@echo "Running linters..."
	@echo "=== Ruff ==="
	ruff check src/ --fix
	@echo "=== Black ==="
	black --check src/
	@echo "=== isort ==="
	isort --check-only src/
	@echo "=== mypy ==="
	mypy src/ --ignore-missing-imports

format:
	@echo "Formatting code..."
	black src/
	isort src/
	ruff check src/ --fix

security:
	@echo "Running security checks..."
	bandit -r src/ -f json -o bandit-report.json
	safety check --json

# Database operations
migrate:
	@echo "Running migrations..."
	docker-compose exec web python manage.py migrate

makemigrations:
	@echo "Creating migrations..."
	docker-compose exec web python manage.py makemigrations

shell:
	@echo "Opening Django shell..."
	docker-compose exec web python manage.py shell

db-shell:
	@echo "Opening PostgreSQL shell..."
	docker-compose exec db psql -U postgres -d trading_db

# RAG operations
setup-rag:
	@echo "Setting up RAG system..."
	chmod +x scripts/setup_rag.sh
	./scripts/setup_rag.sh

test-local-llm:
	@echo "Testing local LLM setup..."
	chmod +x scripts/test_local_llm.sh
	./scripts/test_local_llm.sh

ingest-data:
	@echo "Ingesting trading data into RAG..."
	docker-compose exec web python scripts/test_rag.py --ingest

query-rag:
	@echo "Testing RAG query..."
	docker-compose exec web python scripts/test_rag.py --query "What are momentum strategies?"

# Cleanup
clean:
	@echo "Cleaning up..."
	docker-compose down -v
	docker system prune -f
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	rm -rf htmlcov/ .coverage coverage.xml

clean-logs:
	@echo "Cleaning logs..."
	rm -rf logs/*/*.log
	rm -rf src/logs/*.log

# Deployment
deploy-staging:
	@echo "Deploying to staging..."
	git push staging main

deploy-prod:
	@echo "Deploying to production..."
	@read -p "Are you sure you want to deploy to production? [y/N] " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		git push production main; \
	fi

# Monitoring
status:
	@echo "=== Service Status ==="
	docker-compose ps
	@echo ""
	@echo "=== Disk Usage ==="
	docker system df
	@echo ""
	@echo "=== Container Stats ==="
	docker stats --no-stream

health:
	@echo "Opening health dashboard..."
	@command -v xdg-open >/dev/null 2>&1 && xdg-open http://localhost:8000/health/dashboard/ || \
	command -v open >/dev/null 2>&1 && open http://localhost:8000/health/dashboard/ || \
	echo "Please open http://localhost:8000/health/dashboard/ in your browser"

monitoring:
	@echo "Opening monitoring UIs..."
	@echo "Health Dashboard: http://localhost:8000/health/dashboard/"
	@echo "Grafana: http://localhost:3000 (admin/admin)"
	@echo "Prometheus: http://localhost:9090"
	@echo "Flower (Celery): http://localhost:5555"
	@echo "PgAdmin: http://localhost:5050"
	@command -v xdg-open >/dev/null 2>&1 && xdg-open http://localhost:3000 || \
	command -v open >/dev/null 2>&1 && open http://localhost:3000 || \
	echo "Please open the URLs above in your browser"

logs-prometheus:
	docker-compose logs -f prometheus

logs-grafana:
	docker-compose logs -f grafana

logs-tailscale:
	docker-compose logs -f tailscale

backup-db:
	@echo "Backing up database..."
	mkdir -p backups
	docker-compose exec -T db pg_dump -U postgres trading_db > backups/backup_$$(date +%Y%m%d_%H%M%S).sql
	@echo "Backup created in backups/"

restore-db:
	@echo "Restoring database from latest backup..."
	@read -p "This will overwrite the current database. Continue? [y/N] " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		docker-compose exec -T db psql -U postgres -d trading_db < $$(ls -t backups/*.sql | head -1); \
	fi

# Development helpers
requirements:
	@echo "Updating requirements..."
	pip freeze > requirements.txt

jupyter:
	@echo "Starting Jupyter notebook..."
	docker-compose exec web jupyter notebook --ip=0.0.0.0 --port=8888 --no-browser --allow-root

docs:
	@echo "Building documentation..."
	cd docs && mkdocs build

docs-serve:
	@echo "Serving documentation..."
	cd docs && mkdocs serve

# Security and validation
security-setup:
	@echo "Running security setup..."
	@bash scripts/setup-security.sh

security-check:
	@echo "Running security checks..."
	@bash scripts/security-check.sh

validate-compose:
	@echo "Validating docker-compose configuration..."
	@docker-compose config > /dev/null && echo "✓ docker-compose.yml is valid"
	@docker-compose -f docker-compose.yml -f docker-compose.gpu.yml config > /dev/null && echo "✓ GPU compose override is valid"

env-check:
	@echo "Checking environment configuration..."
	@if [ ! -f .env ]; then echo "✗ .env file not found. Copy from .env.example"; exit 1; fi
	@echo "✓ .env file exists"
	@grep -q "POSTGRES_PASSWORD=postgres" .env && echo "⚠ Using default PostgreSQL password" || echo "✓ Custom PostgreSQL password"
	@grep -q "DJANGO_SECRET_KEY=django-insecure" .env && echo "⚠ Using insecure Django secret key" || echo "✓ Custom Django secret key"
