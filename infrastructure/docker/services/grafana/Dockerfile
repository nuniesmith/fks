# Dockerfile — Grafana (custom image with baked-in provisioning & dashboards)
# Build context: repository root (docker-compose sets `context: .`)
# All config is COPY'd in at build time — no host volume mounts needed for config.

FROM grafana/grafana:12.4.2

# --- Datasource provisioning ---
COPY infrastructure/config/grafana/provisioning/datasources/prometheus.yml \
     /etc/grafana/provisioning/datasources/prometheus.yml

COPY infrastructure/config/grafana/provisioning/datasources/loki.yaml \
     /etc/grafana/provisioning/datasources/loki.yaml

# --- Dashboard provisioning ---
COPY infrastructure/config/grafana/provisioning/dashboards/dashboard.yml \
     /etc/grafana/provisioning/dashboards/dashboard.yml

COPY infrastructure/config/grafana/provisioning/dashboards/fks-logs.json \
     /etc/grafana/provisioning/dashboards/fks-logs.json

COPY infrastructure/config/grafana/provisioning/dashboards/strategy-performance.json \
     /etc/grafana/provisioning/dashboards/strategy-performance.json

# --- Dashboard JSONs ---
COPY infrastructure/config/grafana/dashboards/30-day-paper-trading.json \
     /var/lib/grafana/dashboards/30-day-paper-trading.json

COPY infrastructure/config/grafana/dashboards/backfill-orchestration.json \
     /var/lib/grafana/dashboards/backfill-orchestration.json

COPY infrastructure/config/grafana/dashboards/database-monitoring.json \
     /var/lib/grafana/dashboards/database-monitoring.json

COPY infrastructure/config/grafana/dashboards/execution_overview.json \
     /var/lib/grafana/dashboards/execution_overview.json

COPY infrastructure/config/grafana/dashboards/fks-trading-dashboard.json \
     /var/lib/grafana/dashboards/fks-trading-dashboard.json

COPY infrastructure/config/grafana/dashboards/gap-detection.json \
     /var/lib/grafana/dashboards/gap-detection.json

COPY infrastructure/config/grafana/dashboards/market-data-pipeline.json \
     /var/lib/grafana/dashboards/market-data-pipeline.json

COPY infrastructure/config/grafana/dashboards/operations-overview.json \
     /var/lib/grafana/dashboards/operations-overview.json

COPY infrastructure/config/grafana/dashboards/optimizer.json \
     /var/lib/grafana/dashboards/optimizer.json

COPY infrastructure/config/grafana/dashboards/performance-ingestion.json \
     /var/lib/grafana/dashboards/performance-ingestion.json

COPY infrastructure/config/grafana/dashboards/rate-limiter.json \
     /var/lib/grafana/dashboards/rate-limiter.json

COPY infrastructure/config/grafana/dashboards/rpc_dashboard.json \
     /var/lib/grafana/dashboards/rpc_dashboard.json

COPY infrastructure/config/grafana/dashboards/slo-dashboard.json \
     /var/lib/grafana/dashboards/slo-dashboard.json

COPY infrastructure/config/grafana/dashboards/slo-error-budget.json \
     /var/lib/grafana/dashboards/slo-error-budget.json

COPY infrastructure/config/grafana/dashboards/strategy-performance.json \
     /var/lib/grafana/dashboards/strategy-performance.json

COPY infrastructure/config/grafana/dashboards/technical-indicators.json \
     /var/lib/grafana/dashboards/technical-indicators.json
