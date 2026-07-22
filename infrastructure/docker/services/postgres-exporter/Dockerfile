# =============================================================================
# FKS — Postgres Exporter
# =============================================================================
# Builder : downloads the pre-built release binary
# Runtime : minimal alpine with the binary + custom query config
#
# Exposes :9187/metrics for Prometheus scraping
# =============================================================================

FROM alpine:3.21 AS builder

# NOTE: prometheus-community releases tag as vX.Y.Z but the asset filename
# drops the leading 'v' (postgres_exporter-0.19.1.linux-amd64.tar.gz). Keep the
# version bare and add the 'v' only in the tag path.
ARG EXPORTER_VERSION=0.19.1

RUN apk add --no-cache ca-certificates curl tar

WORKDIR /build

RUN curl -fsSL \
    "https://github.com/prometheus-community/postgres_exporter/releases/download/v${EXPORTER_VERSION}/postgres_exporter-${EXPORTER_VERSION}.linux-amd64.tar.gz" \
    | tar xz --strip-components=1 \
    && chmod +x postgres_exporter


FROM alpine:3.21 AS runtime

LABEL maintainer="nuniesmith" \
      description="Postgres Prometheus Exporter — scrapes janus_db and fks_db metrics"

RUN apk add --no-cache ca-certificates wget \
    && adduser --disabled-password --gecos '' --uid 1000 exporter

COPY --from=builder /build/postgres_exporter          /usr/local/bin/postgres_exporter

# Custom queries file — extends the built-in collector with FKS-specific queries
# (table sizes, replication lag, long-running queries, etc.)
COPY infrastructure/config/postgres-exporter/queries.yaml /etc/postgres-exporter/queries.yaml

USER exporter
EXPOSE 9187

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -qO- http://localhost:9187/metrics > /dev/null || exit 1

ENTRYPOINT ["postgres_exporter"]
CMD ["--extend.query-path=/etc/postgres-exporter/queries.yaml"]
