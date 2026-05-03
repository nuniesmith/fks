# Docker Quick Reference Guide

**Quick commands for building and running FKS services**

---

## 🚀 Quick Start

### Build Everything
```bash
docker compose build
```

### Run Everything
```bash
docker compose up -d
```

### Stop Everything
```bash
docker compose down
```

---

## 📦 Individual Service Builds

### Janus Services

**Forward (Rust - Real-time execution)**
```bash
# Via compose (recommended)
docker compose build forward

# Direct build
docker build -f src/janus/Dockerfile.rust \
  --build-arg SERVICE_PACKAGE=janus-forward \
  -t fks-forward ./src/janus
```

**Gateway (Python - Orchestration)**
```bash
# Via compose (recommended)
docker compose build gateway

# Direct build
docker build -f src/janus/Dockerfile.python \
  -t fks-gateway .
```

### Infrastructure Services

**Audit (Rust - Code analysis)**
```bash
docker compose build audit
# OR
docker build -t fks-audit ./src/audit
```

**Monitor (Rust - System monitoring)**
```bash
docker compose build monitor  # If defined in compose
# OR
docker build -t fks-monitor ./src/monitor
```

**Web UI (Nginx)**
```bash
docker compose build web
# OR
docker build -t fks-web -f docker/Dockerfile.web .
```

---

## 🎮 Development Workflow

### Rebuild After Code Changes
```bash
# Rebuild specific service
docker compose build forward
docker compose up -d forward

# Rebuild and restart
docker compose up -d --build forward
```

### View Logs
```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f forward
docker compose logs -f gateway

# Last 100 lines
docker compose logs --tail=100 forward
```

### Execute Commands in Container
```bash
# Python shell
docker compose exec gateway python

# Rust binary test
docker compose exec forward ./service --help

# Shell access
docker compose exec forward /bin/bash
```

---

## 🔧 Using Base Dockerfiles

### Build New Rust Service
```bash
# Create your service in src/my-service/
# Then build with base template:
docker build -f docker/Dockerfile.rust \
  --build-arg SERVICE_NAME=my-service \
  -t fks-my-service ./src/my-service
```

### Build New Python Service
```bash
# Ensure pyproject.toml exists in project root
docker build -f docker/Dockerfile.python \
  -t fks-my-python-service .
```

### Build GPU Python Service
```bash
docker build -f docker/Dockerfile.python.gpu \
  -t fks-ml-service .

# Run with GPU
docker run --rm --gpus all fks-ml-service python -c \
  "import torch; print(f'CUDA: {torch.cuda.is_available()}')"
```

### Build GPU Rust Service
```bash
docker build -f docker/Dockerfile.rust.gpu \
  --build-arg SERVICE_NAME=ml-rust \
  -t fks-ml-rust ./src/ml-rust

# Run with GPU
docker run --rm --gpus all fks-ml-rust
```

---

## 🏭 Production Builds

### Build for Production
```bash
# Use production compose file
docker compose -f docker-compose.yml -f docker-compose.prod.yml build

# Build specific service
docker compose -f docker-compose.yml -f docker-compose.prod.yml build forward
```

### Tag for Registry
```bash
# Tag for DockerHub
docker tag janus:latest nuniesmith/fks:janus

# Push to registry
docker push nuniesmith/fks:janus
```

---

## 🔍 Debugging

### Build with No Cache
```bash
docker compose build --no-cache forward
```

### Build with Progress Output
```bash
docker compose build --progress=plain forward
```

### Check Build Context
```bash
# Show what files are sent to Docker daemon
docker build -f src/janus/Dockerfile.rust ./src/janus --no-cache 2>&1 | grep "Sending build context"
```

### Inspect Image
```bash
# Check image size
docker images | grep fks

# Inspect layers
docker history fks-forward:latest

# Dive into image (requires dive tool)
dive fks-forward:latest
```

### Enter Failed Build
```bash
# Build up to specific stage
docker build -f src/janus/Dockerfile.rust \
  --target builder \
  -t fks-forward-debug ./src/janus

# Run and inspect
docker run -it --rm fks-forward-debug /bin/bash
```

---

## 🧪 Testing

### Test Health Checks
```bash
# Check health status
docker compose ps

# Inspect health check
docker inspect fks_forward | grep -A 10 Health
```

### Test Individual Service
```bash
# Run service directly
docker run --rm -p 50051:50051 \
  -e RUST_LOG=debug \
  fks-forward:latest

# Test with curl
curl http://localhost:50051/health
```

### Test GPU Access
```bash
# Python GPU test
docker run --rm --gpus all fks-ml-python python -c "
import torch
assert torch.cuda.is_available(), 'CUDA not available!'
print(f'✓ CUDA working: {torch.cuda.get_device_name(0)}')
"

# Check NVIDIA runtime
docker run --rm --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi
```

---

## 📊 Performance

### Check Resource Usage
```bash
# Real-time stats
docker stats

# Specific service
docker stats fks_forward fks_gateway
```

### Build with BuildKit
```bash
# Enable BuildKit for faster builds
export DOCKER_BUILDKIT=1
docker compose build
```

### Parallel Builds
```bash
# Build multiple services in parallel
docker compose build --parallel

# Limit parallelism
docker compose build --parallel 2
```

---

## 🧹 Cleanup

### Remove Service Images
```bash
# Remove specific image
docker rmi fks-forward:latest

# Remove all FKS images
docker images | grep fks | awk '{print $3}' | xargs docker rmi
```

### Clean Build Cache
```bash
# Remove build cache
docker builder prune

# Remove all unused data
docker system prune -a
```

### Reset Everything
```bash
# Stop and remove all containers, networks, volumes
docker compose down -v

# Remove all images
docker compose down --rmi all

# Full cleanup (DANGEROUS - removes all Docker data)
docker system prune -a --volumes
```

---

## 🎯 Common Tasks

### Update Dependencies

**Rust:**
```bash
# Update Cargo.lock in service directory
cd src/janus && cargo update && cd ../..

# Rebuild
docker compose build --no-cache forward
```

**Python:**
```bash
# Update poetry.lock
poetry update

# Rebuild
docker compose build --no-cache gateway
```

### Change Python/Rust Version

**Edit docker-compose.yml:**
```yaml
services:
  forward:
    build:
      args:
        RUST_VERSION: 1.92.0  # Change version
```

**Or build directly:**
```bash
docker build -f src/janus/Dockerfile.rust \
  --build-arg RUST_VERSION=1.92.0 \
  --build-arg SERVICE_PACKAGE=janus-forward \
  ./src/janus
```

### Add New Service

1. **Create service directory:**
   ```bash
   mkdir -p src/my-service/src
   ```

2. **Choose base Dockerfile:**
   - Rust: Use `docker/Dockerfile.rust`
   - Python: Use `docker/Dockerfile.python`
   - Or create custom in service dir

3. **Add to docker-compose.yml:**
   ```yaml
   my-service:
     build:
       context: ./src/my-service
       dockerfile: ../../docker/Dockerfile.rust
       args:
         SERVICE_NAME: my-service
     image: fks-my-service:latest
     container_name: fks_my_service
     ports:
       - "8080:8080"
     networks:
       - fks-network
   ```

4. **Build and run:**
   ```bash
   docker compose build my-service
   docker compose up -d my-service
   ```

---

## 📋 Cheat Sheet

| Task | Command |
|------|---------|
| Build all | `docker compose build` |
| Build one | `docker compose build forward` |
| No cache | `docker compose build --no-cache` |
| Start all | `docker compose up -d` |
| Stop all | `docker compose down` |
| Logs (follow) | `docker compose logs -f` |
| Logs (service) | `docker compose logs -f forward` |
| Restart | `docker compose restart forward` |
| Rebuild & restart | `docker compose up -d --build forward` |
| Shell access | `docker compose exec forward /bin/bash` |
| List running | `docker compose ps` |
| Resource usage | `docker stats` |
| Remove volumes | `docker compose down -v` |
| Clean images | `docker system prune -a` |

---

## 🆘 Quick Troubleshooting

| Problem | Solution |
|---------|----------|
| Build fails | `docker compose build --no-cache SERVICE` |
| Port conflict | Change port in docker-compose.yml |
| Out of space | `docker system prune -a` |
| GPU not found | Ensure `--gpus all` or `runtime: nvidia` |
| Slow builds | Enable BuildKit: `export DOCKER_BUILDKIT=1` |
| File not found | Check build context in docker-compose.yml |
| Permission denied | Check user in Dockerfile (non-root) |
| Health check fails | `docker compose logs SERVICE` |

---

## 🔗 Related Documentation

- **Full Docker Guide:** `docker/README.md`
- **Migration Notes:** `docker/MIGRATION.md`
- **Janus Services:** `src/janus/README.md`
- **Audit Service:** `src/audit/README.md`

---

**Last Updated:** 2024  
**For:** FKS Platform v2.0