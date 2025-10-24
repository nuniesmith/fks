# Environment Configuration Guide

This guide explains how to properly configure environment variables for the FKS Trading Systems Docker Compose services.

## 📁 Environment Files

The following environment files are available:

| File | Purpose | Use Case |
|------|---------|----------|
| `.env.example` | Template file | Copy this to create your own `.env` file |
| `.env.development` | Local development | Use for local development with hot reload |
| `.env.staging` | Staging environment | Use for testing in staging environment |
| `.env.production` | Production environment | Use for production deployment |
| `.env.gpu` | GPU development | Use for local GPU-enabled development |

## 🚀 Quick Setup

### 1. Choose Your Environment

**For local development (CPU only):**
```bash
cp .env.development .env
```

**For local GPU development:**
```bash
cp .env.gpu .env
```

**For staging deployment:**
```bash
cp .env.staging .env
```

**For production deployment:**
```bash
cp .env.production .env
```

### 2. Configure Secrets

Edit your `.env` file and set the following required secrets:

```bash
# Database passwords
POSTGRES_PASSWORD=your_secure_postgres_password
REDIS_PASSWORD=your_secure_redis_password

# Docker Hub (for image pushing)
DOCKER_USERNAME=your_docker_username
DOCKER_TOKEN=your_docker_token

# External services (optional but recommended)
CLOUDFLARE_API_TOKEN=your_cloudflare_token
DOMAIN_NAME=your_domain.com
ADMIN_EMAIL=your_email@domain.com
```

## 🐳 Service Configuration

### All Services Included

Our Docker Compose setup includes these services:

#### CPU Services (Cloud Deployment)
- **API** (`api`) - REST API service on port 8000
- **Worker** (`worker`) - Background task processing on port 8001
- **Data** (`data`) - Data processing and ingestion on port 9001
- **Web** (`web`) - Web interface on port 3000
- **Nginx** (`nginx`) - Reverse proxy on ports 80/443

#### GPU Services (Home Deployment)
- **Training** (`training`) - ML model training on port 8088
- **Transformer** (`transformer`) - AI/NLP service on port 8089

#### Infrastructure Services
- **Redis** - Caching and message broker on port 6379
- **PostgreSQL** - Primary database on port 5432

### Environment Variables by Service

#### Core Variables (All Services)
```bash
APP_ENV=development|staging|production
APP_LOG_LEVEL=DEBUG|INFO|WARNING|ERROR
TZ=America/New_York
```

#### API Service
```bash
API_PORT=8000
API_CPU_LIMIT=2
API_MEMORY_LIMIT=2048M
```

#### Data Service
```bash
DATA_PORT=9001
DATA_CPU_LIMIT=2
DATA_MEMORY_LIMIT=2048M
```

#### Worker Service
```bash
WORKER_PORT=8001
WORKER_COUNT=2
WORKER_CPU_LIMIT=2
WORKER_MEMORY_LIMIT=2048M
```

#### Web Service
```bash
WEB_PORT=3000
NODE_ENV=development|production
REACT_APP_API_URL=http://localhost:8000
```

#### GPU Services
```bash
TRAINING_PORT=8088
TRANSFORMER_PORT=8089
CUDA_VERSION=12.8.0
GPU_COUNT=1
NVIDIA_VISIBLE_DEVICES=all
```

## 🏗️ Deployment Scenarios

### Scenario 1: Full Local Development
```bash
# Copy development environment
cp .env.development .env

# Start all CPU services
docker-compose up -d

# Check status
docker-compose ps
```

### Scenario 2: GPU Development (Home)
```bash
# Copy GPU environment
cp .env.gpu .env

# Start all services including GPU
docker-compose --profile gpu up -d

# Check GPU services
docker-compose ps
nvidia-smi
```

### Scenario 3: Cloud Deployment (CPU only)
```bash
# Copy production environment
cp .env.production .env

# Edit production secrets
nano .env

# Start CPU services only
docker-compose up -d api worker data web nginx postgres redis
```

### Scenario 4: Split Deployment (Recommended)

**On Cloud Server (CPU services):**
```bash
cp .env.production .env
# Configure for cloud deployment
docker-compose up -d api worker data web nginx postgres redis
```

**On Home GPU Machine:**
```bash
cp .env.gpu .env
# Configure for GPU services
docker-compose --profile gpu up -d training transformer
```

## 🔒 Security Configuration

### Required Secrets

For production deployment, ensure these secrets are set:

```bash
# Database security
POSTGRES_PASSWORD=strong_password_here
REDIS_PASSWORD=strong_password_here

# Application security
JWT_SECRET_KEY=your_jwt_secret_key
SECRET_KEY=your_app_secret_key

# External services
CLOUDFLARE_API_TOKEN=your_cloudflare_token
TAILSCALE_AUTH_KEY=your_tailscale_key

# Trading credentials (if using)
RITHMIC_USERNAME=your_rithmic_username
RITHMIC_PASSWORD=your_rithmic_password

# Monitoring
NETDATA_CLAIM_TOKEN=your_netdata_token
DISCORD_WEBHOOK_SERVERS=your_discord_webhook
```

### SSL Configuration

For production with SSL:
```bash
ENABLE_SSL=true
SSL_STAGING=false  # Set to true for Let's Encrypt staging
DOMAIN_NAME=yourdomain.com
ADMIN_EMAIL=admin@yourdomain.com
```

## 🔄 Environment Switching

You can easily switch between environments:

```bash
# Switch to development
cp .env.development .env
docker-compose down
docker-compose up -d

# Switch to GPU development
cp .env.gpu .env
docker-compose down
docker-compose --profile gpu up -d

# Switch to production
cp .env.production .env
docker-compose down
docker-compose up -d
```

## 🐛 Troubleshooting

### Common Issues

**1. Missing environment variables:**
```bash
# Check what variables are being used
grep -r '\${' docker-compose.yml

# Verify your .env file has all required variables
cat .env | grep -E '^[A-Z_]+='
```

**2. Port conflicts:**
```bash
# Check what's using your ports
netstat -tulpn | grep :8000
lsof -i :8000

# Change ports in .env file if needed
```

**3. GPU services not starting:**
```bash
# Check GPU availability
nvidia-smi

# Verify Docker GPU support
docker run --rm --gpus all nvidia/cuda:11.0-base nvidia-smi

# Check profiles are enabled
docker-compose --profile gpu config
```

**4. Service health check failures:**
```bash
# Check service logs
docker-compose logs api
docker-compose logs data

# Test service endpoints
curl http://localhost:8000/health
curl http://localhost:9001/health
```

## 📚 Additional Resources

- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [GPU Services Guide](GPU_SERVICES_GUIDE.md)
- [GitHub Actions Setup](GITHUB_SECRETS_SETUP_GUIDE.md)
- [Production Deployment Guide](PRODUCTION_DEPLOYMENT.md)
