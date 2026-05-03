# =============================================================================
# FKS — QuestDB (time-series database)
# =============================================================================
# Builder : validates and stages config files
# Runtime : official QuestDB image with baked-in config
#
# Ports:
#   9000  — HTTP REST API + web console
#   8812  — PostgreSQL wire protocol
#   9009  — InfluxDB line protocol (ILP / TCP)
# =============================================================================

FROM alpine:3.21 AS builder

WORKDIR /staging

COPY infrastructure/config/questdb/ .

# Validate required config files are present
RUN test -f server.conf || (echo "ERROR: server.conf missing" && exit 1)


FROM questdb/questdb:8.2.1 AS runtime

LABEL maintainer="nuniesmith" \
      description="QuestDB time-series database — bars, ticks, and sensor data"

# QuestDB runs as uid 10001 (questdb) inside the official image
COPY --from=builder /staging/server.conf /var/lib/questdb/conf/server.conf

# Copy any optional config overrides that exist in the source tree
COPY --from=builder /staging/                    /var/lib/questdb/conf/

EXPOSE 9000 8812 9009

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD wget -qO- http://localhost:9000/status || exit 1
