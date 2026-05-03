#!/usr/bin/env python3
"""
HTTP Soak Test - 48-Hour Service Stability Testing

Tests service health, signal generation, and API stability over an extended
period (default: 48 hours) using HTTP endpoints.

Usage:
    python http-soak-test.py --duration 48

Features:
    - Service health monitoring (Janus, Execution, QuestDB, Redis)
    - Signal generation tracking
    - API response time monitoring
    - Memory and resource usage tracking via Docker stats
    - Detailed logging and reporting
    - Graceful shutdown handling

Environment Variables:
    JANUS_URL - Janus service URL (default: http://localhost:7000)
    EXECUTION_URL - Execution service URL (default: http://localhost:7000)
                    NOTE: Execution is embedded inside Janus, so this defaults
                    to the Janus URL. Set to http://localhost:8081 only if
                    execution is running as a standalone service.
    DURATION_HOURS - Test duration in hours (default: 48)
    POLL_INTERVAL - Polling interval in seconds (default: 30)
    REPORT_INTERVAL - Stats report interval in seconds (default: 300)
"""

import argparse
import asyncio
import json
import logging
import os
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections import defaultdict
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("http-soak-test")


class Stats:
    """Statistics tracking for the soak test."""

    def __init__(self):
        self.start_time = time.time()
        self.health_checks = 0
        self.health_successes = 0
        self.health_failures = 0
        self.signals_observed = 0
        self.last_signal_count = 0
        self.api_calls = defaultdict(int)
        self.api_errors = defaultdict(int)
        self.api_latencies: dict[str, list[float]] = defaultdict(list)
        self.service_status: dict[str, bool] = {}
        self.memory_samples: list[dict[str, str | float]] = []
        self.errors: list[str] = []
        self.last_check_time: float | None = None

    def record_health_check(self, success: bool, service: str):
        self.health_checks += 1
        if success:
            self.health_successes += 1
            self.service_status[service] = True
        else:
            self.health_failures += 1
            self.service_status[service] = False
        self.last_check_time = time.time()

    def record_api_call(self, endpoint: str, latency_ms: float, success: bool):
        self.api_calls[endpoint] += 1
        self.api_latencies[endpoint].append(latency_ms)
        if not success:
            self.api_errors[endpoint] += 1

    def record_signals(self, count: int):
        if count > self.signals_observed:
            self.signals_observed = count

    def record_error(self, error: str):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.errors.append(f"[{timestamp}] {error}")
        # Keep only last 100 errors
        if len(self.errors) > 100:
            self.errors = self.errors[-100:]

    def record_memory(self, service: str, memory_mb: float):
        self.memory_samples.append({"timestamp": time.time(), "service": service, "memory_mb": memory_mb})  # type: ignore[dict-item]
        # Keep only last 1000 samples
        if len(self.memory_samples) > 1000:
            self.memory_samples = self.memory_samples[-1000:]

    def get_uptime(self) -> float:
        return time.time() - self.start_time

    def get_health_rate(self) -> float:
        if self.health_checks == 0:
            return 0.0
        return (self.health_successes / self.health_checks) * 100

    def get_avg_latency(self, endpoint: str) -> float:
        latencies = self.api_latencies.get(endpoint, [])
        if not latencies:
            return 0.0
        return sum(latencies) / len(latencies)

    def get_p99_latency(self, endpoint: str) -> float:
        latencies = self.api_latencies.get(endpoint, [])
        if not latencies:
            return 0.0
        sorted_latencies = sorted(latencies)
        idx = int(len(sorted_latencies) * 0.99)
        return sorted_latencies[min(idx, len(sorted_latencies) - 1)]

    def print_report(self):
        uptime = self.get_uptime()
        uptime_str = str(timedelta(seconds=int(uptime)))

        logger.info("=" * 80)
        logger.info("SOAK TEST STATISTICS REPORT")
        logger.info("=" * 80)
        logger.info(f"Uptime: {uptime_str}")
        logger.info(f"Health Checks: {self.health_checks}")
        logger.info(f"Health Success Rate: {self.get_health_rate():.2f}%")
        logger.info(f"Total Signals Observed: {self.signals_observed}")

        logger.info("\nService Status:")
        for service, status in self.service_status.items():
            status_str = "✅ UP" if status else "❌ DOWN"
            logger.info(f"  {service}: {status_str}")

        logger.info("\nAPI Call Statistics:")
        for endpoint, count in sorted(self.api_calls.items()):
            errors = self.api_errors.get(endpoint, 0)
            avg_latency = self.get_avg_latency(endpoint)
            p99_latency = self.get_p99_latency(endpoint)
            error_rate = (errors / count * 100) if count > 0 else 0
            logger.info(
                f"  {endpoint}: {count} calls, {error_rate:.1f}% errors, "
                f"avg={avg_latency:.1f}ms, p99={p99_latency:.1f}ms"
            )

        if self.memory_samples:
            # Get latest memory readings per service
            latest_memory = {}
            for sample in reversed(self.memory_samples):
                service = sample["service"]
                if service not in latest_memory:
                    latest_memory[service] = sample["memory_mb"]
            logger.info("\nMemory Usage (latest):")
            for service, memory in latest_memory.items():
                logger.info(f"  {service}: {memory:.1f} MB")

        if self.errors:
            logger.info(f"\nRecent Errors ({len(self.errors)} total):")
            for error in self.errors[-5:]:
                logger.info(f"  {error}")

        logger.info("=" * 80)


class ServiceMonitor:
    """Monitors service health and metrics."""

    def __init__(
        self,
        janus_url: str,
        execution_url: str,
        questdb_url: str,
        stats: Stats,
    ):
        self.janus_url = janus_url
        self.execution_url = execution_url
        self.questdb_url = questdb_url
        self.stats = stats
        self.running = False

    def _http_get(self, url: str, timeout: float = 10.0) -> tuple[dict | None, float]:
        """Make HTTP GET request and return (response_json, latency_ms)."""
        start = time.time()
        try:
            req = urllib.request.Request(url)
            req.add_header("Accept", "application/json")
            with urllib.request.urlopen(req, timeout=timeout) as response:
                latency_ms = (time.time() - start) * 1000
                data = json.loads(response.read().decode())
                return data, latency_ms
        except urllib.error.URLError:
            latency_ms = (time.time() - start) * 1000
            return None, latency_ms
        except json.JSONDecodeError:
            latency_ms = (time.time() - start) * 1000
            return None, latency_ms
        except Exception:
            latency_ms = (time.time() - start) * 1000
            return None, latency_ms

    async def check_janus_health(self) -> bool:
        """Check Janus service health."""
        endpoint = "/health"
        url = f"{self.janus_url}{endpoint}"

        data, latency = self._http_get(url)
        success = data is not None and data.get("status") in ["healthy", "UP"]

        self.stats.record_api_call(f"janus{endpoint}", latency, success)
        self.stats.record_health_check(success, "janus")

        if success and data is not None and "signals_generated" in data:
            self.stats.record_signals(data["signals_generated"])

        if not success:
            self.stats.record_error(f"Janus health check failed: {data}")

        return success

    async def check_execution_health(self) -> bool:
        """Check Execution service health."""
        endpoint = "/health"
        url = f"{self.execution_url}{endpoint}"

        data, latency = self._http_get(url)
        success = data is not None and data.get("status") in ["healthy", "UP"]

        self.stats.record_api_call(f"execution{endpoint}", latency, success)
        self.stats.record_health_check(success, "execution")

        if not success:
            self.stats.record_error(f"Execution health check failed: {data}")

        return success

    async def check_questdb_health(self) -> bool:
        """Check QuestDB health."""
        endpoint = "/exec"
        url = f"{self.questdb_url}{endpoint}?query=SELECT%201"

        data, latency = self._http_get(url)
        success = data is not None

        self.stats.record_api_call(f"questdb{endpoint}", latency, success)
        self.stats.record_health_check(success, "questdb")

        if not success:
            self.stats.record_error("QuestDB health check failed")

        return success

    async def check_signal_generation(self) -> int:
        """Check signal generation from Janus."""
        endpoint = "/api/signals/latest"
        url = f"{self.janus_url}{endpoint}"

        data, latency = self._http_get(url)
        success = data is not None

        self.stats.record_api_call(f"janus{endpoint}", latency, success)

        if success and isinstance(data, dict):
            # Try to extract signal count from various possible response formats
            count = data.get("count", len(data.get("signals", [])))
            return count

        return 0

    def get_docker_stats(self) -> dict[str, float]:
        """Get memory usage from Docker stats."""
        try:
            result = subprocess.run(
                [
                    "docker",
                    "stats",
                    "--no-stream",
                    "--format",
                    "{{.Name}}\t{{.MemUsage}}",
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )

            memory_usage = {}
            for line in result.stdout.strip().split("\n"):
                if not line:
                    continue
                parts = line.split("\t")
                if len(parts) >= 2:
                    name = parts[0].replace("fks_", "")
                    mem_str = parts[1].split("/")[0].strip()
                    # Parse memory string (e.g., "123.4MiB" or "1.23GiB")
                    if "GiB" in mem_str:
                        mem_mb = float(mem_str.replace("GiB", "")) * 1024
                    elif "MiB" in mem_str:
                        mem_mb = float(mem_str.replace("MiB", ""))
                    elif "KiB" in mem_str:
                        mem_mb = float(mem_str.replace("KiB", "")) / 1024
                    else:
                        continue
                    memory_usage[name] = mem_mb

            return memory_usage
        except Exception as e:
            logger.debug(f"Failed to get Docker stats: {e}")
            return {}

    async def run_checks(self):
        """Run all health checks."""
        await self.check_janus_health()
        await self.check_execution_health()
        await self.check_questdb_health()
        await self.check_signal_generation()

        # Get Docker stats
        docker_stats = self.get_docker_stats()
        for service, memory in docker_stats.items():
            self.stats.record_memory(service, memory)


class SoakTest:
    """Manages the HTTP soak test."""

    def __init__(
        self,
        janus_url: str,
        execution_url: str,
        questdb_url: str,
        duration_hours: float,
        poll_interval: int,
        report_interval: int,
    ):
        self.duration_hours = duration_hours
        self.poll_interval = poll_interval
        self.report_interval = report_interval
        self.stats = Stats()
        self.monitor = ServiceMonitor(
            janus_url=janus_url,
            execution_url=execution_url,
            questdb_url=questdb_url,
            stats=self.stats,
        )
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
        logger.info("STARTING HTTP SOAK TEST")
        logger.info("=" * 80)
        logger.info(f"Janus URL: {self.monitor.janus_url}")
        logger.info(f"Execution URL: {self.monitor.execution_url}")
        logger.info(f"QuestDB URL: {self.monitor.questdb_url}")
        logger.info(f"Duration: {self.duration_hours} hours")
        logger.info(f"Poll Interval: {self.poll_interval} seconds")
        logger.info(f"Report Interval: {self.report_interval} seconds")
        logger.info(f"End Time: {datetime.fromtimestamp(end_time)}")
        logger.info("=" * 80)

        last_report_time = time.time()

        # Initial check
        logger.info("Running initial health checks...")
        await self.monitor.run_checks()
        self.stats.print_report()

        try:
            while self.running and time.time() < end_time:
                # Run health checks
                await self.monitor.run_checks()

                # Periodic report
                if time.time() - last_report_time >= self.report_interval:
                    self.stats.print_report()
                    last_report_time = time.time()

                # Wait for next poll
                await asyncio.sleep(self.poll_interval)

        except KeyboardInterrupt:
            logger.info("Interrupted by user")
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            self.stats.record_error(str(e))
        finally:
            self.running = False

        # Final report
        logger.info("\nFINAL REPORT:")
        self.stats.print_report()

        # Summary
        logger.info("\nTEST SUMMARY:")
        logger.info(f"Test completed: {datetime.now()}")
        logger.info(f"Total runtime: {str(timedelta(seconds=int(self.stats.get_uptime())))}")

        health_rate = self.stats.get_health_rate()
        if health_rate >= 99:
            logger.info("✅ Health check rate: EXCELLENT (≥99%)")
        elif health_rate >= 95:
            logger.info("✅ Health check rate: GOOD (≥95%)")
        elif health_rate >= 80:
            logger.warning("⚠️  Health check rate: FAIR (80-95%)")
        else:
            logger.error("❌ Health check rate: POOR (<80%)")

        if self.stats.signals_observed > 0:
            logger.info(f"✅ Signal generation: WORKING ({self.stats.signals_observed} signals)")
        else:
            logger.warning("⚠️  Signal generation: NO SIGNALS OBSERVED")

        # Check for any services that are down
        down_services = [s for s, up in self.stats.service_status.items() if not up]
        if down_services:
            logger.error(f"❌ Services DOWN: {', '.join(down_services)}")
        else:
            logger.info("✅ All services: UP")

        # Return exit code based on results
        if health_rate < 80 or len(down_services) > 0:
            return 1
        return 0


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="HTTP Soak Test - Test service stability over extended periods")
    parser.add_argument(
        "--janus-url",
        default=os.getenv("JANUS_URL", "http://localhost:7000"),
        help="Janus service URL (default: http://localhost:7000)",
    )
    parser.add_argument(
        "--execution-url",
        default=os.getenv("EXECUTION_URL", "http://localhost:7000"),
        help="Execution service URL (default: http://localhost:7000, embedded in Janus)",
    )
    parser.add_argument(
        "--questdb-url",
        default=os.getenv("QUESTDB_URL", "http://localhost:9000"),
        help="QuestDB URL (default: http://localhost:9000)",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=float(os.getenv("DURATION_HOURS", "48")),
        help="Test duration in hours (default: 48)",
    )
    parser.add_argument(
        "--poll-interval",
        type=int,
        default=int(os.getenv("POLL_INTERVAL", "30")),
        help="Polling interval in seconds (default: 30)",
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
        janus_url=args.janus_url,
        execution_url=args.execution_url,
        questdb_url=args.questdb_url,
        duration_hours=args.duration,
        poll_interval=args.poll_interval,
        report_interval=args.report_interval,
    )

    try:
        exit_code = asyncio.run(test.run())
        sys.exit(exit_code)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
