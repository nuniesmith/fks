#!/usr/bin/env python3
"""
Update Project Health Dashboard with latest metrics.
Run this after analyze_project.py to refresh the dashboard.
"""

import json
import re
from datetime import datetime
from pathlib import Path


def load_metrics() -> dict:
    """Load metrics from metrics.json."""
    metrics_file = Path(__file__).parent.parent / "metrics.json"
    if not metrics_file.exists():
        print("❌ metrics.json not found. Run analyze_project.py first.")
        return {}
    return json.loads(metrics_file.read_text())


def generate_summary(metrics: dict) -> str:
    """Generate executive summary based on metrics."""
    if not metrics:
        return "No metrics available. Run analysis first."

    files = metrics.get('files', {})
    tests = metrics.get('tests', {})
    imports = metrics.get('imports', {})
    debt = metrics.get('technical_debt', {})

    summary = []

    # Test status
    total_tests = tests.get('tests_total', 0)
    passing_tests = tests.get('tests_passed', 0)
    if total_tests > 0:
        test_rate = (passing_tests / total_tests) * 100
        if test_rate < 80:
            summary.append(f"⚠️  Test coverage is low ({test_rate:.1f}%)")
        else:
            summary.append(f"✅ Tests are healthy ({test_rate:.1f}% passing)")

    # Legacy imports
    legacy_files = imports.get('files_with_legacy', 0)
    if legacy_files > 0:
        summary.append(f"🚨 {legacy_files} files have legacy imports that need migration")

    # Empty files
    empty_files = files.get('empty_files', 0)
    if empty_files > 0:
        summary.append(f"🧹 {empty_files} empty files should be cleaned up")

    # Technical debt
    debt_markers = debt.get('total_debt_comments', 0)
    if debt_markers > 10:
        summary.append(f"💸 High technical debt ({debt_markers} markers)")

    if not summary:
        summary.append("✅ Project is in good health")

    return " | ".join(summary)


def generate_recommendations(metrics: dict) -> str:
    """Generate priority recommendations based on metrics."""
    recommendations = []

    tests = metrics.get('tests', {})
    imports = metrics.get('imports', {})
    files = metrics.get('files', {})

    failing_tests = tests.get('tests_total', 0) - tests.get('tests_passed', 0)
    if failing_tests > 0:
        recommendations.append(f"- **CRITICAL**: Fix {failing_tests} failing tests")

    legacy_files = imports.get('files_with_legacy', 0)
    if legacy_files > 0:
        recommendations.append(f"- **HIGH**: Migrate {legacy_files} files with legacy imports")

    empty_files = files.get('empty_files', 0)
    if empty_files > 5:
        recommendations.append(f"- **MEDIUM**: Clean up {empty_files} empty files")

    if not recommendations:
        recommendations.append("- **LOW**: Maintain current standards")

    return "\n".join(recommendations)


def update_dashboard():
    """Update the dashboard markdown file."""
    metrics = load_metrics()
    if not metrics:
        return

    dashboard_file = Path(__file__).parent.parent / "docs" / "PROJECT_HEALTH_DASHBOARD.md"

    if not dashboard_file.exists():
        print("❌ Dashboard file not found")
        return

    content = dashboard_file.read_text()

    # Update timestamp
    content = re.sub(
        r'\*Last updated: \[TIMESTAMP\]\*',
        f'*Last updated: {datetime.now().strftime("%Y-%m-%d %H:%M")}*',
        content
    )

    # Update summary
    summary = generate_summary(metrics)
    content = re.sub(
        r'\[Auto-generated summary based on metrics\]',
        summary,
        content
    )

    # Update metrics
    files = metrics.get('files', {})
    content = content.replace('[TOTAL_FILES]', str(files.get('total', 0)))
    content = content.replace('[SOURCE_FILES]', str(files.get('source_files', 0)))
    content = content.replace('[TEST_FILES]', str(files.get('test_files', 0)))
    content = content.replace('[EMPTY_FILES]', str(files.get('empty_files', 0)))

    code = metrics.get('code', {})
    content = content.replace('[LOC]', str(code.get('total_lines', 0)))
    content = content.replace('[COVERAGE]', str(code.get('coverage_percent', 0)))
    content = content.replace('[LEGACY_IMPORTS]', str(metrics.get('imports', {}).get('files_with_legacy', 0)))
    content = content.replace('[DEBT_MARKERS]', str(metrics.get('technical_debt', {}).get('total_debt_comments', 0)))

    tests = metrics.get('tests', {})
    content = content.replace('[TOTAL_TESTS]', str(tests.get('tests_total', 0)))
    content = content.replace('[PASSING_TESTS]', str(tests.get('tests_passed', 0)))
    content = content.replace('[FAILING_TESTS]', str(tests.get('tests_total', 0) - tests.get('tests_passed', 0)))

    git = metrics.get('git', {})
    content = content.replace('[UNCOMMITTED]', str(git.get('uncommitted_changes', 0)))
    content = content.replace('[LAST_COMMIT]', git.get('last_commit_date', 'Unknown'))

    # Update recommendations
    recommendations = generate_recommendations(metrics)
    content = re.sub(
        r'\[Auto-generated recommendations\]',
        recommendations,
        content
    )

    # Write back
    dashboard_file.write_text(content)
    print(f"✅ Dashboard updated: {dashboard_file}")


if __name__ == "__main__":
    update_dashboard()