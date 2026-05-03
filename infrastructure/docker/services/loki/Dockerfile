# =============================================================================
# FKS — Loki (log aggregation)
# =============================================================================
# Builder : downloads the pre-built release binary
# Runtime : minimal alpine with binary + baked-in config
#
# Exposes :3100 for the Loki HTTP API (Grafana datasource + Promtail push)
# =============================================================================

FROM alpine:3.21 AS builder

ARG LOKI_VERSION=3.3.2

RUN apk add --no-cache ca-certificates curl unzip

WORKDIR /build

RUN curl -fsSL \
    "https://github.com/grafana/loki/releases/download/v${LOKI_VERSION}/loki-linux-amd64.zip" \
    -o loki.zip \
    && unzip loki.zip \
    && mv loki-linux-amd64 loki \
    && chmod +x loki


FROM alpine:3.21 AS runtime

LABEL maintainer="nuniesmith" \
      description="Grafana Loki — log aggregation backend for FKS services"

RUN apk add --no-cache ca-certificates wget \
    && adduser --disabled-password --gecos '' --uid 1000 loki \
    && mkdir -p /loki/chunks /loki/rules /loki/index \
    && chown -R loki:loki /loki

COPY --from=builder /build/loki                    /usr/local/bin/loki
COPY infrastructure/config/loki/loki.yaml          /etc/loki/loki.yaml

USER loki
EXPOSE 3100

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD wget -qO- http://localhost:3100/ready || exit 1

ENTRYPOINT ["loki"]
CMD ["-config.file=/etc/loki/loki.yaml"]
