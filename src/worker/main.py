"""
WORKER Service Entry Point

This module serves as the entry point for the WORKER service, integrating with the main application
and utilizing the service template for service management.

NOTE: Internal package previously named 'queue' has been renamed to 'task_queue' to avoid shadowing
the Python standard library 'queue' module (which broke third-party libs expecting stdlib APIs).
"""

import os
import sys

from framework.services.template import start_template_service  # local template


def main():
    # Set the service name and port from environment variables or defaults
    service_name = os.getenv("WORKER_SERVICE_NAME", "worker")
    port = int(os.getenv("WORKER_SERVICE_PORT", os.getenv("SERVICE_PORT", "8006")))

    # Log the service startup
    print(f"Starting {service_name} service on port {port}")

    start_template_service(service_name=service_name, service_port=port)


if __name__ == "__main__":
    sys.exit(main())
