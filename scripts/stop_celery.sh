#!/bin/bash
# Stop Celery worker and beat scheduler
# Usage: ./stop_celery.sh

echo "Stopping Celery services..."

# Stop Celery worker
if [ -f "logs/celery_worker.pid" ]; then
    WORKER_PID=$(cat logs/celery_worker.pid)
    echo "Stopping Celery worker (PID: $WORKER_PID)..."
    kill -TERM $WORKER_PID 2>/dev/null
    
    # Wait for graceful shutdown
    sleep 3
    
    # Force kill if still running
    if ps -p $WORKER_PID > /dev/null 2>&1; then
        echo "Force killing worker..."
        kill -KILL $WORKER_PID 2>/dev/null
    fi
    
    rm -f logs/celery_worker.pid
    echo "✅ Worker stopped"
else
    echo "Worker PID file not found"
fi

# Stop Celery beat
if [ -f "logs/celery_beat.pid" ]; then
    BEAT_PID=$(cat logs/celery_beat.pid)
    echo "Stopping Celery beat (PID: $BEAT_PID)..."
    kill -TERM $BEAT_PID 2>/dev/null
    
    # Wait for graceful shutdown
    sleep 2
    
    # Force kill if still running
    if ps -p $BEAT_PID > /dev/null 2>&1; then
        echo "Force killing beat..."
        kill -KILL $BEAT_PID 2>/dev/null
    fi
    
    rm -f logs/celery_beat.pid
    echo "✅ Beat stopped"
else
    echo "Beat PID file not found"
fi

echo ""
echo "Celery services stopped"
