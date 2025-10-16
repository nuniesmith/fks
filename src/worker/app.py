"""
Custom FKS Worker Service

Standalone worker service implementation without shared framework dependencies.
"""

import os
import json
import time
import logging
from datetime import datetime
from flask import Flask, jsonify
import pytz

# Set up logging without being shadowed by local helper module
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(__name__)

# Service configuration
SERVICE_NAME = "fks_worker"
SERVICE_PORT = int(os.getenv("WORKER_SERVICE_PORT", "4600"))
TIMEZONE = pytz.timezone("America/Toronto")

# Global task queue (simple in-memory for now)
task_queue = []
task_results = {}

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    toronto_time = datetime.now(TIMEZONE)
    return jsonify({
        "status": "healthy",
        "service": SERVICE_NAME,
        "timestamp": toronto_time.isoformat(),
        "timezone": "America/Toronto",
        "queue_size": len(task_queue),
        "results_count": len(task_results)
    })

@app.route('/status', methods=['GET'])
def status():
    """Service status endpoint"""
    toronto_time = datetime.now(TIMEZONE)
    return jsonify({
        "service": SERVICE_NAME,
        "status": "running",
        "timestamp": toronto_time.isoformat(),
        "port": SERVICE_PORT,
        "queue_size": len(task_queue),
        "results_count": len(task_results)
    })

@app.route('/tasks', methods=['GET'])
def list_tasks():
    """List pending tasks"""
    return jsonify({
        "queue_size": len(task_queue),
        "results_count": len(task_results),
        "tasks": task_queue[-10:] if task_queue else []  # Last 10 tasks
    })

@app.route('/submit-task', methods=['POST'])
def submit_task():
    """Submit a task to the queue"""
    try:
        from flask import request
        task_data = request.get_json()
        task_id = f"task_{int(time.time())}_{len(task_queue)}"
        
        task = {
            "id": task_id,
            "data": task_data,
            "submitted_at": datetime.now(TIMEZONE).isoformat(),
            "status": "pending"
        }
        
        task_queue.append(task)
        logger.info(f"Task {task_id} submitted to queue")
        
        return jsonify({
            "success": True,
            "task_id": task_id,
            "queue_position": len(task_queue)
        })
    except Exception as e:
        logger.error(f"Error submitting task: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    logger.info(f"Starting {SERVICE_NAME} service on port {SERVICE_PORT}")
    logger.info(f"Timezone: {TIMEZONE}")
    app.run(host='0.0.0.0', port=SERVICE_PORT, debug=False, use_reloader=False, threaded=True)
