# syntax=docker/dockerfile:1

# ==============================================================================
# Generic Rust Dockerfile (GPU / NVIDIA CUDA) — Multi-Stage Template
#
# For Rust services that require NVIDIA GPU acceleration at runtime.
#
# Stages:
#   builder  — CUDA-enabled Rust build environment
#   runtime  — lean CUDA runtime image            ← default target
#
# Build args (set via --build-arg or docker-compose build.args):
#   RUST_VERSION     Rust toolchain version               (default: 1.94.1)
#   CUDA_VERSION     nvidia/cuda image tag for builder     (default: 12.4.1-devel-ubuntu22.04)
#   CUDA_RUNTIME     nvidia/cuda image tag for runtime     (default: 12.4.1-runtime-ubuntu22.04)
#   SERVICE_NAME     Binary name to build and run          (default: app)
#   BINARY_NAME      Installed binary filename (if diff.)  (default: SERVICE_NAME)
#   SERVICE_PORT     HTTP port the service exposes         (default: 8080)
#   EXTRUSTCODE_BINARIES   Additional binaries to copy to /app/bin (default: "")
#
# Runtime requirements:
#   - Docker host with NVIDIA Container Toolkit installed
#   - Compatible GPU drivers
#
# docker-compose example:
#   services:
#     gpu-worker:
#       build:
#         context: .
#         dockerfile: infrastructure/docker/base/rust-gpu/Dockerfile
#         args:
#           SERVICE_NAME: my-gpu-service
#           SERVICE_PORT: "8080"
#       deploy:
#         resources:
#           reservations:
#             devices:
#               - driver: nvidia
#                 count: all
#                 capabilities: [gpu]
# ==============================================================================

ARG RUST_VERSION=1.94.1
ARG CUDA_VERSION=12.4.1-devel-ubuntu22.04
ARG CUDA_RUNTIME=12.4.1-runtime-ubuntu22.04

# ==============================================================================
# STAGE 1: BUILDER — Rust toolchain on CUDA devel image
# ==============================================================================
FROM nvidia/cuda:${CUDA_VERSION} AS builder

ARG RUST_VERSION
ARG SERVICE_NAME=app
ARG BINARY_NAME=${SERVICE_NAME}
ARG EXTRUSTCODE_BINARIES=""

ENV RUSTUP_HOME=/usr/local/rustup \
    CARGO_HOME=/usr/local/cargo \
    PATH=/usr/local/cargo/bin:$PATH

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        pkg-config \
        libssl-dev \
        protobuf-compiler \
        build-essential \
        git \
    && curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs \
        | sh -s -- -y --default-toolchain ${RUST_VERSION} \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Copy the full workspace/source tree.
# Tune what gets sent to the daemon with a .dockerignore that excludes
# target/, docs/, .git/, and any large asset directories.
COPY . .

# Build primary binary
RUN cargo build --release --bin ${BINARY_NAME} && \
    strip /build/target/release/${BINARY_NAME}

# Build any extra binaries (no-op when EXTRUSTCODE_BINARIES is empty)
RUN set -e; \
    for bin in ${EXTRUSTCODE_BINARIES:-}; do \
        echo "==> Building extra binary: $bin"; \
        cargo build --release --bin $bin && strip /build/target/release/$bin; \
    done

# ==============================================================================
# STAGE 2: RUNTIME — lean CUDA runtime image
# ==============================================================================
FROM nvidia/cuda:${CUDA_RUNTIME} AS runtime

ARG SERVICE_NAME=app
ARG BINARY_NAME=${SERVICE_NAME}
ARG SERVICE_PORT=8080
ARG EXTRUSTCODE_BINARIES=""

ENV NVIDIA_VISIBLE_DEVICES=all \
    NVIDIA_DRIVER_CAPABILITIES=compute,utility \
    RUST_LOG=info \
    RUST_BACKTRACE=1 \
    SERVICE_NAME=${SERVICE_NAME} \
    SERVICE_PORT=${SERVICE_PORT}

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ca-certificates \
        libssl3 \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Create non-root user
RUN useradd -m -u 1000 -s /bin/bash appuser

# Copy primary service binary
COPY --from=builder --chown=appuser:appuser \
    /build/target/release/${BINARY_NAME} /app/service

# Copy extra binaries to /app/bin (bind-mount; no-op if none were built)
RUN mkdir -p /app/bin /app/config /app/data
RUN --mount=type=bind,from=builder,source=/build/target/release,target=/mnt/bins \
    for bin in ${EXTRUSTCODE_BINARIES:-}; do \
        [ -f "/mnt/bins/$bin" ] && cp "/mnt/bins/$bin" /app/bin/ && echo "Copied: $bin" || true; \
    done

# Optional: copy a config directory from your build context.
# Uncomment and adapt to your project layout:
# COPY --from=builder --chown=appuser:appuser /build/config /app/config

RUN chown -R appuser:appuser /app

USER appuser

EXPOSE ${SERVICE_PORT}

HEALTHCHECK --interval=30s --timeout=5s --retries=3 --start-period=10s \
    CMD curl -f http://localhost:${SERVICE_PORT}/health 2>/dev/null || exit 1

CMD ["/app/service"]
