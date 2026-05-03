# syntax=docker/dockerfile:1

# ==============================================================================
# Generic Python Dockerfile (GPU / NVIDIA CUDA) — Multi-Stage Template
#
# Stages:
#   builder     — CPU-based dep builder (faster builds, no GPU needed)
#   ml-builder  — adds GPU-enabled PyTorch on top of builder
#   runtime     — CUDA runtime image with the installed venv ← default target
#   trainer     — extends runtime for long-running training services
#
# Build args (set via --build-arg or docker-compose build.args):
#   PYTHON_VERSION   Python slim image tag               (default: 3.13)
#   CUDA_VERSION     nvidia/cuda image tag               (default: 12.8.0-runtime-ubuntu24.04)
#   SERVICE_PORT     HTTP port the service exposes       (default: 8000)
#   APP_SRC          Host source directory to copy       (default: src)
#   INSTALL_TALIB    Build & install TA-Lib C library    (default: false)
#   EXTRUSTCODE_APT_PKGS   Space-separated extra apt packages  (default: "")
#
# docker-compose example:
#   services:
#     ml-worker:
#       build:
#         context: .
#         dockerfile: infrastructure/docker/base/python-gpu/Dockerfile
#         args:
#           SERVICE_PORT: "8200"
#           APP_SRC: src/ml
#       deploy:
#         resources:
#           reservations:
#             devices:
#               - driver: nvidia
#                 count: all
#                 capabilities: [gpu]
# ==============================================================================

ARG PYTHON_VERSION=3.13
ARG CUDA_VERSION=12.8.0-runtime-ubuntu24.04

# ==============================================================================
# STAGE 1: BUILDER — CPU-based dep install (faster; no GPU required at build time)
# ==============================================================================
FROM python:${PYTHON_VERSION}-slim AS builder

ARG EXTRUSTCODE_APT_PKGS=""
ARG INSTALL_TALIB=false

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential curl libpq-dev git wget ca-certificates \
    && ( [ -z "${EXTRUSTCODE_APT_PKGS}" ] || \
         apt-get install -y --no-install-recommends ${EXTRUSTCODE_APT_PKGS} ) \
    && rm -rf /var/lib/apt/lists/*

# Optional: TA-Lib C library.
# Set INSTALL_TALIB=true when your app uses the `ta-lib` pip package.
# Single-threaded make avoids the gen_code parallel-build race condition.
RUN if [ "$INSTALL_TALIB" = "true" ]; then \
        set -e; \
        cd /tmp && \
        wget -q http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz && \
        tar -xzf ta-lib-0.4.0-src.tar.gz && \
        cd ta-lib && \
        ./configure --prefix=/usr && \
        make && make install && \
        rm -rf /tmp/ta-lib*; \
    fi

# Create virtualenv
RUN python -m venv /app/venv

# Copy only the dependency manifests first (cache-friendly layer).
# Supports requirements.txt (plain pip) or pyproject.toml (tomllib extraction).
COPY pyproject.toml* requirements*.txt* ./

RUN set -e; \
    . /app/venv/bin/activate; \
    pip install --upgrade pip setuptools wheel; \
    export PIP_DEFAULT_TIMEOUT=600; \
    if [ -f requirements.txt ]; then \
        echo "==> Installing from requirements.txt..."; \
        pip install --no-cache-dir -r requirements.txt; \
    elif [ -f pyproject.toml ]; then \
        echo "==> Extracting deps from pyproject.toml..."; \
        python -c "import tomllib,pathlib;d=tomllib.load(open('pyproject.toml','rb'));deps=d.get('project',{}).get('dependencies',[]);pathlib.Path('/tmp/req.txt').write_text('\n'.join(deps)+'\n');print(f'Extracted {len(deps)} dependencies')"; \
        pip install --no-cache-dir -r /tmp/req.txt; \
    else \
        echo "WARNING: No dependency file found — no deps installed"; \
    fi

# ==============================================================================
# STAGE 2: ML-BUILDER — add GPU-enabled PyTorch on top of the base venv
# ==============================================================================
FROM builder AS ml-builder

# Extract optional-dependency groups for GPU + server extras from pyproject.toml,
# or install from a separate requirements-gpu.txt if it exists.
# Customize the group names below to match your pyproject.toml extras.
RUN set -e; \
    . /app/venv/bin/activate; \
    export PIP_DEFAULT_TIMEOUT=600; \
    if [ -f requirements-gpu.txt ]; then \
        echo "==> Installing GPU extras from requirements-gpu.txt..."; \
        pip install --no-cache-dir -r requirements-gpu.txt; \
    elif [ -f pyproject.toml ]; then \
        echo "==> Extracting GPU extras from pyproject.toml..."; \
        python -c "import tomllib,pathlib;d=tomllib.load(open('pyproject.toml','rb'));extras=d.get('project',{}).get('optional-dependencies',{});groups=['gpu','server','training'];deps=[dep for g in groups for dep in extras.get(g,[])];pathlib.Path('/tmp/req-gpu.txt').write_text('\n'.join(deps)+'\n');print(f'Extracted {len(deps)} GPU/server/training extras')"; \
        pip install --no-cache-dir -r /tmp/req-gpu.txt; \
    fi && \
    pip cache purge || true && \
    python -c "import torch; print(f'PyTorch {torch.__version__} (CUDA: {torch.cuda.is_available()})')" || \
        echo "torch not installed or not importable — check your deps"

# ==============================================================================
# STAGE 3: RUNTIME — CUDA-enabled production image
# ==============================================================================
FROM nvidia/cuda:${CUDA_VERSION} AS runtime

ARG PYTHON_VERSION=3.13
ARG SERVICE_PORT=8000
ARG APP_SRC=src
# Source acquisition: clone from git (CI/prod) or bind-mount copy (dev)
ARG REPO_URL=""
ARG REPO_REF=main

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app:/app/src \
    PATH="/app/venv/bin:$PATH" \
    NVIDIA_VISIBLE_DEVICES=all \
    NVIDIA_DRIVER_CAPABILITIES=compute,utility \
    CUDA_VISIBLE_DEVICES=0 \
    SERVICE_NAME=app \
    SERVICE_PORT=${SERVICE_PORT}

WORKDIR /app

# Install Python on the CUDA base image
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        software-properties-common build-essential curl libpq5 ca-certificates git \
    && add-apt-repository ppa:deadsnakes/ppa -y && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
        python${PYTHON_VERSION} \
        python${PYTHON_VERSION}-dev \
        python${PYTHON_VERSION}-venv \
    && rm -rf /var/lib/apt/lists/*

# Bootstrap pip for the installed Python version
RUN curl -sS https://bootstrap.pypa.io/get-pip.py | python${PYTHON_VERSION}

# Create canonical python / python3 symlinks
RUN ln -sf /usr/bin/python${PYTHON_VERSION} /usr/bin/python && \
    ln -sf /usr/bin/python${PYTHON_VERSION} /usr/bin/python3

# Create non-root user.
# NVIDIA CUDA Ubuntu images ship an "ubuntu" user at UID 1000 — rename it.
RUN set -e; \
    if getent passwd 1000 >/dev/null 2>&1; then \
        OLD="$(getent passwd 1000 | cut -d: -f1)"; \
        if [ "$OLD" != "appuser" ]; then \
            usermod  -l appuser -d /home/appuser -m "$OLD"; \
            groupmod -n appuser "$OLD" 2>/dev/null || true; \
        fi; \
    else \
        useradd -u 1000 -m -s /bin/bash appuser; \
    fi

# Copy TA-Lib shared libraries from builder (no-op if INSTALL_TALIB=false)
RUN --mount=type=bind,from=builder,source=/usr/lib,target=/mnt/blib \
    find /mnt/blib -maxdepth 1 -name "libta_lib*" -exec cp {} /usr/lib/ \; && \
    ldconfig 2>/dev/null || true

# Copy virtualenv from ml-builder and re-point interpreter paths to this Python
COPY --from=ml-builder --chown=appuser:appuser /app/venv /app/venv
RUN sed -i "s|^home = .*|home = /usr/bin|" /app/venv/pyvenv.cfg && \
    sed -i "s|^executable = .*|executable = /usr/bin/python${PYTHON_VERSION}|" /app/venv/pyvenv.cfg && \
    rm -f /app/venv/bin/python /app/venv/bin/python3 /app/venv/bin/python${PYTHON_VERSION} && \
    ln -s /usr/bin/python${PYTHON_VERSION} /app/venv/bin/python && \
    ln -s python /app/venv/bin/python3 && \
    ln -s python /app/venv/bin/python${PYTHON_VERSION} && \
    find /app/venv/bin -type f -executable -exec \
        sh -c 'head -1 "$1" 2>/dev/null | grep -q "^#!" && \
               sed -i "1s|^#!.*python.*|#!/app/venv/bin/python|" "$1"' _ {} \;

# Copy application source — two modes:
#   REPO_URL set   → git clone at REPO_REF, copy APP_SRC subdir into ./src
#   REPO_URL empty → bind-mount local context and copy APP_SRC into ./src
RUN --mount=type=bind,source=.,target=/ctx \
    mkdir -p ./src && \
    if [ -n "${REPO_URL}" ]; then \
        git clone --depth=1 --branch "${REPO_REF}" "${REPO_URL}" /tmp/_repo && \
        cp -r /tmp/_repo/${APP_SRC}/. ./src/ && \
        rm -rf /tmp/_repo; \
    else \
        cp -r /ctx/${APP_SRC}/. ./src/; \
    fi && \
    chown -R appuser:appuser ./src

USER appuser

# Verify PyTorch + CUDA linkage (non-fatal — GPU may not be present at build time)
RUN python -c " \
import torch; \
print(f'PyTorch: {torch.__version__}'); \
print(f'CUDA available: {torch.cuda.is_available()}'); \
" || echo "GPU verification skipped (expected if no GPU during build)"

EXPOSE ${SERVICE_PORT}

HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=60s \
    CMD python -c "import sys; sys.exit(0)" || exit 1

# Override with `command:` in docker-compose to run your actual entrypoint.
CMD ["python", "-m", "src.main"]

# ==============================================================================
# TARGET: TRAINER — long-running GPU training service
# ==============================================================================
# Extends the CUDA runtime with directories and configuration for persistent
# model training workloads that accept requests and run between restarts.
#
# Customise via docker-compose environment / volumes:
#   environment:
#     TRAINER_HOST: 0.0.0.0
#     TRAINER_PORT: "8200"
#     SERVICE_NAME: my-trainer
#   volumes:
#     - ./models:/app/models
#     - trainer_dataset:/app/dataset
#   command: ["python", "-m", "src.trainer_server"]
# ==============================================================================
FROM runtime AS trainer

USER root

# Persistent directories — all bind-mountable via docker-compose volumes:
#   /app/models   — trained model artefacts (bind-mount for host git-tracking)
#   /app/dataset  — training dataset       (named volume recommended)
#   /app/data     — local data cache       (bind-mount or volume)
RUN mkdir -p /app/models /app/dataset /app/data && \
    chown -R appuser:appuser /app/models /app/dataset /app/data

USER appuser

ENV TRAINER_HOST=0.0.0.0 \
    TRAINER_PORT=8200 \
    SERVICE_NAME=trainer

EXPOSE 8200

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c \
        "import urllib.request; urllib.request.urlopen('http://localhost:${TRAINER_PORT:-8200}/health')" \
    || exit 1

CMD ["python", "-m", "src.trainer_server"]
