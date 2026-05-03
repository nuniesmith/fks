# =============================================================================
# FKS — Qdrant (vector database)
# =============================================================================
# Builder : validates and stages config files
# Runtime : official Qdrant image with baked-in config
#
# Ports:
#   6333  — HTTP REST API
#   6334  — gRPC API
# =============================================================================

FROM alpine:3.21 AS builder

WORKDIR /staging

COPY infrastructure/config/qdrant/ .

# Validate the primary config is present
RUN test -f config.yaml || (echo "ERROR: config.yaml missing" && exit 1)


FROM qdrant/qdrant:v1.13.4 AS runtime

LABEL maintainer="nuniesmith" \
      description="Qdrant vector database — embedding storage for AI/ML pipelines"

# Qdrant expects its config at /qdrant/config/production.yaml
# (overrides the built-in default.yaml via the QDRANT__CONFIG_PATH env var or config layering)
COPY --from=builder /staging/config.yaml /qdrant/config/production.yaml

# Copy any additional files (e.g. TLS certs, collection snapshots) if present
COPY --from=builder /staging/             /qdrant/config/

EXPOSE 6333 6334

HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD wget -qO- http://localhost:6333/healthz || exit 1
