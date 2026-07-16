# Dockerfile — Prometheus (custom image with baked-in config + alert rules)
# Build context: repository root (docker-compose sets `context: .`)
# All config is COPY'd in at build time — no host volume mounts needed for config.

FROM prom/prometheus:v2.53.0

# --- Main scrape / global config ---
COPY infrastructure/config/prometheus/prometheus.yml \
     /etc/prometheus/prometheus.yml

# --- Alert rules ---
COPY infrastructure/config/prometheus/alerts/data.yml \
     /etc/prometheus/alerts/data.yml
COPY infrastructure/config/prometheus/alerts/database-alerts.yml \
     /etc/prometheus/alerts/database-alerts.yml
COPY infrastructure/config/prometheus/alerts/execution_alerts.yml \
     /etc/prometheus/alerts/execution_alerts.yml
COPY infrastructure/config/prometheus/alerts/market-data-pipeline.yml \
     /etc/prometheus/alerts/market-data-pipeline.yml
COPY infrastructure/config/prometheus/alerts/technical-indicators.yml \
     /etc/prometheus/alerts/technical-indicators.yml
COPY infrastructure/config/prometheus/alerts/trading-alerts.yml \
     /etc/prometheus/alerts/trading-alerts.yml
COPY infrastructure/config/prometheus/alerts/bot-alerts.yml \
    /etc/prometheus/alerts/bot-alerts.yml
COPY infrastructure/config/prometheus/alerts/janus-silent-stall.yml \
     /etc/prometheus/alerts/janus-silent-stall.yml