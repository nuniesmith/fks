# =============================================================================
# FKS Rithmic Connector — Docker image
#
# Self-contained multi-stage build for the `rithmic-connector` binary — the
# credential-gated, READ-ONLY Rithmic futures market-data sidecar.
#
# DOCTRINE: read-only. The image contains no order-entry path. At runtime the
# connector no-ops unless RITHMIC_ENABLED=true AND credentials are injected.
#
# This image is NOT part of the default `docker compose up`. It is profile-gated
# behind `rithmic` and only makes sense once a Rithmic dev kit + test-system
# credentials are in hand (spike Phase 0). See docker-compose.yml.
#
# Build (from repo root):
#   docker compose --profile rithmic build rithmic_connector
#
# Mirrors crates/spawner's Dockerfile: builds against the crate's own nested
# [workspace] manifest (it is NOT a member of the fks root workspace).
# =============================================================================

ARG RUST_VERSION=1.94.1
ARG BUILDER_BASE=debian:bookworm-slim
ARG RUNTIME_BASE=debian:bookworm-slim

FROM ${BUILDER_BASE} AS base

ARG RUST_VERSION=1.94.1
ARG REPO_URL=""
ARG REPO_REF=main

ENV RUSTUP_HOME=/usr/local/rustup \
    CARGO_HOME=/usr/local/cargo \
    PATH=/usr/local/cargo/bin:$PATH

# libssl-dev is required: rithmic-rs speaks TLS via native-tls (openssl).
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl ca-certificates pkg-config libssl-dev g++ make git \
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

ENV CARGO_TARGET_DIR=/build/target

# The connector is a self-contained crate with its own nested [workspace]
# (crates/rithmic-connector/Cargo.toml) — NOT a member of the fks root
# workspace. Point cargo at the crate's own manifest, mirroring spawner.
RUN cargo build --release --locked \
        --manifest-path crates/rithmic-connector/Cargo.toml \
        --bin rithmic-connector && \
    strip /build/target/release/rithmic-connector

# ── Runtime image ─────────────────────────────────────────────────────────────
FROM ${RUNTIME_BASE}

ARG APP_USER=appuser
ARG SERVICE_PORT=9091

# libssl3 for the native-tls runtime linkage.
RUN apt-get update && \
    apt-get install -y --no-install-recommends ca-certificates curl && \
    ( apt-get install -y --no-install-recommends libssl3 2>/dev/null || \
      apt-get install -y --no-install-recommends libssl3t64 ) && \
    rm -rf /var/lib/apt/lists/*

RUN useradd -u 1000 -m -s /bin/bash ${APP_USER}

WORKDIR /app

COPY --from=0 /build/target/release/rithmic-connector /app/rithmic-connector

RUN chown ${APP_USER}:${APP_USER} /app
USER ${APP_USER}

# Read-only + gated OFF by default. The spawner secret store injects
# RITHMIC_USER / RITHMIC_PASSWORD / RITHMIC_SYSTEM_NAME at deploy time.
ENV RUST_LOG=info,rithmic_connector=debug \
    RITHMIC_ENABLED=false \
    RITHMIC_ENV=demo \
    RITHMIC_INSTRUMENT=MES \
    RITHMIC_EXCHANGE=CME \
    QUESTDB_ILP_HOST=fks_questdb \
    QUESTDB_ILP_PORT=9009 \
    RITHMIC_HEALTH_HOST=0.0.0.0 \
    RITHMIC_HEALTH_PORT=${SERVICE_PORT}

EXPOSE ${SERVICE_PORT}

HEALTHCHECK --interval=30s --timeout=5s --retries=3 --start-period=10s \
    CMD curl -f http://localhost:${RITHMIC_HEALTH_PORT:-9091}/health || exit 1

CMD ["/app/rithmic-connector"]
