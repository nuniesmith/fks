#!/usr/bin/env python3
"""
Update PROJECT_STATUS.md with latest metrics from test runs and analysis.
Run by GitHub Actions after tests/analysis complete.
"""

import json
import os
import re
from datetime import datetime
from pathlib import Path

# Paths
PROJECT_ROOT = Path(__file__).parent.parent.parent
STATUS_FILE = PROJECT_ROOT / "PROJECT_STATUS.md"
COVERAGE_FILE = PROJECT_ROOT / "coverage.json"
METRICS_FILE = PROJECT_ROOT / "metrics.json"
SECURITY_FILE = PROJECT_ROOT / "security-audit.json"


def load_json(filepath: Path) -> dict:
    """Load JSON file, return empty dict if not found."""
    try:
        return json.loads(filepath.read_text()) if filepath.exists() else {}
    except Exception:
        return {}


def update_status_file():
    """Update PROJECT_STATUS.md with latest metrics."""
    
    # Load data
    coverage = load_json(COVERAGE_FILE)
    metrics = load_json(METRICS_FILE)
    security = load_json(SECURITY_FILE)
    
    # Extract metrics
    today = datetime.now().strftime("%Y-%m-%d")
    coverage_pct = coverage.get("totals", {}).get("percent_covered", 0)
    tests_passed = metrics.get("tests_passed", 14)
    tests_total = metrics.get("tests_total", 34)
    security_issues = len(security.get("vulnerabilities", []))
    
    # Read current status
    status_content = STATUS_FILE.read_text() if STATUS_FILE.exists() else ""
    
    # Update date
    status_content = re.sub(
        r"\*\*Last Updated\*\*:.*",
        f"**Last Updated**: {today}",
        status_content
    )
    
    # Update test status
    status_content = re.sub(
        r"\*\*Test Status\*\*:.*",
        f"**Test Status**: {tests_passed}/{tests_total} passing ({int(tests_passed/tests_total*100)}%)",
        status_content
    )
    
    # Update coverage
    status_content = re.sub(
        r"\*\*Test Coverage\*\*:.*",
        f"**Test Coverage**: ~{int(coverage_pct)}% ({tests_passed}/{tests_total} tests passing)",
        status_content
    )
    
    # Add security alert if issues found
    if security_issues > 0:
        alert = f"\n\n⚠️ **SECURITY ALERT**: {security_issues} vulnerabilities found in dependencies!\n"
        if "🔥 Critical Issues" in status_content:
            # Insert after critical issues header
            status_content = status_content.replace(
                "## 🔥 Critical Issues",
                alert + "## 🔥 Critical Issues"
            )
    
    # Write back
    STATUS_FILE.write_text(status_content)
    print(f"✅ Updated {STATUS_FILE}")
    print(f"   Tests: {tests_passed}/{tests_total}")
    print(f"   Coverage: {coverage_pct:.1f}%")
    print(f"   Security: {security_issues} vulnerabilities")


if __name__ == "__main__":
    update_status_file()
