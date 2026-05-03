# FKS Dockerfiles Guide

This document explains the unified Dockerfile structure for FKS services and how to use them.

## 📁 Structure Overview

```
docker/
├── authelia/Dockerfile       # Authelia authentication service
├── python/Dockerfile         # Python services (CPU)
├── python-gpu/Dockerfile     # Python services with GPU support
├── rust/Dockerfile           # Unified Rust services (CPU)
├── rust-gpu/Dockerfile       # Rust services with GPU support (Janus workspace)
├── web/Dockerfile            # Web UI (nginx + KMP)
└── DOCKERFILE_GUIDE.md       # This file
```

## 🦀 Rust Dockerfile (Unified)

The base `docker/rust/Dockerfile` now supports **three types of services**:

### Supported Services

1. **Audit** - Code analysis and LLM-powered auditing
2. **Monitor** - Infrastructure monitoring service  
3. **Janus** - Trading system workspace services (via `SERVICE_TYPE=workspace`)

### Build Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `RUST_VERSION` | `1.92.0` | Rust toolchain version |
| `SERVICE_NAME` | varies by target | Binary name to build |
| **--target** | *required* | `standalone`, `audit`, or `workspace` |

### Usage Examples

#### Building the Monitor Service

```bash
docker build \
  -f docker/rust/Dockerfile \
  --target standalone \
  --build-arg SERVICE_NAME=monitor \
  -t fks/monitor:latest \
  .
```

#### Building the Audit Service

```bash
docker build \
  -f docker/rust/Dockerfile \
  --target audit \
  -t fks/audit:latest \
  .
```

The audit service includes both `audit-server` and `audit-cli` binaries.

#### Building a Janus Workspace Service

```bash
docker build \
  -f docker/rust/Dockerfile \
  --target workspace \
  --build-arg SERVICE_NAME=gateway \
  -t fks/gateway:latest \
  .
```

### In docker-compose.yml

```yaml
services:
  monitor:
    build:
      context: .
      dockerfile: docker/rust/Dockerfile
      target: standalone
      args:
        SERVICE_NAME: monitor
    environment:
      SERVICE_PORT: 8009
      
  audit:
    build:
      context: .
      dockerfile: docker/rust/Dockerfile
      target: audit
    environment:
      AUDIT_PORT: 8080
      
  gateway:
    build:
      context: .
      dockerfile: docker/rust/Dockerfile
      target: workspace
      args:
        SERVICE_NAME: gateway
    environment:
      SERVICE_PORT: 8001
```

## 🐍 Python Dockerfiles

### Python (CPU) - `docker/python/Dockerfile`

**Version:** Python 3.13 (matches `pyproject.toml`)

**Features:**
- Poetry dependency management
- TA-Lib for technical analysis
- Multi-stage build for smaller images
- Non-root user (appuser)
- Virtual environment isolation

**Usage:**

```bash
docker build \
  -f docker/python/Dockerfile \
  -t fks/python-service:latest \
  .
```

**In docker-compose.yml:**

```yaml
services:
  signal-service:
    build:
      context: .
      dockerfile: docker/python/Dockerfile
    environment:
      SERVICE_NAME: signal_service
      SERVICE_PORT: 8002
    command: ["python", "-m", "src.services.signal_service"]
```

### Python GPU - `docker/python-gpu/Dockerfile`

**Version:** Python 3.13 + CUDA 12.4.1

**Features:**
- All features from CPU version
- NVIDIA CUDA runtime
- PyTorch with GPU support
- ML/AI dependencies (installed with `--with ml`)

**Usage:**

```bash
docker build \
  -f docker/python-gpu/Dockerfile \
  -t fks/ml-service:latest \
  .
```

**Runtime requirements:**
- NVIDIA Docker runtime
- Compatible GPU drivers

**In docker-compose.yml:**

```yaml
services:
  ml-engine:
    build:
      context: .
      dockerfile: docker/python-gpu/Dockerfile
    runtime: nvidia
    environment:
      NVIDIA_VISIBLE_DEVICES: all
      CUDA_VISIBLE_DEVICES: 0
```

## 🎮 Rust GPU Dockerfile

**Path:** `docker/rust-gpu/Dockerfile`

**Purpose:** Janus workspace services requiring GPU acceleration (neuromorphic computing, GPU-accelerated trading algorithms)

**Version:** Rust 1.92.0 + CUDA 12.4.1

### Build Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `RUST_VERSION` | `1.92.0` | Rust toolchain version |
| `CUDA_VERSION` | `12.4.1-devel-ubuntu22.04` | CUDA version for builder |
| `SERVICE_NAME` | `neuromorphic` | Binary to build from Janus workspace |
| `CARGO_BUILD_FLAGS` | `""` | Additional cargo build flags |

### Usage

```bash
docker build \
  -f docker/rust-gpu/Dockerfile \
  --build-arg SERVICE_NAME=neuromorphic \
  -t fks/neuromorphic:latest \
  .
```

### In docker-compose.yml

```yaml
services:
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

## 🌐 Web Dockerfile

**Path:** `docker/web/Dockerfile`

**Purpose:** Serve the Kotlin Multiplatform web UI via nginx

### Prerequisites

Build the web app first:

```bash
./scripts/build/build_web.sh
```

This creates `src/clients/web/dist/` with the compiled web assets.

### Usage

```bash
docker build \
  -f docker/web/Dockerfile \
  -t fks/web:latest \
  .
```

### In docker-compose.yml

```yaml
services:
  web:
    build:
      context: .
      dockerfile: docker/web/Dockerfile
    ports:
      - "3001:3001"
```

## 🔐 Authelia Dockerfile

**Path:** `docker/authelia/Dockerfile`

**Purpose:** Custom Authelia authentication service with baked-in config

### Usage

```bash
docker build \
  -f docker/authelia/Dockerfile \
  -t fks/authelia:latest \
  .
```

**Config location:** `config/authelia/configuration.yml`

## 🏗️ Build Context

All Dockerfiles expect to be built from the **project root**:

```bash
# ✅ Correct
docker build -f docker/rust/Dockerfile .

# ❌ Incorrect
cd docker/rust && docker build -f Dockerfile .
```

## 📦 Multi-Stage Build Benefits

All Dockerfiles use multi-stage builds to:

1. **Reduce image size** - Only runtime dependencies in final image
2. **Improve security** - Smaller attack surface
3. **Speed up builds** - Better layer caching
4. **Separate concerns** - Build vs. runtime environments

## 🔧 Common Build Patterns

### Building all services locally

```bash
# Rust services
docker build -f docker/rust/Dockerfile --target standalone --build-arg SERVICE_NAME=monitor -t fks/monitor .
docker build -f docker/rust/Dockerfile --target audit -t fks/audit .

# Python services
docker build -f docker/python/Dockerfile -t fks/python-base .

# Web
docker build -f docker/web/Dockerfile -t fks/web .
```

### Using docker-compose

```bash
# Build all services
docker-compose build

# Build specific service
docker-compose build monitor

# Build with no cache
docker-compose build --no-cache
```

## 🐛 Troubleshooting

### Python dependency build failures

**Problem:** `asyncpg` or `pyarrow` fails to build

**Solution:** Ensure Python version matches `pyproject.toml` (3.13)

```dockerfile
ARG PYTHON_VERSION=3.13  # Must match pyproject.toml
```

### Rust workspace not found

**Problem:** `could not find Cargo.toml`

**Solution:** Ensure you're building from project root with correct target:

```bash
docker build -f docker/rust/Dockerfile --target workspace --build-arg SERVICE_NAME=gateway .
```

### Missing static files (audit service)

**Problem:** Audit service missing static assets

**Solution:** Ensure `src/audit/static/` exists before building

### GPU runtime not available

**Problem:** `nvidia-smi` not found in container

**Solution:** 
1. Install NVIDIA Container Toolkit
2. Use `runtime: nvidia` in docker-compose
3. Verify with: `docker run --rm --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi`

## 📚 Path Reference

### Source Code Paths

- **Janus workspace:** `src/janus/` (Cargo workspace)
- **Audit service:** `src/audit/` (standalone Rust project)
- **Monitor service:** `src/monitor/` (standalone Rust project)
- **Python services:** `src/services/` (Python modules)
- **Web client:** `src/clients/web/`

### Configuration Paths

- **Authelia:** `config/authelia/configuration.yml`
- **Nginx:** `config/nginx/web.conf`
- **Janus configs:** `src/janus/config/`
- **Audit configs:** `src/audit/config/`

### Dependency Files

- **Python:** `pyproject.toml`, `poetry.lock` (project root)
- **Janus:** `src/janus/Cargo.toml`, `src/janus/Cargo.lock`
- **Audit:** `src/audit/Cargo.toml`, `src/audit/Cargo.lock`
- **Monitor:** `src/monitor/Cargo.toml`, `src/monitor/Cargo.lock`

## 🚀 CI/CD Integration

Example GitHub Actions workflow:

```yaml
- name: Build Rust services
  run: |
    docker build -f docker/rust/Dockerfile \
      --target standalone \
      --build-arg SERVICE_NAME=monitor \
      -t ${{ secrets.DOCKER_USERNAME }}/fks-monitor:${{ github.sha }} \
      .
      
    docker build -f docker/rust/Dockerfile \
      --target audit \
      -t ${{ secrets.DOCKER_USERNAME }}/fks-audit:${{ github.sha }} \
      .
```

## 📝 Best Practices

1. **Always specify versions** - Pin Rust, Python, and CUDA versions
2. **Use --target** - Specify build target for multi-stage Dockerfiles
3. **Layer caching** - Copy dependency files before source code
4. **Non-root users** - All services run as non-root in runtime stage
5. **Health checks** - Include appropriate health checks per service
6. **Security** - Minimal base images, no secrets in images
7. **Build context** - Always build from project root for consistent paths

## 🔄 Migration from Old Structure

### Before (deprecated)

- `docker/rust/Dockerfile.audit` ❌
- `docker/rust/Dockerfile.monitor` ❌
- Multiple separate Dockerfiles

### After (current)

- `docker/rust/Dockerfile` ✅ (unified, supports all Rust services)
- Build argument differentiation
- Shared base layers for efficiency

### Migration checklist

- [x] Delete `Dockerfile.audit`
- [x] Delete `Dockerfile.monitor`
- [x] Update `docker-compose.yml` to use unified Dockerfile
- [x] Update CI/CD build scripts
- [x] Test builds for all services
- [x] Update documentation

---

**Last updated:** 2024-12-30  
**Maintained by:** nuniesmith
