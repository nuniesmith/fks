# syntax=docker/dockerfile:1

# ==============================================================================
# Generic Python Dockerfile (CPU) — Multi-Stage Template
#
# Stages:
#   base       — OS packages + build tools (NOT the final image)
#   builder    — virtualenv + Python dependencies
#   runtime    — lean production image           ← default target
#   supervisor — multi-process variant (supervisord)
#
# Build args (set via --build-arg or docker-compose build.args):
#   PYTHON_VERSION   Python slim image tag              (default: 3.13)
#   SERVICE_PORT     HTTP port the service exposes      (default: 8000)
#   APP_SRC          Host source directory to copy      (default: src)
#   EXTRUSTCODE_APT_PKGS   Space-separated extra apt packages (default: "")
#   INSTALL_TALIB    Build & install TA-Lib C library   (default: false)
#
# docker-compose example:
#   services:
#     api:
#       build:
#         context: .
#         dockerfile: infrastructure/docker/base/python/Dockerfile
#         args:
#           SERVICE_PORT: "9000"
#           APP_SRC: src/api
#       environment:
#         SERVICE_NAME: api
#         SERVICE_PORT: "9000"
#       command: ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "9000"]
# ==============================================================================

ARG PYTHON_VERSION=3.13

# ==============================================================================
# STAGE 1: BASE — OS-level packages shared by the builder
# Not shipped in the final image — keeps the runtime lean.
# ==============================================================================
FROM python:${PYTHON_VERSION}-slim AS base

ARG EXTRUSTCODE_APT_PKGS=""
ARG INSTALL_TALIB=false

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app:/app/src \
    PATH="/app/venv/bin:$PATH"

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential curl libpq-dev git wget ca-certificates \
    && ( [ -z "${EXTRUSTCODE_APT_PKGS}" ] || \
         apt-get install -y --no-install-recommends ${EXTRUSTCODE_APT_PKGS} ) \
    && rm -rf /var/lib/apt/lists/*

# Optional: TA-Lib C library.
# Required only when your Python code uses the `ta-lib` pip package.
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

# ==============================================================================
# STAGE 2: BUILDER — virtualenv + Python dependencies
# ==============================================================================
FROM base AS builder

RUN python -m venv /app/venv

# Copy only the dependency manifests first so this layer is cached independently
# from source-code changes.  Supports two formats:
#   requirements.txt  → plain pip install
#   pyproject.toml    → extracts [project.dependencies] via tomllib
#                       (avoids a full hatchling/poetry wheel build)
COPY pyproject.toml* requirements*.txt* ./

RUN set -e; \
    . /app/venv/bin/activate; \
    pip install --upgrade pip setuptools wheel; \
    export PIP_DEFAULT_TIMEOUT=300; \
    if [ -f requirements.txt ]; then \
        echo "==> Installing from requirements.txt..."; \
        pip install --no-cache-dir -r requirements.txt; \
    elif [ -f pyproject.toml ]; then \
        echo "==> Extracting deps from pyproject.toml..."; \
        python -c "import tomllib,pathlib;d=tomllib.load(open('pyproject.toml','rb'));deps=d.get('project',{}).get('dependencies',[]);pathlib.Path('/tmp/req.txt').write_text('\n'.join(deps)+'\n');print(f'Extracted {len(deps)} dependencies')" && \
        pip install --no-cache-dir -r /tmp/req.txt; \
    else \
        echo "WARNING: No requirements.txt or pyproject.toml found — no deps installed"; \
    fi

# ==============================================================================
# STAGE 3: RUNTIME — lean production image
# ==============================================================================
FROM python:${PYTHON_VERSION}-slim AS runtime

# Re-declare build args that are consumed in this stage
ARG SERVICE_PORT=8000
ARG APP_SRC=src

# Source acquisition: clone from git at build time (CI/prod) or copy from
# local build context (dev).  Set REPO_URL to enable git mode.
#   dev:  docker compose build ruby          (REPO_URL not set → bind-mount copy)
#   prod: docker compose build ruby \
#           --build-arg REPO_URL=https://github.com/nuniesmith/ruby \
#           --build-arg REPO_REF=v1.2.3
ARG REPO_URL=""
ARG REPO_REF=main

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app:/app/src \
    PATH="/app/venv/bin:$PATH" \
    SERVICE_NAME=app \
    SERVICE_PORT=${SERVICE_PORT}

WORKDIR /app

# Minimal runtime OS packages.
# Add more at deploy time via docker-compose environment overrides.
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libpq5 \
        curl \
        git \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user.
# Handles distros (e.g. Ubuntu-based images) that pre-ship a user at UID 1000.
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

# Copy virtualenv from builder
COPY --from=builder --chown=appuser:appuser /app/venv /app/venv

# Copy TA-Lib shared libraries from the builder stage.
# This is a no-op when INSTALL_TALIB=false (find returns nothing, cp is skipped).
# Requires BuildKit (DOCKER_BUILDKIT=1), which is the default in Docker 23+.
RUN --mount=type=bind,from=builder,source=/usr/lib,target=/mnt/blib \
    find /mnt/blib -maxdepth 1 -name "libta_lib*" -exec cp {} /usr/lib/ \; && \
    ldconfig 2>/dev/null || true

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

EXPOSE ${SERVICE_PORT}

HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=30s \
    CMD curl -f http://localhost:${SERVICE_PORT}/health || exit 1

# Override with `command:` in docker-compose to run your actual entrypoint.
CMD ["python", "-m", "src.main"]

# ==============================================================================
# TARGET: SUPERVISOR — multi-process service (supervisord)
# ==============================================================================
# Use this target when a single container must run multiple processes
# (e.g. an API server + a background worker side-by-side).
#
# You must supply a supervisord.conf.  Recommended: bind-mount it at runtime
# so you can iterate without rebuilding:
#
#   docker-compose:
#     build:
#       target: supervisor
#     volumes:
#       - ./config/supervisord.conf:/etc/supervisor/conf.d/app.conf:ro
#     command: ["supervisord", "-n", "-c", "/etc/supervisor/conf.d/app.conf"]
#
# Or bake it into the image:
#   COPY config/supervisord.conf /etc/supervisor/conf.d/app.conf
# ==============================================================================
FROM runtime AS supervisor

USER root

RUN apt-get update && \
    apt-get install -y --no-install-recommends supervisor bash && \
    rm -rf /var/lib/apt/lists/*

RUN mkdir -p /var/log/supervisor /var/log/fks /var/run && \
    chown -R appuser:appuser /var/log/supervisor /var/log/fks && \
    chmod 1777 /var/run

# Copy or bind-mount your supervisord config:
# COPY config/supervisord.conf /etc/supervisor/conf.d/app.conf

USER appuser

CMD ["supervisord", "-n", "-c", "/etc/supervisor/conf.d/app.conf"]

# ==============================================================================
# TARGET: SUPERVISOR-FROM-VENV — fast CI/CD build using the pre-cached venv
# ==============================================================================
# Skips the pip install entirely by reusing the nuniesmith/fks:python-venv image
# which was built once when pyproject.toml last changed.
#
# Build order (CI/CD pipeline):
#   1. docker compose --profile base build venv    ← run only when pyproject.toml changes
#   2. docker compose build ruby                   ← always fast: just copies source
#
# To activate in docker-compose.yml:
#   ruby:
#     build:
#       target: supervisor-from-venv
#
# Note: BuildKit only resolves the FROM below when this target is requested,
# so building `target: supervisor` never pulls the venv image.
# ==============================================================================
FROM nuniesmith/fks:python-venv AS venv-prebuilt

FROM python:${PYTHON_VERSION}-slim AS supervisor-from-venv

ARG SERVICE_PORT=8000
ARG APP_SRC=src
ARG REPO_URL=""
ARG REPO_REF=main

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app:/app/src \
    PATH="/app/venv/bin:$PATH" \
    SERVICE_NAME=app \
    SERVICE_PORT=${SERVICE_PORT}

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libpq5 \
        libgomp1 \
        curl \
        git \
        supervisor \
        bash \
    && rm -rf /var/lib/apt/lists/*

# Reuse the non-root user creation logic from the runtime stage
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

# Pull in the pre-built venv — no pip install in this stage at all
COPY --from=venv-prebuilt --chown=appuser:appuser /app/venv /app/venv

RUN mkdir -p /var/log/supervisor /var/log/fks /var/run && \
    chown -R appuser:appuser /var/log/supervisor /var/log/fks && \
    chmod 1777 /var/run

# Source acquisition: same git-clone / bind-mount dual-mode as the standard runtime
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

EXPOSE ${SERVICE_PORT}

HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=30s \
    CMD curl -f http://localhost:${SERVICE_PORT}/health || exit 1

CMD ["supervisord", "-n", "-c", "/etc/supervisor/conf.d/app.conf"]
