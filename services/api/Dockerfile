FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
        PYTHONUNBUFFERED=1 \
        PIP_NO_CACHE_DIR=1 \
        SERVICE_NAME=api \
        SERVICE_TYPE=api \
        API_SERVICE_PORT=8000 \
        SERVICE_PORT=8000

WORKDIR /app

COPY requirements.txt pyproject.toml ./
RUN python -m pip install --upgrade pip && \
        python -m pip install -r requirements.txt && \
        python -m pip install .

COPY . .

ENV PYTHONPATH=/app/src

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
        CMD python -c "import os,urllib.request,sys;port=os.getenv('SERVICE_PORT','8000');u=f'http://localhost:{port}/health';\
import urllib.error;\
try: urllib.request.urlopen(u,timeout=3);\
except Exception: sys.exit(1)" || exit 1

EXPOSE 8000

RUN useradd -u 1000 -m appuser && chown -R appuser /app
USER appuser

CMD ["python", "src/main.py"]
