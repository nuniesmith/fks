# =============================================================================
# FKS — Redis Exporter
# =============================================================================
# Builder : downloads the pre-built release binary
# Runtime : minimal alpine with the binary + config
#
# Exposes :9121/metrics for Prometheus scraping
# =============================================================================

FROM alpine:3.21 AS builder

ARG EXPORTER_VERSION=v1.66.0

RUN apk add --no-cache ca-certificates curl tar

WORKDIR /build

RUN curl -fsSL \
    "https://github.com/oliver006/redis_exporter/releases/download/${EXPORTER_VERSION}/redis_exporter-${EXPORTER_VERSION}.linux-amd64.tar.gz" \
    | tar xz --strip-components=1 \
    && chmod +x redis_exporter


FROM alpine:3.21 AS runtime

LABEL maintainer="nuniesmith" \
      description="Redis Prometheus Exporter — scrapes Redis metrics for Grafana"

RUN apk add --no-cache ca-certificates wget \
    && adduser --disabled-password --gecos '' --uid 1000 exporter

COPY --from=builder /build/redis_exporter        /usr/local/bin/redis_exporter
#COPY infrastructure/config/redis-exporter/       /etc/redis-exporter/

USER exporter
EXPOSE 9121

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -qO- http://localhost:9121/health || exit 1

ENTRYPOINT ["redis_exporter"]
