# syntax=docker/dockerfile:1

# ==============================================================================
# Generic Rust Dockerfile (CPU) — Multi-Stage Template
#
# Two builder variants × one runtime base:
#
#   standalone  — single-crate service (no workspace)
#     builder: copies Cargo.toml + src/, builds one binary
#
#   workspace   — Cargo workspace service
#     builder: copies the full workspace, builds one or more binaries
#
# Build args (set via --build-arg or docker-compose build.args):
#   RUST_VERSION       Rust toolchain version                  (default: 1.94.1)
#   BUILDER_BASE       Debian-based builder image              (default: debian:bookworm-slim)
#                      Set to debian:trixie-slim for glibc 2.41+ (e.g. ort-sys/ONNX Runtime)
#   RUNTIME_BASE       Debian-based runtime image              (default: debian:bookworm-slim)
#   SERVICE_NAME       Binary name to build and run            (default: app)
#   BINARY_NAME        Installed binary filename (if diff.)    (default: SERVICE_NAME)
#   SERVICE_PORT       HTTP port the service exposes           (default: 8080)
#   APP_USER           Non-root user name in the runtime image (default: appuser)
#   SRUSTCODE_PATH           Source subdirectory in build context    (default: .)
#                      (standalone only) e.g. "src/myservice" for monorepos
#   SQLX_OFFLINE       Set "true" to enable sqlx offline mode  (default: "")
#   MIGRATIONS_SRC     Source dir for sqlx migration SQL files (default: "")
#   MIGRATIONS_DEST    Dest dir for migrations in build tree   (default: "")
#                      When both are set, files are copied before cargo build
#                      so sqlx::migrate!() can embed them at compile time.
#                      Example: MIGRATIONS_SRC=src/sql/rc  MIGRATIONS_DEST=src/rc/migrations
#   EXTRUSTCODE_BUILD_PKGS   Extra apt packages at build time        (default: "")
#   EXTRUSTCODE_RUNTIME_PKGS Extra apt packages in runtime image     (default: "")
#   EXTRUSTCODE_BINARIES     Additional binaries to copy to /app/bin (default: "")
#
# docker-compose examples:
#   # Standard workspace service:
#   gateway:
#     build:
#       context: .
#       dockerfile: infrastructure/docker/base/rust/Dockerfile
#       target: workspace
#       args:
#         SERVICE_NAME: gateway
#         SERVICE_PORT: "8080"
#
#   # Workspace service requiring glibc 2.41+ and embedded sqlx migrations:
#   rc-app:
#     build:
#       context: .
#       dockerfile: infrastructure/docker/base/rust/Dockerfile
#       target: workspace
#       args:
#         BUILDER_BASE: debian:trixie-slim
#         RUNTIME_BASE: debian:trixie-slim
#         SERVICE_NAME: rustcode-server
#         SERVICE_PORT: "3500"
#         APP_USER: rustcode
#         EXTRUSTCODE_RUNTIME_PKGS: "git"
#         SQLX_OFFLINE: "true"
#         MIGRATIONS_SRC: src/sql/rc
#         MIGRATIONS_DEST: src/rc/migrations
# ==============================================================================

ARG RUST_VERSION=1.94.1
ARG BUILDER_BASE=debian:bookworm-slim
ARG RUNTIME_BASE=debian:bookworm-slim

# ==============================================================================
# STAGE 1: BASE — Rust toolchain via rustup on a configurable Debian base
#
# Using rustup (rather than the official rust:* image) lets BUILDER_BASE be any
# Debian variant — including debian:trixie-slim for glibc 2.41+ requirements
# such as ort-sys / pre-built ONNX Runtime binaries (__isoc23_strtoll, etc.).
# ==============================================================================
FROM ${BUILDER_BASE} AS base

ARG RUST_VERSION=1.94.1
ARG EXTRUSTCODE_BUILD_PKGS=""

ENV RUSTUP_HOME=/usr/local/rustup \
    CARGO_HOME=/usr/local/cargo \
    PATH=/usr/local/cargo/bin:$PATH

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl ca-certificates pkg-config libssl-dev protobuf-compiler g++ make git \
    && ( [ -z "${EXTRUSTCODE_BUILD_PKGS}" ] || \
         apt-get install -y --no-install-recommends ${EXTRUSTCODE_BUILD_PKGS} ) \
    && rm -rf /var/lib/apt/lists/*

# Install Rust toolchain (profile=minimal keeps the download lean)
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | \
    sh -s -- -y --no-modify-path --profile minimal \
              --default-toolchain ${RUST_VERSION} && \
    chmod -R a+w ${RUSTUP_HOME} ${CARGO_HOME}

WORKDIR /build

# ==============================================================================
# STAGE 2a: BUILDER-STANDALONE — single Cargo crate (no workspace)
# ==============================================================================
# Use this when your service lives in its own directory with its own Cargo.toml
# and Cargo.lock, without a parent workspace.
#
# SRUSTCODE_PATH lets you point at a subdirectory of the build context:
#   args: { SRUSTCODE_PATH: src/myservice }
# This copies src/myservice/Cargo.toml and src/myservice/src/ while preserving
# the two-step cache: deps are only rebuilt when Cargo.toml / Cargo.lock change.
#
# MIGRATIONS_SRC + MIGRATIONS_DEST (optional):
#   Copies migration SQL files into the build tree so sqlx::migrate!() can
#   embed them at compile time. Uses a BuildKit bind-mount of the build context
#   so the step is a true no-op when the ARGs are empty.
# ==============================================================================
FROM base AS builder-standalone

ARG SERVICE_NAME=app
ARG BINARY_NAME=${SERVICE_NAME}
ARG SRUSTCODE_PATH=.
ARG SQLX_OFFLINE=""
ARG MIGRATIONS_SRC=""
ARG MIGRATIONS_DEST=""

ENV SQLX_OFFLINE=${SQLX_OFFLINE}

# Step 1 — dependency manifests only (cache-friendly layer)
COPY ${SRUSTCODE_PATH}/Cargo.toml ${SRUSTCODE_PATH}/Cargo.lock* ./

# Step 2 — application source
COPY ${SRUSTCODE_PATH}/src ./src

# Step 3 — optional: copy migrations for sqlx::migrate!() compile-time embedding.
# Bind-mounts the full build context at /ctx so we can conditionally copy without
# a hard COPY failure when MIGRATIONS_SRC is empty.
RUN --mount=type=bind,source=.,target=/ctx \
    if [ -n "${MIGRATIONS_SRC}" ] && [ -n "${MIGRATIONS_DEST}" ]; then \
        mkdir -p "${MIGRATIONS_DEST}" && \
        cp -r /ctx/${MIGRATIONS_SRC}/. "${MIGRATIONS_DEST}/"; \
    fi

RUN cargo build --release --bin ${BINARY_NAME} && \
    strip /build/target/release/${BINARY_NAME}

# ==============================================================================
# STAGE 2b: BUILDER-WORKSPACE — Cargo workspace
# ==============================================================================
# Use this when your service is a member of a larger Cargo workspace.
#
# Copies the full workspace (tune with .dockerignore: exclude target/, docs/,
# .git/, large asset dirs).
#
# MIGRATIONS_SRC + MIGRATIONS_DEST: after COPY . . the source files are already
# present, so we use a plain RUN cp to relocate them for sqlx::migrate!().
#   Example: MIGRATIONS_SRC=src/sql/rc  MIGRATIONS_DEST=src/rc/migrations
#
# EXTRUSTCODE_BINARIES: space-separated list of extra binary names to build and strip.
# ==============================================================================
FROM base AS builder-workspace

ARG SERVICE_NAME=app
ARG BINARY_NAME=${SERVICE_NAME}
ARG EXTRUSTCODE_BINARIES=""
ARG SQLX_OFFLINE=""
ARG MIGRATIONS_SRC=""
ARG MIGRATIONS_DEST=""
# Source acquisition: clone from git (CI/prod) or bind-mount copy (dev).
#   REPO_URL="" + REPO_REF=main → use local build context (default)
#   REPO_URL set               → git clone --depth=1 --branch REPO_REF REPO_URL
ARG REPO_URL=""
ARG REPO_REF=main

ENV SQLX_OFFLINE=${SQLX_OFFLINE}

# Acquire workspace source — git clone or local context copy.
# Both modes land the full workspace at /build so cargo build works identically.
RUN --mount=type=bind,source=.,target=/ctx \
    if [ -n "${REPO_URL}" ]; then \
        git clone --depth=1 --branch "${REPO_REF}" "${REPO_URL}" /tmp/_repo && \
        cp -r /tmp/_repo/. . && \
        rm -rf /tmp/_repo; \
    else \
        cp -r /ctx/. .; \
    fi

# Optional: relocate migrations so sqlx::migrate!() finds them at CARGO_MANIFEST_DIR.
# Example: MIGRATIONS_SRC=src/sql/rc  MIGRATIONS_DEST=src/rc/migrations
RUN if [ -n "${MIGRATIONS_SRC}" ] && [ -n "${MIGRATIONS_DEST}" ]; then \
        if [ -L "${MIGRATIONS_DEST}" ]; then rm -f "${MIGRATIONS_DEST}"; fi && \
        mkdir -p "${MIGRATIONS_DEST}" && \
        cp -r "${MIGRATIONS_SRC}/." "${MIGRATIONS_DEST}/"; \
    fi

# Build primary binary
RUN cargo build --release --bin ${BINARY_NAME} && \
    strip /build/target/release/${BINARY_NAME}

# Build any extra binaries (no-op when EXTRUSTCODE_BINARIES is empty)
RUN set -e; \
    for bin in ${EXTRUSTCODE_BINARIES}; do \
        echo "==> Building extra binary: $bin"; \
        cargo build --release --bin $bin && strip /build/target/release/$bin; \
    done

# ==============================================================================
# STAGE 3: RUNTIME-BASE — lean Debian runtime (shared by all targets)
# ==============================================================================
FROM ${RUNTIME_BASE} AS runtime-base

ARG APP_USER=appuser
ARG EXTRUSTCODE_RUNTIME_PKGS=""

# Install runtime OS packages.
# libssl3 is the bookworm package name; trixie renamed it libssl3t64.
# Try bookworm name first and fall back gracefully — works on both.
RUN apt-get update && \
    apt-get install -y --no-install-recommends ca-certificates curl && \
    ( apt-get install -y --no-install-recommends libssl3 2>/dev/null || \
      apt-get install -y --no-install-recommends libssl3t64 ) && \
    ( [ -z "${EXTRUSTCODE_RUNTIME_PKGS}" ] || \
      apt-get install -y --no-install-recommends ${EXTRUSTCODE_RUNTIME_PKGS} ) && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Create non-root user
RUN useradd -u 1000 -m -s /bin/bash ${APP_USER}

ENV RUST_LOG=info \
    RUST_BACKTRACE=1

# ==============================================================================
# TARGET: STANDALONE — single-crate service
# ==============================================================================
FROM runtime-base AS standalone

ARG SERVICE_NAME=app
ARG BINARY_NAME=${SERVICE_NAME}
ARG SERVICE_PORT=8080
ARG APP_USER=appuser

ENV SERVICE_PORT=${SERVICE_PORT}

COPY --from=builder-standalone /build/target/release/${BINARY_NAME} /app/service

RUN chown -R ${APP_USER}:${APP_USER} /app

USER ${APP_USER}

EXPOSE ${SERVICE_PORT}

HEALTHCHECK --interval=30s --timeout=5s --retries=3 --start-period=10s \
    CMD curl -f http://localhost:${SERVICE_PORT}/health 2>/dev/null || exit 1

CMD ["/app/service"]

# ==============================================================================
# TARGET: WORKSPACE — Cargo workspace service
# ==============================================================================
FROM runtime-base AS workspace

ARG SERVICE_NAME=app
ARG BINARY_NAME=${SERVICE_NAME}
ARG SERVICE_PORT=8080
ARG EXTRUSTCODE_BINARIES=""
ARG APP_USER=appuser

ENV SERVICE_PORT=${SERVICE_PORT}

# Primary service binary
COPY --from=builder-workspace /build/target/release/${BINARY_NAME} /app/service

# Extra binaries go to /app/bin — add /app/bin to PATH in docker-compose if needed
RUN mkdir -p /app/bin /app/config /app/data

# Copy extra binaries if any were built (bind-mount trick for optional copy)
RUN --mount=type=bind,from=builder-workspace,source=/build/target/release,target=/mnt/bins \
    for bin in ${EXTRUSTCODE_BINARIES:-}; do \
        [ -f "/mnt/bins/$bin" ] && cp "/mnt/bins/$bin" /app/bin/ && echo "Copied extra binary: $bin" || true; \
    done

# Optional: copy a config directory from your workspace root.
# Uncomment and adapt the path to match your project layout:
# COPY --from=builder-workspace /build/config /app/config

RUN chown -R ${APP_USER}:${APP_USER} /app

USER ${APP_USER}

EXPOSE ${SERVICE_PORT}

HEALTHCHECK --interval=30s --timeout=5s --retries=3 --start-period=10s \
    CMD curl -f http://localhost:${SERVICE_PORT}/health 2>/dev/null || exit 1

CMD ["/app/service"]
