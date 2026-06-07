# =============================================================================
# FKS — Alertmanager (Prometheus alert routing)
# =============================================================================
# Builder : downloads the pre-built release binary
# Runtime : minimal alpine with binary + baked-in routing config
#
# Exposes :9093 for the Alertmanager HTTP API + web UI
# =============================================================================

FROM alpine:3.21 AS builder

# NOTE: Prometheus-ecosystem releases tag as vX.Y.Z but the asset filename
# drops the leading 'v' (alertmanager-0.27.0.linux-amd64.tar.gz). Keep the
# version bare and add the 'v' only in the tag path.
ARG ALERTMANAGER_VERSION=0.27.0

RUN apk add --no-cache ca-certificates curl tar

WORKDIR /build

RUN curl -fsSL \
    "https://github.com/prometheus/alertmanager/releases/download/v${ALERTMANAGER_VERSION}/alertmanager-${ALERTMANAGER_VERSION}.linux-amd64.tar.gz" \
    | tar xz --strip-components=1 \
    && chmod +x alertmanager amtool


FROM alpine:3.21 AS runtime

LABEL maintainer="nuniesmith" \
      description="Prometheus Alertmanager — routes FKS alerts to Discord and PagerDuty"

RUN apk add --no-cache ca-certificates wget \
    && adduser --disabled-password --gecos '' --uid 1000 alertmanager \
    && mkdir -p /alertmanager \
    && chown alertmanager:alertmanager /alertmanager

COPY --from=builder /build/alertmanager               /usr/local/bin/alertmanager
COPY --from=builder /build/amtool                     /usr/local/bin/amtool
COPY infrastructure/config/alertmanager/alertmanager.yml /etc/alertmanager/alertmanager.yml

USER alertmanager
EXPOSE 9093

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -qO- http://localhost:9093/-/healthy || exit 1

ENTRYPOINT ["alertmanager"]
CMD [ \
    "--config.file=/etc/alertmanager/alertmanager.yml", \
    "--storage.path=/alertmanager" \
]
