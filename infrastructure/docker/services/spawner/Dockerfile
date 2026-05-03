# =============================================================================
# FKS Bot Spawner — Docker image
#
# Wraps the workspace base/rust/Dockerfile to build the `spawner` binary.
# The spawner manages bot container lifecycles via the Docker socket.
#
# Build (from repo root):
#   docker compose build fks_bot_spawner
#
# The spawner requires /var/run/docker.sock mounted at runtime (see compose).
# It writes Prometheus SD config to /prometheus-sd/bots.json — mount a shared
# volume between spawner and prometheus containers.
# =============================================================================

# Re-use the shared Rust base image (builder-workspace + runtime-base targets).
# This keeps the build pipeline identical to janus and rustcode — one Dockerfile
# handles everything; only build args differ.
#
# docker-compose.yml sets:
#   dockerfile: infrastructure/docker/base/rust/Dockerfile
#   target: workspace
#   args:
#     SERVICE_NAME: spawner
#     SERVICE_PORT: "8090"
#
# This file exists as a thin reference / standalone alternative for CI pipelines
# that build the spawner image independently of the monorepo compose setup.
# =============================================================================

ARG RUST_VERSION=1.92.0
ARG BUILDER_BASE=debian:bookworm-slim
ARG RUNTIME_BASE=debian:bookworm-slim

FROM ${BUILDER_BASE} AS base

ARG RUST_VERSION=1.92.0
ARG REPO_URL=""
ARG REPO_REF=main

ENV RUSTUP_HOME=/usr/local/rustup \
    CARGO_HOME=/usr/local/cargo \
    PATH=/usr/local/cargo/bin:$PATH

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl ca-certificates pkg-config libssl-dev protobuf-compiler g++ make git \
    && rm -rf /var/lib/apt/lists/*

RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | \
    sh -s -- -y --no-modify-path --profile minimal \
              --default-toolchain ${RUST_VERSION} && \
    chmod -R a+w ${RUSTUP_HOME} ${CARGO_HOME}

WORKDIR /build

# ── Source acquisition: git clone OR bind-mount from local context ────────────
RUN --mount=type=bind,source=.,target=/ctx \
    if [ -n "${REPO_URL}" ]; then \
        git clone --depth=1 --branch "${REPO_REF}" "${REPO_URL}" /tmp/_repo && \
        cp -r /tmp/_repo/. . && \
        rm -rf /tmp/_repo; \
    else \
        cp -r /ctx/. .; \
    fi

ENV SQLX_OFFLINE=true

RUN cargo build --release --bin spawner && \
    strip /build/target/release/spawner

# ── Runtime image ─────────────────────────────────────────────────────────────
FROM ${RUNTIME_BASE}

ARG APP_USER=appuser
ARG SERVICE_PORT=8090

RUN apt-get update && \
    apt-get install -y --no-install-recommends ca-certificates curl && \
    ( apt-get install -y --no-install-recommends libssl3 2>/dev/null || \
      apt-get install -y --no-install-recommends libssl3t64 ) && \
    rm -rf /var/lib/apt/lists/*

RUN useradd -u 1000 -m -s /bin/bash ${APP_USER}

WORKDIR /app

COPY --from=0 /build/target/release/spawner /app/spawner

# Prometheus SD output directory (must be a shared volume with prometheus)
RUN mkdir -p /prometheus-sd && chown ${APP_USER}:${APP_USER} /prometheus-sd /app

USER ${APP_USER}

ENV RUST_LOG=info,spawner=debug \
    SPAWNER_HOST=0.0.0.0 \
    SPAWNER_PORT=${SERVICE_PORT} \
    ALLOWED_IMAGE_PREFIX=fks-bot- \
    MAX_CONCURRENT_BOTS=20 \
    ALLOWED_NETWORK=fks_network \
    PROMETHEUS_SD_PATH=/prometheus-sd/bots.json

EXPOSE ${SERVICE_PORT}

HEALTHCHECK --interval=30s --timeout=5s --retries=3 --start-period=10s \
    CMD curl -f http://localhost:${SPAWNER_PORT:-8090}/health || exit 1

CMD ["/app/spawner"]
