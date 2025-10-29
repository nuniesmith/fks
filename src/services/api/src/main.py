"""
API Service Entry Point

This module serves as the entry point for the API service using FastAPI with CORS support.
"""

import os, sys
import uvicorn

# Flat layout: simply import fastapi_main.app
from fastapi_main import app  # type: ignore


def main():
    # Set the service name and port from environment variables or defaults
    service_name = os.getenv("API_SERVICE_NAME", "api")
    port = int(os.getenv("API_SERVICE_PORT", "8001"))
    host = os.getenv("API_SERVICE_HOST", "0.0.0.0")
    env = os.getenv("APP_ENV", "development")

    # Log the service startup
    print(f"Starting {service_name} service on {host}:{port}")
    
    # Start uvicorn programmatically (no reload to keep container light)
    uvicorn.run(app, host=host, port=port, reload=False, log_level="info")


if __name__ == "__main__":
    sys.exit(main())
