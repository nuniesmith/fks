# Docker Configuration

This directory contains **base Dockerfiles** for building FKS services organized by language and runtime (CPU/GPU).

## 📁 Directory Structure

```
docker/
├── README.md                    # This file
├── Dockerfile.rust              # Base Rust service (CPU)
├── Dockerfile.rust.gpu          # Base Rust service (GPU-enabled)
├── Dockerfile.python            # Base Python service (CPU)
├── Dockerfile.python.gpu        # Base Python service (GPU-enabled)
├── Dockerfile.authelia          # Authelia authentication service
├── Dockerfile.web               # Web frontend (nginx)
└── .dockerignore                # Common ignore patterns
```

## 🏗️ Architecture Overview

FKS uses a **hybrid Dockerfile strategy**:

1. **Base Dockerfiles** (in `docker/`) - Language-specific templates for generic services
2. **Service-specific Dockerfiles** (in `src/*/`) - Specialized builds for complex services

### Base Dockerfiles (`docker/`)

These provide standardized build environments:

| Dockerfile | Purpose | Used By |
|------------|---------|---------|
| `Dockerfile.rust` | Standard Rust service | Monitor (future services) |
| `Dockerfile.rust.gpu` | GPU-enabled Rust | Future ML/AI Rust services |
| `Dockerfile.python` | Standard Python service | Future Python services |
| `Dockerfile.python.gpu` | GPU-enabled Python | Future ML/AI Python services |
| `Dockerfile.authelia` | Authelia auth server | Authelia service |
| `Dockerfile.web` | Nginx web server | Web UI service |

### Service-specific Dockerfiles (`src/`)

These handle complex builds with workspace dependencies:

| Service | Dockerfile Location | Runtime | Notes |
|---------|---------------------|---------|-------|
| **Janus Forward** | `src/janus/Dockerfile.rust` | Rust | Workspace build |
| **Janus Gateway** | `src/janus/Dockerfile.python` | Python | Workspace build |
| **Audit** | `src/audit/Dockerfile` | Rust | Standalone |
| **Monitor** | `src/monitor/Dockerfile` | Rust | Standalone |

## 🚀 Base Dockerfiles Usage

### Dockerfile.rust (CPU)

**Purpose:** Standard Rust service builder

**Features:**
- Multi-stage build (builder + runtime)
- Debian bookworm-slim runtime
- SSL support (libssl3)
- Optimized binary stripping
- Health checks included

**Build Args:**
- `RUST_VERSION` - Rust version (default: 1.91.1)
- `SERVICE_NAME` - Binary name to build (default: monitor)

**Example:**
```bash
# Build monitor service using base Dockerfile
docker build \
  -f docker/Dockerfile.rust \
  --build-arg SERVICE_NAME=monitor \
  -t fks-monitor \
  ./src/monitor
```

**Runtime Environment:**
- `RUST_LOG` - Logging level (default: info)
- `RUST_BACKTRACE` - Enable backtraces (default: 1)

### Dockerfile.rust.gpu (GPU)

**Purpose:** GPU-accelerated Rust services (future use)

**Features:**
- NVIDIA CUDA base image (12.4.1)
- CUDA development tools in builder
- CUDA runtime in final image
- GPU compute capabilities

**Build Args:**
- `RUST_VERSION` - Rust version (default: 1.91.1)
- `CUDA_VERSION` - CUDA version (default: 12.4.1-devel-ubuntu22.04)
- `SERVICE_NAME` - Binary name to build
- `CARGO_BUILD_FLAGS` - Additional cargo flags

**Example:**
```bash
docker build \
  -f docker/Dockerfile.rust.gpu \
  --build-arg SERVICE_NAME=ml-service \
  -t fks-ml-rust \
  ./src/ml-service
```

**Runtime Environment:**
- `NVIDIA_VISIBLE_DEVICES=all`
- `NVIDIA_DRIVER_CAPABILITIES=compute,utility`

### Dockerfile.python (CPU)

**Purpose:** Standard Python service builder

**Features:**
- Python 3.13 slim base
- Virtual environment (`/app/venv`)
- TA-Lib C library included
- Poetry dependency management
- Non-root user (appuser)

**Build Args:**
- `PYTHON_VERSION` - Python version (default: 3.13)

**Build Context:** Project root (needs `pyproject.toml`)

**Example:**
```bash
docker build \
  -f docker/Dockerfile.python \
  -t fks-python-service \
  .
```

**Runtime Environment:**
- `PYTHONPATH=/app:/app/src:/app/shared`
- `SERVICE_NAME` - Service identifier
- `SERVICE_PORT` - HTTP port (default: 8000)

### Dockerfile.python.gpu (GPU)

**Purpose:** GPU-accelerated Python ML/AI services

**Features:**
- NVIDIA CUDA 12.4.1 runtime base
- Python 3.13 installed on CUDA
- PyTorch with CUDA support
- TA-Lib C library included
- Poetry with ML dependencies (`--with ml`)
- Virtual environment path fixes for CUDA

**Build Args:**
- `PYTHON_VERSION` - Python version (default: 3.13)
- `CUDA_VERSION` - CUDA version (default: 12.4.1-runtime-ubuntu22.04)

**Build Context:** Project root (needs `pyproject.toml`)

**Example:**
```bash
docker build \
  -f docker/Dockerfile.python.gpu \
  -t fks-ml-python \
  .
```

**Runtime Environment:**
- `NVIDIA_VISIBLE_DEVICES=all`
- `NVIDIA_DRIVER_CAPABILITIES=compute,utility`
- `CUDA_VISIBLE_DEVICES=0`

**GPU Verification:**
```python
import torch
print(f'CUDA Available: {torch.cuda.is_available()}')
print(f'CUDA Version: {torch.version.cuda}')
```

## 📦 Service-Specific Dockerfiles

### Janus Services (`src/janus/`)

**Dockerfile.rust** - Forward/Backward services
- Multi-service workspace build
- Shared JANUS crates (common, types, config)
- gRPC proto compilation (protobuf-compiler)
- Service selection via `SERVICE_PACKAGE` arg

**Example:**
```bash
# Build Forward service
docker build \
  -f src/janus/Dockerfile.rust \
  --build-arg SERVICE_PACKAGE=janus-forward \
  -t fks-forward \
  ./src/janus
```

**Dockerfile.python** - Gateway service
- FastAPI orchestration layer
- Project-wide dependencies
- Context is project root (not janus dir)
- Needs access to `pyproject.toml` at root

**Example:**
```bash
# Build Gateway service
docker build \
  -f src/janus/Dockerfile.python \
  -t fks-gateway \
  .
```

### Audit Service (`src/audit/`)

**Dockerfile** - Rust-based code analysis
- Standalone Rust workspace
- Builds both server and CLI binaries
- LLM-powered audit capabilities
- Independent versioning

**Example:**
```bash
docker build -t fks-audit ./src/audit
```

### Monitor Service (`src/monitor/`)

**Dockerfile** - Infrastructure monitoring
- Standalone Rust binary
- Redis, Prometheus integration
- Health monitoring for all services
- Uses simplified build (not base Dockerfile)

**Example:**
```bash
docker build -t fks-monitor ./src/monitor
```

## 🐳 Docker Compose Integration

### Current Configuration

**Main services** (`docker-compose.yml`):
```yaml
services:
  forward:
    build:
      context: ./src/janus
      dockerfile: Dockerfile.rust
      args:
        SERVICE_PACKAGE: janus-forward
    image: fks-forward:latest

  gateway:
    build:
      context: .
      dockerfile: ./src/janus/Dockerfile.python
    image: fks-gateway:latest

  audit:
    build:
      context: ./src/audit
      dockerfile: Dockerfile
    image: fks-audit:latest

  monitor:
    build:
      context: ./src/monitor
      dockerfile: Dockerfile
    image: fks-monitor:latest
```

**Production overrides** (`docker-compose.prod.yml`):
```yaml
services:
  forward:
    image: nuniesmith/fks:janus
    # No build - uses pre-built image from DockerHub

  monitor:
    image: nuniesmith/fks:monitor
    # Pre-built image with build config for reference
```

## 🎯 When to Use Base vs Service-Specific Dockerfiles

### Use Base Dockerfiles (`docker/`) when:
- ✅ Building a new standalone service
- ✅ Service has simple dependencies
- ✅ No workspace/multi-crate builds needed
- ✅ Standard runtime requirements
- ✅ Want consistent build patterns

### Use Service-Specific Dockerfiles (`src/*/`) when:
- ✅ Complex workspace builds (Cargo workspace, Poetry monorepo)
- ✅ Multiple binaries/services in one build
- ✅ Service needs custom build steps
- ✅ Special runtime requirements
- ✅ Service is independently versioned

## 🔧 Development Workflow

### Local Development Build
```bash
# Build specific service
docker compose build forward

# Build all services
docker compose build

# Build with no cache
docker compose build --no-cache gateway
```

### Testing Builds
```bash
# Test base Rust Dockerfile
docker build -f docker/Dockerfile.rust --build-arg SERVICE_NAME=monitor ./src/monitor

# Test base Python Dockerfile
docker build -f docker/Dockerfile.python .

# Test GPU builds (requires NVIDIA runtime)
docker build -f docker/Dockerfile.python.gpu .
```

### Production Builds
```bash
# Build and tag for production
docker build -t nuniesmith/fks:janus-forward-latest -f src/janus/Dockerfile.rust \
  --build-arg SERVICE_PACKAGE=janus-forward ./src/janus

# Push to DockerHub
docker push nuniesmith/fks:janus-forward-latest
```

## 📊 Build Performance Tips

### Layer Caching
- **Dependencies first:** Copy `Cargo.toml`, `pyproject.toml` before source
- **Source last:** Copy `src/` directory last for better cache hits
- **Multi-stage:** Use builder stages to avoid bloating final image

### Build Context Size
- Use `.dockerignore` to exclude unnecessary files
- Keep context small (avoid project root when possible)
- Service-specific contexts are faster

### Parallel Builds
```bash
# Build multiple services in parallel
docker compose build --parallel

# Limit parallelism
docker compose build --parallel 2
```

## 🔍 Troubleshooting

### Build Context Issues

**Problem:** "COPY failed: file not found"

**Solution:**
```bash
# Check build context path in docker-compose.yml
# Ensure Dockerfile path is relative to context
# Review .dockerignore
```

### GPU Runtime Issues

**Problem:** "nvidia-smi not found" or "CUDA not available"

**Solution:**
```bash
# Ensure NVIDIA Docker runtime is installed
docker run --rm --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi

# Add runtime to docker-compose.yml
services:
  ml-service:
    runtime: nvidia
    environment:
      - NVIDIA_VISIBLE_DEVICES=all
```

### Virtual Environment Path Issues (Python GPU)

**Problem:** Python can't find packages in GPU containers

**Solution:** The Dockerfile.python.gpu handles this automatically by:
- Updating `pyvenv.cfg` to point to correct Python
- Fixing symlinks in `/app/venv/bin/`
- Updating shebang lines in executables

### TA-Lib Installation Failures

**Problem:** TA-Lib compilation fails

**Solution:**
```bash
# Increase build timeout
export DOCKER_BUILDKIT=1
export COMPOSE_HTTP_TIMEOUT=600

# Check if TA-Lib source is downloadable
wget http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz
```

## 🧪 Testing GPU Support

### Test PyTorch CUDA
```bash
docker run --rm --gpus all -it fks-ml-python python -c "
import torch
print(f'PyTorch: {torch.__version__}')
print(f'CUDA Available: {torch.cuda.is_available()}')
print(f'CUDA Version: {torch.version.cuda}')
print(f'Device Count: {torch.cuda.device_count()}')
"
```

### Test Rust GPU (future)
```bash
docker run --rm --gpus all -it fks-ml-rust /app/service --test-gpu
```

## 📝 Migration from Old Structure

### Old Structure (Deprecated)
```
docker/
└── Dockerfile              # Monolithic multi-target
    ├── Target: rust
    ├── Target: python-cpu
    ├── Target: python-gpu
    └── Target: python-ml-gpu
```

### New Structure
```
docker/
├── Dockerfile.rust         # Separated by language
├── Dockerfile.rust.gpu     # and runtime (CPU/GPU)
├── Dockerfile.python
└── Dockerfile.python.gpu

src/janus/
├── Dockerfile.rust         # Service-specific for
└── Dockerfile.python       # complex builds

src/audit/
└── Dockerfile              # Standalone services

src/monitor/
└── Dockerfile              # get their own
```

### Benefits
- 🚀 **Faster builds** - Smaller contexts, better caching
- 🔧 **Easier maintenance** - Language changes don't affect other stacks
- 📦 **Clearer organization** - Each service owns its build
- ⚡ **Parallel development** - Teams can work independently
- 🎯 **GPU flexibility** - Easy to enable GPU for any service

## 🔐 Security Best Practices

### Non-root Users
All Dockerfiles create and use non-root users:
- Rust: `appuser` (UID 1000)
- Python: `appuser` (UID 1000)
- Monitor: `monitor` (UID 1000)
- Audit: `audit` (UID 1000)

### Minimal Base Images
- Rust: `debian:bookworm-slim` (~80MB)
- Python: `python:3.13-slim` (~130MB)
- GPU: `nvidia/cuda:*-runtime` (not devel for final stage)

### Dependency Scanning
```bash
# Scan for vulnerabilities
docker scout cves fks-forward:latest
docker scout quickview fks-forward:latest
```

## 📚 Additional Resources

- **Docker Best Practices:** https://docs.docker.com/develop/dev-best-practices/
- **Multi-stage Builds:** https://docs.docker.com/build/building/multi-stage/
- **NVIDIA Container Toolkit:** https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/
- **Poetry in Docker:** https://python-poetry.org/docs/faq/#poetry-in-docker
- **Rust in Docker:** https://www.lpalmieri.com/posts/fast-rust-docker-builds/

## 🔄 Future Enhancements

Planned improvements:
- [ ] BuildKit cache mounts for faster dependency downloads
- [ ] Multi-architecture builds (amd64, arm64)
- [ ] Distroless base images for smaller runtimes
- [ ] Dedicated CI/CD Dockerfiles with test tools
- [ ] Service mesh sidecar injection support

---

**Last Updated:** 2024  
**Maintainer:** FKS Platform Team  
**Version:** 2.0 (Base Dockerfiles)