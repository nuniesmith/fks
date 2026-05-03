# =============================================================================
# FKS — Shared Python Venv Image
# =============================================================================
#
# Installs ALL CPU Python dependencies from pyproject.toml ONCE into a venv
# at /app/venv. The ruby service inherits this image to skip the ~5-10 min
# pip install on every source-only rebuild.
#
# Build order (CI/CD):
#   1. docker compose --profile base build venv   ← slow (once per pyproject.toml change)
#   2. docker compose build ruby                  ← fast (source copy only)
#
# Local dev: build `ruby` directly with `target: supervisor` — it builds its
# own venv. Switch to `target: supervisor-from-venv` only when you want the
# CI/CD fast path and the venv image is already in the registry.
#
# Trainer has its own CUDA venv with [gpu] extras — it is NOT derived from
# this image (see docker/base/python-gpu/Dockerfile).
# =============================================================================

ARG PYTHON_VERSION=3.13

# ---------------------------------------------------------------------------
# Stage 1 — dep-builder
# Creates /app/venv with all CPU dependencies installed.
# Cache-busted only when pyproject.toml or requirements.txt changes.
# ---------------------------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim AS dep-builder

# Build-time packages for C-extension wheels:
#   build-essential — gcc/g++ for native wheels
#   libpq-dev       — psycopg builds against the Postgres C headers
#   libssl-dev      — several packages link against OpenSSL at build time
#   pkg-config      — used by various C-extension build scripts
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        libssl-dev \
        pkg-config \
        curl \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN python -m venv /app/venv

# Copy only the dependency manifests — layer cache is not busted by source changes.
COPY pyproject.toml* requirements*.txt* ./

# Install all CPU deps via tomllib extraction (no stub-file hacks, no package install):
#   1. Upgrade pip/setuptools/wheel first to avoid old-resolver edge cases.
#   2. Extract project.dependencies (core deps).
#   3. Extract all optional-dependency groups EXCEPT gpu/cuda/training/torch extras
#      — those belong exclusively to the trainer image.
#   4. Fall back to requirements.txt if no pyproject.toml is present.
RUN set -e; \
    . /app/venv/bin/activate; \
    pip install --upgrade pip setuptools wheel; \
    export PIP_DEFAULT_TIMEOUT=300; \
    if [ -f requirements.txt ]; then \
        echo "==> Installing from requirements.txt..."; \
        pip install --no-cache-dir -r requirements.txt; \
    elif [ -f pyproject.toml ]; then \
        echo "==> Extracting all CPU deps from pyproject.toml..."; \
        python3 -c "\
import tomllib, pathlib, sys; \
d = tomllib.load(open('pyproject.toml', 'rb')); \
core = d.get('project', {}).get('dependencies', []); \
opts = d.get('project', {}).get('optional-dependencies', {}); \
skip = {'gpu', 'cuda', 'training', 'torch', 'nvidia'}; \
extras = [dep for grp, deps in opts.items() \
          if not any(w in grp.lower() for w in skip) \
          for dep in deps]; \
all_deps = core + extras; \
pathlib.Path('/tmp/req.txt').write_text('\n'.join(all_deps) + '\n'); \
print(f'Extracted {len(core)} core + {len(extras)} optional (non-GPU) deps', file=sys.stderr); \
"; \
        pip install --no-cache-dir -r /tmp/req.txt; \
    else \
        echo "WARNING: No pyproject.toml or requirements.txt — nothing installed"; \
    fi

# ---------------------------------------------------------------------------
# Stage 2 — runtime (the published image)
# Lean image: just the venv, no build tools or -dev headers.
# Tagged nuniesmith/fks:python-venv and consumed by supervisor-from-venv builds.
# ---------------------------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim AS runtime

ARG PYTHON_VERSION=3.13

LABEL org.opencontainers.image.title="fks-python-venv" \
      org.opencontainers.image.description="Shared Python venv for FKS CPU services — all deps pre-installed, no source"

# Runtime-only native libs:
#   libpq5   — psycopg binary wheel links against this at runtime
#   libgomp1 — OpenMP, required by numpy / scikit-learn / matplotlib
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libpq5 \
        libgomp1 \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Export the fully-populated venv.
# Downstream images use:  COPY --from=nuniesmith/fks:python-venv /app/venv /app/venv
COPY --from=dep-builder /app/venv /app/venv

ENV PYTHONPATH="/app/src" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/venv/bin:$PATH" \
    LOG_LEVEL=info
