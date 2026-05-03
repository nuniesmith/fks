# =============================================================================
# FKS — Promtail (log shipper)
# =============================================================================
# Thin wrapper over the official Grafana Promtail image.
# Config is bind-mounted at runtime via docker-compose:
#   ./infrastructure/config/promtail/promtail-simple.yml → /etc/promtail/config.yml
#
# Add any customisations (extra tools, CA certs, etc.) below.
# =============================================================================

FROM grafana/promtail:3.5.0

# Add curl for debugging / ad-hoc healthchecks if needed.
# The base image is Ubuntu-based and ships apt-get.
USER root
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl ca-certificates && \
    rm -rf /var/lib/apt/lists/*
USER nobody
