# =============================================================================
# FKS — Jaeger (distributed tracing)
# =============================================================================
# Builder : downloads the all-in-one pre-built release binary
# Runtime : minimal alpine with binary + sampling config
#
# Ports:
#   16686 — Jaeger web UI
#   4317  — OTLP gRPC receiver
#   4318  — OTLP HTTP receiver
#   14268 — Jaeger HTTP collector (legacy)
# =============================================================================

FROM alpine:3.21 AS builder

ARG JAEGER_VERSION=1.65.0

RUN apk add --no-cache ca-certificates curl tar

WORKDIR /build

RUN curl -fsSL \
    "https://github.com/jaegertracing/jaeger/releases/download/v${JAEGER_VERSION}/jaeger-${JAEGER_VERSION}-linux-amd64.tar.gz" \
    | tar xz --strip-components=1 \
    && chmod +x jaeger-all-in-one


FROM alpine:3.21 AS runtime

LABEL maintainer="nuniesmith" \
      description="Jaeger all-in-one — distributed tracing for FKS microservices"

RUN apk add --no-cache ca-certificates wget \
    && adduser --disabled-password --gecos '' --uid 1000 jaeger

COPY --from=builder /build/jaeger-all-in-one          /usr/local/bin/jaeger-all-in-one
COPY infrastructure/config/jaeger/sampling.json        /etc/jaeger/sampling.json

USER jaeger
EXPOSE 16686 4317 4318 14268

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD wget -qO- http://localhost:14269/ || exit 1

ENTRYPOINT ["jaeger-all-in-one"]
CMD [ \
    "--sampling.strategies-file=/etc/jaeger/sampling.json", \
    "--collector.otlp.enabled=true" \
]
