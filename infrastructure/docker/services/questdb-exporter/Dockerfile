# =============================================================================
# FKS — QuestDB Exporter
# =============================================================================
# Builder : installs Python dependencies into an isolated prefix
# Runtime : minimal python:slim with installed packages + exporter script
#
# Custom Prometheus exporter that queries QuestDB's REST API and exposes
# time-series metrics (row counts, ingestion lag, query latency) for Grafana.
#
# Exposes :9122/metrics for Prometheus scraping
# =============================================================================

FROM python:3.13-slim AS builder

WORKDIR /app

COPY infrastructure/config/questdb-exporter/requirements.txt requirements.txt

RUN pip install --no-cache-dir -q --prefix=/install -r requirements.txt


FROM python:3.13-slim AS runtime

LABEL maintainer="nuniesmith" \
      description="QuestDB Prometheus Exporter — exposes QuestDB metrics for Grafana"

RUN adduser --disabled-password --gecos '' --uid 1000 exporter

WORKDIR /app

COPY --from=builder /install                              /usr/local
COPY infrastructure/config/questdb-exporter/exporter.py  exporter.py

RUN chown -R exporter:exporter /app

USER exporter
EXPOSE 9122

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:9122/health')" || exit 1

CMD ["python", "exporter.py"]
