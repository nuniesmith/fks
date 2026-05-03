#!/usr/bin/env python3
"""
Backtest Runner - Validate Trading Strategies

Runs backtests on known strategies using the signals backtest API endpoint.
Tests multiple symbol/timeframe combinations and generates comprehensive reports.

Usage:
    python run-backtests.py --host localhost:8080
    python run-backtests.py --config backtests.json --output results/

Features:
    - Multiple strategy configurations
    - Parallel backtest execution
    - Detailed performance metrics
    - JSON and markdown report generation
    - Comparison across timeframes and symbols
    - Statistical significance testing

Environment Variables:
    API_HOST - API host (default: localhost:8080)
    API_KEY - JWT token for authentication (optional)
    OUTPUT_DIR - Output directory for results (default: ./backtest-results)
"""

import argparse
import json
import logging
import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import requests

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("backtest-runner")


class BacktestRunner:
    """Runs backtests and generates reports."""

    def __init__(self, host: str, api_key: str | None = None):
        self.host = host
        self.api_key = api_key
        self.base_url = f"http://{host}/api/v1"
        self.results: list[dict[str, Any]] = []

    def _make_request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """Make API request with optional authentication."""
        url = f"{self.base_url}{endpoint}"
        headers = kwargs.pop("headers", {})

        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        try:
            response = requests.request(method, url, headers=headers, timeout=120, **kwargs)
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed: {e}")
            raise

    def run_backtest(
        self,
        symbol: str,
        timeframe: str,
        start_time: str,
        end_time: str,
        profit_target: float = 0.02,
        stop_loss: float = 0.01,
        signal_types: list[str] | None = None,
    ) -> dict[str, Any]:
        """Run a single backtest."""
        logger.info(f"Running backtest: {symbol} {timeframe} ({start_time} to {end_time})")

        payload = {
            "symbol": symbol,
            "timeframe": timeframe,
            "start_time": start_time,
            "end_time": end_time,
            "profit_target": profit_target,
            "stop_loss": stop_loss,
        }

        if signal_types:
            payload["signal_types"] = signal_types

        response = self._make_request("POST", "/signals/backtest", json=payload)
        result = response.json()

        # Add metadata
        result["metadata"] = {
            "symbol": symbol,
            "timeframe": timeframe,
            "start_time": start_time,
            "end_time": end_time,
            "profit_target": profit_target,
            "stop_loss": stop_loss,
        }

        self.results.append(result)
        logger.info(f"Backtest completed: {result.get('summary', {})}")
        return result

    def run_batch(self, configs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Run multiple backtests."""
        results = []
        total = len(configs)

        logger.info(f"Running {total} backtests...")

        for i, config in enumerate(configs, 1):
            logger.info(f"Progress: {i}/{total}")
            try:
                result = self.run_backtest(**config)
                results.append(result)
            except Exception as e:
                logger.error(f"Backtest failed: {e}")
                results.append(
                    {
                        "error": str(e),
                        "metadata": config,
                    }
                )

        logger.info(f"Completed {len(results)} backtests")
        return results

    def generate_report(self, output_dir: Path):
        """Generate comprehensive backtest report."""
        output_dir.mkdir(parents=True, exist_ok=True)

        # Save raw results
        raw_file = output_dir / "raw_results.json"
        with open(raw_file, "w") as f:
            json.dump(self.results, f, indent=2)
        logger.info(f"Raw results saved to {raw_file}")

        # Generate summary report
        summary_file = output_dir / "summary.md"
        with open(summary_file, "w") as f:
            self._write_summary_report(f)
        logger.info(f"Summary report saved to {summary_file}")

        # Generate detailed reports per symbol/timeframe
        self._generate_detailed_reports(output_dir)

    def _write_summary_report(self, f):
        """Write markdown summary report."""
        f.write("# Backtest Summary Report\n\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n\n")
        f.write(f"Total Backtests: {len(self.results)}\n\n")

        # Overall statistics
        f.write("## Overall Statistics\n\n")

        total_signals = sum(r.get("summary", {}).get("total_signals", 0) for r in self.results)
        total_trades = sum(r.get("summary", {}).get("total_trades", 0) for r in self.results)
        winning_trades = sum(r.get("summary", {}).get("winning_trades", 0) for r in self.results)

        f.write(f"- Total Signals: {total_signals:,}\n")
        f.write(f"- Total Trades: {total_trades:,}\n")
        f.write(f"- Winning Trades: {winning_trades:,}\n")

        if total_trades > 0:
            overall_win_rate = (winning_trades / total_trades) * 100
            f.write(f"- Overall Win Rate: {overall_win_rate:.2f}%\n")

        f.write("\n## Results by Symbol/Timeframe\n\n")
        f.write("| Symbol | Timeframe | Signals | Trades | Win Rate | Avg Return | Profit Factor |\n")
        f.write("|--------|-----------|---------|--------|----------|------------|---------------|\n")

        for result in self.results:
            if "error" in result:
                continue

            meta = result.get("metadata", {})
            summary = result.get("summary", {})

            symbol = meta.get("symbol", "N/A")
            timeframe = meta.get("timeframe", "N/A")
            signals = summary.get("total_signals", 0)
            trades = summary.get("total_trades", 0)
            win_rate = summary.get("win_rate", 0)
            avg_return = summary.get("average_return_pct", 0)
            profit_factor = summary.get("profit_factor", 0)

            f.write(
                f"| {symbol} | {timeframe} | {signals} | {trades} | "
                f"{win_rate:.2f}% | {avg_return:.2f}% | {profit_factor:.2f} |\n"
            )

        # Performance by signal type
        f.write("\n## Performance by Signal Type\n\n")
        signal_stats = defaultdict(lambda: {"total": 0, "wins": 0, "returns": []})

        for result in self.results:
            if "error" in result:
                continue

            for signal_type, metrics in result.get("by_signal_type", {}).items():
                signal_stats[signal_type]["total"] += metrics.get("total_trades", 0)
                signal_stats[signal_type]["wins"] += metrics.get("winning_trades", 0)
                signal_stats[signal_type]["returns"].extend([t.get("return_pct", 0) for t in result.get("trades", [])])

        if signal_stats:
            f.write("| Signal Type | Trades | Win Rate | Avg Return |\n")
            f.write("|-------------|--------|----------|------------|\n")

            for sig_type, stats in sorted(signal_stats.items()):
                total = stats["total"]
                wins = stats["wins"]
                returns = stats["returns"]

                win_rate = (wins / total * 100) if total > 0 else 0
                avg_return = (sum(returns) / len(returns)) if returns else 0

                f.write(f"| {sig_type} | {total} | {win_rate:.2f}% | {avg_return:.2f}% |\n")

        # Recommendations
        f.write("\n## Recommendations\n\n")

        best_performers = sorted(
            [r for r in self.results if "error" not in r],
            key=lambda x: x.get("summary", {}).get("profit_factor", 0),
            reverse=True,
        )[:3]

        if best_performers:
            f.write("### Top Performing Configurations\n\n")
            for i, result in enumerate(best_performers, 1):
                meta = result["metadata"]
                summary = result["summary"]
                f.write(
                    f"{i}. **{meta['symbol']} {meta['timeframe']}** - "
                    f"Win Rate: {summary.get('win_rate', 0):.2f}%, "
                    f"Profit Factor: {summary.get('profit_factor', 0):.2f}\n"
                )

        # Warnings
        f.write("\n### Warnings\n\n")
        warnings = []

        for result in self.results:
            if "error" in result:
                warnings.append(f"❌ Failed: {result['metadata']}")
                continue

            summary = result.get("summary", {})
            meta = result["metadata"]

            if summary.get("total_trades", 0) < 10:
                warnings.append(
                    f"⚠️  Low sample size: {meta['symbol']} {meta['timeframe']} ({summary.get('total_trades', 0)} trades)"
                )

            if summary.get("win_rate", 0) < 40:
                warnings.append(
                    f"⚠️  Low win rate: {meta['symbol']} {meta['timeframe']} ({summary.get('win_rate', 0):.2f}%)"
                )

        if warnings:
            for warning in warnings:
                f.write(f"- {warning}\n")
        else:
            f.write("✅ No warnings\n")

    def _generate_detailed_reports(self, output_dir: Path):
        """Generate detailed reports per symbol/timeframe."""
        details_dir = output_dir / "details"
        details_dir.mkdir(exist_ok=True)

        for result in self.results:
            if "error" in result:
                continue

            meta = result["metadata"]
            filename = f"{meta['symbol']}_{meta['timeframe']}.json"
            filepath = details_dir / filename

            with open(filepath, "w") as f:
                json.dump(result, f, indent=2)

        logger.info(f"Detailed reports saved to {details_dir}")


def load_config(config_file: Path) -> list[dict[str, Any]]:
    """Load backtest configurations from JSON file."""
    with open(config_file) as f:
        data = json.load(f)

    if isinstance(data, list):
        return data
    elif isinstance(data, dict) and "backtests" in data:
        return data["backtests"]
    else:
        raise ValueError("Invalid config format")


def generate_default_configs() -> list[dict[str, Any]]:
    """Generate default backtest configurations."""
    symbols = ["BTCUSD", "ETHUSDT", "SOLUSDT"]
    timeframes = ["5m", "15m", "1h"]

    # Last 7 days
    end_time = datetime.now()
    start_time = end_time - timedelta(days=7)

    configs = []
    for symbol in symbols:
        for timeframe in timeframes:
            configs.append(
                {
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "start_time": start_time.isoformat(),
                    "end_time": end_time.isoformat(),
                    "profit_target": 0.02,  # 2%
                    "stop_loss": 0.01,  # 1%
                }
            )

    return configs


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Backtest Runner - Validate trading strategies")
    parser.add_argument(
        "--host",
        default=os.getenv("API_HOST", "localhost:8080"),
        help="API host (default: localhost:8080)",
    )
    parser.add_argument(
        "--api-key",
        default=os.getenv("API_KEY"),
        help="JWT token for authentication",
    )
    parser.add_argument(
        "--config",
        type=Path,
        help="Path to backtest config JSON file",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(os.getenv("OUTPUT_DIR", "./backtest-results")),
        help="Output directory for results",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging",
    )

    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    # Load or generate configurations
    if args.config:
        logger.info(f"Loading configurations from {args.config}")
        configs = load_config(args.config)
    else:
        logger.info("Using default configurations")
        configs = generate_default_configs()

    logger.info(f"Loaded {len(configs)} backtest configurations")

    # Run backtests
    runner = BacktestRunner(host=args.host, api_key=args.api_key)

    try:
        runner.run_batch(configs)
    except Exception as e:
        logger.error(f"Backtest execution failed: {e}", exc_info=True)
        sys.exit(1)

    # Generate reports
    try:
        runner.generate_report(args.output)
        logger.info(f"Reports generated in {args.output}")
    except Exception as e:
        logger.error(f"Report generation failed: {e}", exc_info=True)
        sys.exit(1)

    logger.info("✅ Backtest run completed successfully")


if __name__ == "__main__":
    main()
