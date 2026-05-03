# ============================================================================
# RustCode — API Server Dockerfile
# ============================================================================
#
# Multi-stage build for the RustCode API-only server.
# Produces a minimal runtime image without build tools or source code.
#
# Target: Oryx server (AMD64 primary, ARM64 optional)
#
# Build:
#   docker build -f docker/rustcode/Dockerfile -t rustcode:latest .
#   docker build -f docker/rustcode/Dockerfile --build-arg SERVICE_PORT=3500 -t rustcode:latest .
#
# Requires:
#   - Cargo.toml, Cargo.lock, src/, src/sql/rc/ in build context (RUSTCODE migrations)
#   - SQLX_OFFLINE=true at build time (no live DB needed — project uses runtime sqlx::query())
# ============================================================================

# ----------------------------------------------------------------------------
# Stage 1: Builder — Compile RustCode
# ----------------------------------------------------------------------------
# Use debian:trixie-slim (glibc 2.41) as the builder base to satisfy ort-sys/ONNX Runtime
# prebuilt binaries which require glibc 2.38+ (__isoc23_strtoll etc.).
# debian:bookworm only ships glibc 2.36 which causes undefined symbol linker errors.
FROM debian:trixie-slim AS builder

# Install Rust toolchain + build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    pkg-config \
    libssl-dev \
    ca-certificates \
    git \
    g++ \
    make \
    && rm -rf /var/lib/apt/lists/*

ENV RUSTUP_HOME=/usr/local/rustup \
    CARGO_HOME=/usr/local/cargo \
    PATH=/usr/local/cargo/bin:$PATH

RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | \
    sh -s -- -y --no-modify-path --profile minimal --default-toolchain 1.92.0 && \
    chmod -R a+w /usr/local/rustup /usr/local/cargo

WORKDIR /build

# ── Dependency caching layer ─────────────────────────────────────────────────
# Copy manifests first so deps are only rebuilt when Cargo.toml/lock change.
COPY Cargo.toml Cargo.lock ./

# Create a minimal dummy source tree that satisfies Cargo's workspace/bin layout.
# This lets `cargo build` download and compile all dependencies without the real
# source, producing a cacheable layer.
RUN mkdir -p src/bin && \
    echo "fn main() {}" > src/bin/server.rs && \
    echo "fn main() {}" > src/bin/cli.rs && \
    echo "fn main() {}" > src/bin/github-sync-daemon.rs && \
    echo "fn main() {}" > src/main.rs && \
    touch src/lib.rs

# Build dependencies only (this layer is cached until Cargo.toml/lock change)
ENV SQLX_OFFLINE=true
RUN cargo build --release --bin rustcode-server 2>&1 || true

# Remove dummy source and any fingerprints so Cargo rebuilds with real source
RUN rm -rf src target/release/rustcode* target/release/.fingerprint/rustcode* \
    target/release/deps/rustcode* target/release/deps/librust*

# ── Real source build ────────────────────────────────────────────────────────
COPY src ./src
COPY src/sql/rustcode ./migrations

ENV SQLX_OFFLINE=true
RUN cargo build --release --bin rustcode-server && \
    strip /build/target/release/rustcode-server

# ----------------------------------------------------------------------------
# Stage 2: Runtime — Minimal production image
# ----------------------------------------------------------------------------
# Runtime must also use trixie (glibc 2.38+) since the binary was linked against
# trixie's glibc 2.41 and ort-sys embeds ONNX symbols requiring __isoc23_strtoll.
FROM debian:trixie-slim

ARG SERVICE_PORT=3500

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    libssl3t64 \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN useradd -m -u 1000 -s /bin/bash rustcode && \
    mkdir -p /app/data /app/config /app/workspace /app/docs && \
    chown -R rustcode:rustcode /app

WORKDIR /app

# Copy binary from builder
COPY --from=builder --chown=rustcode:rustcode \
    /build/target/release/rustcode-server \
    /usr/local/bin/rustcode-server

# Copy config directory if present
COPY --chown=rustcode:rustcode infrastructure/config/rustcode ./config

# Copy migrations for runtime auto-migration
COPY --from=builder --chown=rustcode:rustcode \
    /build/migrations ./migrations

# Switch to non-root user
USER rustcode

# Environment variables with sane defaults.
# All can be overridden by docker-compose environment{} or .env.
# NOTE: The binary (src/bin/server.rs) reads HOST and PORT, not SERVER_HOST/SERVER_PORT.
ENV HOST=0.0.0.0 \
    PORT=${SERVICE_PORT} \
    RUST_LOG=info,rustcode=debug \
    DATABASE_URL=postgres://rustcode:changeme@localhost:5432/rustcode \
    CACHE_ENABLED=true \
    MULTI_TENANT_MODE=false \
    TELEMETRY_ENABLED=false \
    ANALYTICS_ENABLED=true

EXPOSE ${SERVICE_PORT}

# Health check — uses /health (available in all image versions).
# /healthz alias exists in newer builds but /health is the safe default.
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -sf http://127.0.0.1:${PORT:-3500}/health || exit 1

CMD ["rustcode-server"]
