FROM python:3.13-slim AS builder

WORKDIR /app
COPY infrastructure/docker/services/alertmanager-discord/requirements.txt requirements.txt
RUN pip install --no-cache-dir -q --prefix=/install -r requirements.txt

FROM python:3.13-slim AS runtime

LABEL maintainer="nuniesmith" \
      description="Alertmanager Discord Bridge - converts webhooks to Discord embeds"

RUN adduser --disabled-password --gecos '' --uid 1000 bridge

WORKDIR /app

COPY --from=builder /install /usr/local
COPY infrastructure/docker/services/alertmanager-discord/bridge.py bridge.py

RUN chown -R bridge:bridge /app

USER bridge
EXPOSE 9094

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:9094/health')" || exit 1

CMD ["python", "bridge.py"]