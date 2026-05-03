# =============================================================================
# STAGE 1: Builder - Prepare entrypoint script
# =============================================================================
FROM alpine:latest AS builder

LABEL stage="builder"

WORKDIR /build

COPY docker/redis/entrypoint.sh /build/entrypoint.sh

# Validate and prepare entrypoint
RUN set -ex && \
    # Ensure LF line endings (not CRLF)
    sed -i 's/\r$//' /build/entrypoint.sh && \
    chmod +x /build/entrypoint.sh && \
    # Sanity check — must start with shebang
    head -1 /build/entrypoint.sh | grep -q '^#!/' && \
    echo "Entrypoint script prepared successfully"

# =============================================================================
# STAGE 2: Production - Final Redis image
# =============================================================================
FROM redis:8.6-alpine AS production

LABEL description="Redis cache & pub/sub with kernel tuning for reliable persistence"
LABEL version="1.0.0"

# Copy our custom entrypoint (runs BEFORE the official docker-entrypoint.sh)
COPY --from=builder /build/entrypoint.sh /usr/local/bin/entrypoint.sh

# Ensure the data directory exists with correct ownership
RUN mkdir -p /data && chown redis:redis /data

# Redis default port
EXPOSE 6379

# Health check — uses redis-cli ping (password injected via env at runtime)
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=5 \
    CMD redis-cli -a "${REDIS_PASSWORD:-}" --no-auth-warning ping | grep -q PONG || exit 1

# Our entrypoint handles kernel tuning, then delegates to the official entrypoint
ENTRYPOINT ["entrypoint.sh"]

# Default command — can be overridden entirely via docker-compose `command:`
CMD ["redis-server"]
