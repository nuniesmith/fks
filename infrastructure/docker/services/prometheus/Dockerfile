# Dockerfile — Prometheus (custom image with baked-in config + alert rules)
# Build context: repository root (docker-compose sets `context: .`)
# All config is COPY'd in at build time — no host volume mounts needed for config.

FROM prom/prometheus:v2.53.0

# --- Main scrape / global config ---
COPY infrastructure/config/prometheus/prometheus.yml \
     /etc/prometheus/prometheus.yml

# --- Alert rules ---
# Copy the whole alerts/ dir so every *.yml rule file ships automatically.
# (Individual per-file COPYs were a footgun: a new rule file silently didn't
# bake in until someone remembered to add a matching COPY line — see #209/#210.)
COPY infrastructure/config/prometheus/alerts/ /etc/prometheus/alerts/