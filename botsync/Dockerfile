# botsync — one-shot: sync bots/*.yaml into the spawner, then exit.
# Runs on every `docker compose up` (restart: "no").
FROM python:3.13-alpine

RUN pip install --no-cache-dir pyyaml requests

WORKDIR /app
COPY sync.py /app/sync.py

ENTRYPOINT ["python", "/app/sync.py"]
