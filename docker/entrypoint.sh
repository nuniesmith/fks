#!/bin/sh
# entrypoint.sh - Docker entrypoint script for FKS web service
# This ensures proper startup order and error handling

set -e  # Exit immediately if a command exits with a non-zero status

echo "=========================================="
echo "FKS Trading Platform - Starting Web Service"
echo "=========================================="

# Wait for database to be ready
echo "Waiting for PostgreSQL..."
until python manage.py dbshell --command="SELECT 1" > /dev/null 2>&1; do
  echo "PostgreSQL is unavailable - sleeping"
  sleep 2
done
echo "✓ PostgreSQL is up"

# Wait for Redis to be ready
echo "Checking Redis connection..."
python -c "import redis; r = redis.Redis(host='redis', port=6379, db=0); r.ping()" || {
  echo "Redis is unavailable - sleeping"
  sleep 2
}
echo "✓ Redis is up"

# Run database migrations
echo "Running database migrations..."
python manage.py migrate --noinput

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput

# Create cache table (if using database cache)
echo "Setting up cache..."
python manage.py createcachetable || true

echo "=========================================="
echo "✓ Initialization complete"
echo "Starting Gunicorn..."
echo "=========================================="

# Execute the main process (replace shell with gunicorn)
exec gunicorn web.django.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers ${GUNICORN_WORKERS:-4} \
    --timeout ${GUNICORN_TIMEOUT:-120} \
    --access-logfile ${GUNICORN_ACCESS_LOG:-/var/log/gunicorn/access.log} \
    --error-logfile ${GUNICORN_ERROR_LOG:-/var/log/gunicorn/error.log} \
    --log-level ${GUNICORN_LOG_LEVEL:-info}
