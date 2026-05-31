# =============================================================================
# crypto-demo — a working rustrade bot over crypto pairs (paper mode)
#
# Builds the standalone bot crate at `bots/crypto-demo/`, which consumes the
# published rustrade-framework + indicators-ta + exchange-apiws from crates.io,
# then ships a slim runtime image exposing :9091/metrics with the `fks_bot_*`
# series — spawnable by the FKS spawner exactly like fks-bot-example.
#
# Build (from repo root):
#   docker build -f infrastructure/docker/services/crypto-demo/Dockerfile \
#                -t crypto-demo:latest .
#
# Run (paper, live KuCoin data):
#   docker run --rm -p 9091:9091 crypto-demo:latest
#
# Run offline (synthetic data, no network):
#   docker run --rm -e DEMO_SOURCE=synthetic -p 9091:9091 crypto-demo:latest
# =============================================================================

ARG RUST_VERSION=1.94.1
ARG BUILDER_BASE=debian:bookworm-slim
ARG RUNTIME_BASE=debian:bookworm-slim

# ─── Builder ─────────────────────────────────────────────────────────────────
FROM ${BUILDER_BASE} AS builder

ARG RUST_VERSION
ENV RUSTUP_HOME=/usr/local/rustup \
    CARGO_HOME=/usr/local/cargo \
    PATH=/usr/local/cargo/bin:$PATH

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl ca-certificates pkg-config libssl-dev g++ make \
    && rm -rf /var/lib/apt/lists/*

RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | \
    sh -s -- -y --no-modify-path --profile minimal \
              --default-toolchain ${RUST_VERSION} && \
    chmod -R a+w ${RUSTUP_HOME} ${CARGO_HOME}

WORKDIR /build
# Copy just the standalone bot crate; cargo fetches the published crates from
# crates.io during the build. Build context is the repo root.
COPY bots/crypto-demo/ .

RUN cargo build --release --locked && \
    strip /build/target/release/crypto-demo

# ─── Runtime ─────────────────────────────────────────────────────────────────
FROM ${RUNTIME_BASE}

ARG APP_USER=appuser

RUN apt-get update && \
    apt-get install -y --no-install-recommends ca-certificates curl && \
    ( apt-get install -y --no-install-recommends libssl3 2>/dev/null || \
      apt-get install -y --no-install-recommends libssl3t64 ) && \
    rm -rf /var/lib/apt/lists/*

RUN useradd -u 1000 -m -s /bin/bash ${APP_USER}

WORKDIR /app
COPY --from=builder /build/target/release/crypto-demo /app/crypto-demo

USER ${APP_USER}

ENV RUST_LOG=info,crypto_demo=info \
    BOT_METRICS_PORT=9091 \
    DEMO_SOURCE=kucoin \
    DEMO_SYMBOLS=XBTUSDTM,ETHUSDTM,SOLUSDTM

EXPOSE 9091

# Single-process container; the bot owns its own SIGTERM handling.
HEALTHCHECK --interval=30s --timeout=5s --retries=3 --start-period=10s \
    CMD curl -fs http://localhost:9091/health || exit 1

CMD ["/app/crypto-demo"]
