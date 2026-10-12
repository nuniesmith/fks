# janus-bridge — Milestone 1: daily logged Janus<->crypto regime assessment.
#
# Read-only/advisory by design. Every 5 minutes it polls Janus's
# RegimeBridgeService (GetCurrentRegime), records the crypto-regime bot's own
# daily regime flags from its state.json (read-only volume mount), and at the
# close of each 00:05->00:05 UTC window appends one JSONL assessment line per
# pair plus a window summary. It never touches the bot and never posts
# anywhere.
FROM python:3.13-slim

ENV GRPCURL_VERSION=1.9.3
RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates curl \
 && curl -fsSL -o /tmp/grpcurl.tgz "https://github.com/fullstorydev/grpcurl/releases/download/v${GRPCURL_VERSION}/grpcurl_${GRPCURL_VERSION}_linux_x86_64.tar.gz" \
 && tar -xzf /tmp/grpcurl.tgz -C /usr/local/bin grpcurl \
 && rm /tmp/grpcurl.tgz \
 && apt-get purge -y --auto-remove curl \
 && rm -rf /var/lib/apt/lists/* \
 && adduser --disabled-password --gecos '' --uid 1000 bridge

WORKDIR /app
COPY infrastructure/docker/services/janus-bridge/regime_bridge.proto /proto/fks/janus/v1/regime_bridge.proto
COPY infrastructure/docker/services/janus-bridge/app.py /app/app.py
RUN mkdir -p /data && chown -R bridge:bridge /app /data

USER bridge

HEALTHCHECK --interval=60s --timeout=10s --start-period=180s --retries=3 \
  CMD python -c "import json,time; s=json.load(open('/tmp/janus-bridge.status')); assert time.time()-s['last_poll']<900" || exit 1

CMD ["python", "/app/app.py"]
