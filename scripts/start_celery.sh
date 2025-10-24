#!/bin/bash
# Start Celery worker and beat scheduler
# Usage: ./start_celery.sh

echo "Starting Celery services..."

# Check if Redis is running
if ! redis-cli ping > /dev/null 2>&1; then
    echo "Error: Redis is not running. Please start Redis first."
    echo "Run: docker-compose up -d redis"
    exit 1
fi

# Activate virtual environment if exists
if [ -d "venv" ]; then
    source venv/bin/activate
elif [ -d ".venv" ]; then
    source .venv/bin/activate
fi

# Set Django settings module
export DJANGO_SETTINGS_MODULE=django.settings

# Create logs directory
mkdir -p logs

# Start Celery worker in background
echo "Starting Celery worker..."
celery -A django worker \
    --loglevel=info \
    --concurrency=4 \
    --logfile=logs/celery_worker.log \
    --pidfile=logs/celery_worker.pid \
    --detach

# Wait a moment for worker to start
sleep 2

# Start Celery beat scheduler in background
echo "Starting Celery beat scheduler..."
celery -A django beat \
    --loglevel=info \
    --scheduler django_celery_beat.schedulers:DatabaseScheduler \
    --logfile=logs/celery_beat.log \
    --pidfile=logs/celery_beat.pid \
    --detach

# Wait a moment
sleep 2

# Check if processes are running
if [ -f "logs/celery_worker.pid" ] && [ -f "logs/celery_beat.pid" ]; then
    echo ""
    echo "✅ Celery services started successfully!"
    echo ""
    echo "Worker PID: $(cat logs/celery_worker.pid)"
    echo "Beat PID: $(cat logs/celery_beat.pid)"
    echo ""
    echo "Logs:"
    echo "  Worker: logs/celery_worker.log"
    echo "  Beat: logs/celery_beat.log"
    echo ""
    echo "To stop Celery services, run: ./stop_celery.sh"
    echo "To monitor tasks, run: celery -A django events"
    echo "Or start Flower UI: celery -A django flower"
else
    echo "❌ Error: Failed to start Celery services"
    exit 1
fi
