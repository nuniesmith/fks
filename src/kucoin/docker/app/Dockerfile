# =============================================================================
# kucoin — multi-stage build
#
# Build context: repo root (docker-compose `context: .`)
# External crates (indicators-ta, exchange-apiws) are fetched by cargo.
# =============================================================================

ARG APP_SRC=src

# ── Stage 1: builder ──────────────────────────────────────────────────────────
FROM rust:1.94.1-slim-bookworm AS builder

ARG APP_SRC

RUN apt-get update && apt-get install -y --no-install-recommends \
        pkg-config \
        libssl-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Copy manifests first — this layer is cached until Cargo.toml/lock changes,
# so a src-only edit won't re-download the entire dependency graph.
COPY Cargo.toml Cargo.lock ./

# Build a stub binary to pre-fetch and compile all dependencies.
RUN mkdir -p src && \
    echo 'fn main() {}' > src/main.rs && \
    cargo build --release --bin kucoin; \
    rm -rf src/

# Now copy the real source and do the final build.
# Only this layer re-runs on normal src/ edits.
COPY ${APP_SRC}/ ./src/

# Touch main.rs so cargo knows the real source is newer than the stub build.
RUN touch src/main.rs && \
    cargo build --release --bin kucoin

# ── Stage 2: runtime ──────────────────────────────────────────────────────────
FROM debian:bookworm-slim AS runtime

RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /build/target/release/kucoin /usr/local/bin/kucoin

RUN mkdir -p /app/data /app/logs
WORKDIR /app

# No ENTRYPOINT — the compose `command:` drives startup (supervisord in
# production, or kucoin directly for one-off runs).
CMD ["kucoin", "--sim", "--symbols", "XBTUSDTM,ETHUSDTM,SOLUSDTM"]
