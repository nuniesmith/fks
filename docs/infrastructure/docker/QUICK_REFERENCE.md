# Docker Quick Reference Card

**Quick commands for building FKS services**

## 🦀 Rust Services

### Monitor Service
```bash
docker build -f docker/rust/Dockerfile \
  --target standalone \
  --build-arg SERVICE_NAME=monitor \
  -t fks/monitor:latest .
```

### Audit Service (includes CLI + server)
```bash
docker build -f docker/rust/Dockerfile \
  --target audit \
  -t fks/audit:latest .
```

### Janus Workspace Services
```bash
# Gateway
docker build -f docker/rust/Dockerfile \
  --target workspace \
  --build-arg SERVICE_NAME=gateway \
  -t fks/gateway:latest .

# Forward
docker build -f docker/rust/Dockerfile \
  --target workspace \
  --build-arg SERVICE_NAME=forward \
  -t fks/forward:latest .

# Trading Engine
docker build -f docker/rust/Dockerfile \
  --target workspace \
  --build-arg SERVICE_NAME=trading-engine \
  -t fks/trading-engine:latest .
```

### GPU-Enabled (Janus/Neuromorphic)
```bash
docker build -f docker/rust-gpu/Dockerfile \
  --build-arg SERVICE_NAME=neuromorphic \
  -t fks/neuromorphic:latest .
```

## 🐍 Python Services

### CPU
```bash
docker build -f docker/python/Dockerfile \
  -t fks/python-service:latest .
```

### GPU (ML/AI)
```bash
docker build -f docker/python-gpu/Dockerfile \
  -t fks/ml-service:latest .
```

## 🌐 Web UI

```bash
# Build web assets first
./scripts/build/build_web.sh

# Then build Docker image
docker build -f docker/web/Dockerfile \
  -t fks/web:latest .
```

## 🔐 Authelia

```bash
docker build -f docker/authelia/Dockerfile \
  -t fks/authelia:latest .
```

## 📦 docker-compose Examples

### Single Service
```yaml
monitor:
  build:
    context: .
    dockerfile: docker/rust/Dockerfile
    target: standalone
    args:
      SERVICE_NAME: monitor
  environment:
    SERVICE_PORT: 8009
  ports:
    - "8009:8009"
```

### Multiple Rust Services
```yaml
services:
  monitor:
    build:
      context: .
      dockerfile: docker/rust/Dockerfile
      target: standalone
      args:
        SERVICE_NAME: monitor
        
  audit:
    build:
      context: .
      dockerfile: docker/rust/Dockerfile
      target: audit
        
  gateway:
    build:
      context: .
      dockerfile: docker/rust/Dockerfile
      target: workspace
      args:
        SERVICE_NAME: gateway
```

### GPU Service
```yaml
neuromorphic:
  build:
    context: .
    dockerfile: docker/rust-gpu/Dockerfile
    args:
      SERVICE_NAME: neuromorphic
  runtime: nvidia
  environment:
    NVIDIA_VISIBLE_DEVICES: all
    SERVICE_PORT: 8010
```

## 🔧 Common Tasks

### Build all services
```bash
docker-compose build
```

### Build single service
```bash
docker-compose build monitor
```

### Build with no cache
```bash
docker-compose build --no-cache monitor
```

### Run service
```bash
docker-compose up monitor
```

### Check logs
```bash
docker-compose logs -f monitor
```

### Shell into running container
```bash
docker-compose exec monitor /bin/bash
```

## 🐛 Troubleshooting

### Python dependency failures
```bash
# Ensure Python 3.13 is set
grep PYTHON_VERSION docker/python/Dockerfile
# Should show: ARG PYTHON_VERSION=3.13
```

### Rust workspace not found
```bash
# Always build from project root with --target
docker build -f docker/rust/Dockerfile --target standalone --build-arg SERVICE_NAME=monitor .  # ✅
# NOT from docker/ directory
```

### GPU not available
```bash
# Test GPU access
docker run --rm --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi

# Ensure runtime is set
# docker-compose.yml:
runtime: nvidia
```

### Audit CLI missing
```bash
# The audit service includes both binaries
docker run --rm fks/audit:latest ls -la /usr/local/bin/
# Should show: audit-cli
```

## 📝 Build Arguments Reference

### Rust Dockerfile
| Argument | Default | Options |
|----------|---------|---------|
| `RUST_VERSION` | `1.92.0` | Any valid Rust version |
| `SERVICE_NAME` | varies | `monitor` for standalone, any Janus binary for workspace |
| `--target` | *required* | `standalone`, `audit`, or `workspace` |

### Python Dockerfile
| Argument | Default | Notes |
|----------|---------|-------|
| `PYTHON_VERSION` | `3.13` | ⚠️ Must match pyproject.toml |

### Rust-GPU Dockerfile
| Argument | Default | Notes |
|----------|---------|-------|
| `RUST_VERSION` | `1.92.0` | Rust toolchain |
| `CUDA_VERSION` | `12.4.1-devel-ubuntu22.04` | CUDA builder version |
| `SERVICE_NAME` | `neuromorphic` | Janus workspace binary |

## 📚 See Also

- `DOCKERFILE_GUIDE.md` - Comprehensive documentation
- `MIGRATION_SUMMARY.md` - Migration details from old structure
- `.dockerignore` - Files excluded from build context

---

**Last updated:** 2024-12-30
