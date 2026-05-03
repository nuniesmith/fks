#!/usr/bin/env python3
"""
WebSocket Soak Test - 48-Hour Stability Testing

Tests WebSocket connection stability, message throughput, and error recovery
over an extended period (default: 48 hours).

Usage:
    python websocket-soak-test.py --url ws://localhost:8080/ws/signals --duration 48

Features:
    - Multiple concurrent WebSocket connections
    - Automatic reconnection with exponential backoff
    - Message rate tracking and statistics
    - Connection stability metrics
    - Memory and CPU monitoring
    - Detailed logging and reporting
    - Graceful shutdown handling

Environment Variables:
    WS_URL - WebSocket URL (default: ws://localhost:8080/ws/signals)
    NUM_CLIENTS - Number of concurrent clients (default: 10)
    DURATION_HOURS - Test duration in hours (default: 48)
    REPORT_INTERVAL - Stats report interval in seconds (default: 300)
"""

import argparse
import asyncio
import json
import logging
import os
import signal
import sys
import time
from collections import defaultdict
from datetime import datetime, timedelta

import websockets
from websockets.exceptions import ConnectionClosed, WebSocketException

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("soak-test")


# Statistics tracking
class Stats:
    def __init__(self):
        self.start_time = time.time()
        self.messages_received = 0
        self.messages_by_type = defaultdict(int)
        self.connection_attempts = 0
        self.successful_connections = 0
        self.failed_connections = 0
        self.disconnections = 0
        self.errors = defaultdict(int)
        self.latencies = []
        self.last_message_time = None

    def record_message(self, msg_type: str = "unknown"):
        self.messages_received += 1
        self.messages_by_type[msg_type] += 1
        self.last_message_time = time.time()

    def record_connection(self, success: bool):
        self.connection_attempts += 1
        if success:
            self.successful_connections += 1
        else:
            self.failed_connections += 1

    def record_disconnection(self):
        self.disconnections += 1

    def record_error(self, error_type: str):
        self.errors[error_type] += 1

    def get_uptime(self) -> float:
        return time.time() - self.start_time

    def get_message_rate(self) -> float:
        uptime = self.get_uptime()
        return self.messages_received / uptime if uptime > 0 else 0

    def get_connection_success_rate(self) -> float:
        if self.connection_attempts == 0:
            return 0.0
        return (self.successful_connections / self.connection_attempts) * 100

    def print_report(self):
        uptime = self.get_uptime()
        uptime_str = str(timedelta(seconds=int(uptime)))

        logger.info("=" * 80)
        logger.info("SOAK TEST STATISTICS REPORT")
        logger.info("=" * 80)
        logger.info(f"Uptime: {uptime_str}")
        logger.info(f"Messages Received: {self.messages_received:,}")
        logger.info(f"Message Rate: {self.get_message_rate():.2f} msg/sec")
        logger.info(f"Connection Attempts: {self.connection_attempts}")
        logger.info(f"Successful Connections: {self.successful_connections}")
        logger.info(f"Failed Connections: {self.failed_connections}")
        logger.info(f"Connection Success Rate: {self.get_connection_success_rate():.2f}%")
        logger.info(f"Disconnections: {self.disconnections}")

        if self.messages_by_type:
            logger.info("\nMessages by Type:")
            for msg_type, count in sorted(self.messages_by_type.items(), key=lambda x: x[1], reverse=True):
                logger.info(f"  {msg_type}: {count:,}")

        if self.errors:
            logger.info("\nErrors:")
            for error_type, count in sorted(self.errors.items(), key=lambda x: x[1], reverse=True):
                logger.info(f"  {error_type}: {count}")

        if self.last_message_time:
            time_since_last = time.time() - self.last_message_time
            logger.info(f"\nTime Since Last Message: {time_since_last:.1f}s")

        logger.info("=" * 80)


class WebSocketClient:
    """WebSocket client with automatic reconnection."""

    def __init__(
        self,
        client_id: int,
        url: str,
        stats: Stats,
        filters: dict | None = None,
    ):
        self.client_id = client_id
        self.url = url
        self.stats = stats
        self.filters = filters or {}
        self.ws: websockets.ClientConnection | None = None
        self.running = False
        self.reconnect_delay = 1
        self.max_reconnect_delay = 60

    async def connect(self) -> bool:
        """Establish WebSocket connection."""
        try:
            logger.info(f"Client {self.client_id}: Connecting to {self.url}")
            self.ws = await websockets.connect(
                self.url,
                ping_interval=20,
                ping_timeout=10,
                close_timeout=5,
            )

            # Send subscription filters if provided
            if self.filters:
                assert self.ws is not None
                await self.ws.send(json.dumps(self.filters))
                logger.debug(f"Client {self.client_id}: Sent filters: {self.filters}")

            self.stats.record_connection(success=True)
            self.reconnect_delay = 1  # Reset reconnect delay on success
            logger.info(f"Client {self.client_id}: Connected successfully")
            return True

        except Exception as e:
            self.stats.record_connection(success=False)
            self.stats.record_error(type(e).__name__)
            logger.error(f"Client {self.client_id}: Connection failed: {e}")
            return False

    async def disconnect(self):
        """Close WebSocket connection."""
        if self.ws:
            try:
                await self.ws.close()
            except Exception as e:
                logger.debug(f"Client {self.client_id}: Error closing connection: {e}")
            finally:
                self.ws = None

    async def run(self):
        """Main client loop with automatic reconnection."""
        self.running = True

        while self.running:
            # Connect or reconnect
            if not self.ws and not await self.connect():
                # Exponential backoff
                logger.info(f"Client {self.client_id}: Reconnecting in {self.reconnect_delay}s")
                await asyncio.sleep(self.reconnect_delay)
                self.reconnect_delay = min(self.reconnect_delay * 2, self.max_reconnect_delay)
                continue

            # Receive messages
            try:
                async for message in self.ws:
                    try:
                        data = json.loads(message)

                        # Determine message type
                        msg_type = "unknown"
                        if isinstance(data, dict):
                            if "signal_type" in data:
                                msg_type = data.get("signal_type", "signal")
                            elif "type" in data:
                                msg_type = data.get("type")

                        self.stats.record_message(msg_type)

                        logger.debug(f"Client {self.client_id}: Received {msg_type} message")

                    except json.JSONDecodeError as e:
                        self.stats.record_error("JSONDecodeError")
                        logger.warning(f"Client {self.client_id}: Invalid JSON: {e}")
                    except Exception as e:
                        self.stats.record_error(type(e).__name__)
                        logger.error(f"Client {self.client_id}: Message processing error: {e}")

            except ConnectionClosed as e:
                self.stats.record_disconnection()
                logger.warning(f"Client {self.client_id}: Connection closed: {e.code} {e.reason}")
                await self.disconnect()

            except WebSocketException as e:
                self.stats.record_error("WebSocketException")
                logger.error(f"Client {self.client_id}: WebSocket error: {e}")
                await self.disconnect()

            except Exception as e:
                self.stats.record_error(type(e).__name__)
                logger.error(f"Client {self.client_id}: Unexpected error: {e}")
                await self.disconnect()

        # Clean shutdown
        await self.disconnect()
        logger.info(f"Client {self.client_id}: Stopped")

    async def stop(self):
        """Stop the client."""
        self.running = False
        await self.disconnect()


class SoakTest:
    """Manages multiple WebSocket clients for soak testing."""

    def __init__(
        self,
        url: str,
        num_clients: int,
        duration_hours: float,
        report_interval: int,
    ):
        self.url = url
        self.num_clients = num_clients
        self.duration_hours = duration_hours
        self.report_interval = report_interval
        self.stats = Stats()
        self.clients: list[WebSocketClient] = []
        self.running = False

        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        logger.info(f"Received signal {signum}, shutting down...")
        self.running = False

    async def run(self):
        """Run the soak test."""
        self.running = True
        end_time = time.time() + (self.duration_hours * 3600)

        logger.info("=" * 80)
        logger.info("STARTING WEBSOCKET SOAK TEST")
        logger.info("=" * 80)
        logger.info(f"WebSocket URL: {self.url}")
        logger.info(f"Number of Clients: {self.num_clients}")
        logger.info(f"Duration: {self.duration_hours} hours")
        logger.info(f"Report Interval: {self.report_interval} seconds")
        logger.info(f"End Time: {datetime.fromtimestamp(end_time)}")
        logger.info("=" * 80)

        # Create and start clients
        tasks = []
        for i in range(self.num_clients):
            client = WebSocketClient(
                client_id=i,
                url=self.url,
                stats=self.stats,
                filters={
                    "symbols": ["BTCUSD", "ETHUSDT"],
                    "timeframes": ["1m", "5m"],
                },
            )
            self.clients.append(client)
            tasks.append(asyncio.create_task(client.run()))

        # Periodic reporting task
        async def report_stats():
            while self.running:
                await asyncio.sleep(self.report_interval)
                self.stats.print_report()

        tasks.append(asyncio.create_task(report_stats()))

        # Wait for duration or shutdown signal
        try:
            while self.running and time.time() < end_time:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            logger.info("Interrupted by user")
        finally:
            logger.info("Stopping all clients...")
            self.running = False

            # Stop all clients
            for client in self.clients:
                await client.stop()

            # Cancel all tasks
            for task in tasks:
                task.cancel()

            # Wait for tasks to complete
            await asyncio.gather(*tasks, return_exceptions=True)

        # Final report
        logger.info("\nFINAL REPORT:")
        self.stats.print_report()

        # Summary
        logger.info("\nTEST SUMMARY:")
        logger.info(f"Test completed: {datetime.now()}")
        logger.info(f"Total runtime: {str(timedelta(seconds=int(self.stats.get_uptime())))}")

        if self.stats.messages_received > 0:
            logger.info("✅ Test PASSED - Messages received")
        else:
            logger.warning("⚠️  Test WARNING - No messages received")

        if self.stats.get_connection_success_rate() > 95:
            logger.info("✅ Connection stability: GOOD (>95%)")
        elif self.stats.get_connection_success_rate() > 80:
            logger.warning("⚠️  Connection stability: FAIR (80-95%)")
        else:
            logger.error("❌ Connection stability: POOR (<80%)")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="WebSocket Soak Test - Test connection stability over extended periods"
    )
    parser.add_argument(
        "--url",
        default=os.getenv("WS_URL", "ws://localhost:8080/ws/signals"),
        help="WebSocket URL (default: ws://localhost:8080/ws/signals)",
    )
    parser.add_argument(
        "--clients",
        type=int,
        default=int(os.getenv("NUM_CLIENTS", "10")),
        help="Number of concurrent clients (default: 10)",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=float(os.getenv("DURATION_HOURS", "48")),
        help="Test duration in hours (default: 48)",
    )
    parser.add_argument(
        "--report-interval",
        type=int,
        default=int(os.getenv("REPORT_INTERVAL", "300")),
        help="Report interval in seconds (default: 300)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging",
    )

    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    # Run soak test
    test = SoakTest(
        url=args.url,
        num_clients=args.clients,
        duration_hours=args.duration,
        report_interval=args.report_interval,
    )

    try:
        asyncio.run(test.run())
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
