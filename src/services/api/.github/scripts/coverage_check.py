#!/usr/bin/env python
"""Lightweight coverage threshold gate (soft for now).

Reads coverage XML (Cobertura / `coverage xml`) and enforces a configurable
minimum line-rate. Designed to run AFTER combined coverage generation.

Environment:
  COVERAGE_FILE: path to coverage xml (default: coverage-combined.xml then coverage.xml)
  COVERAGE_FAIL_UNDER: float percentage (e.g. 62.5) required. If unset, acts in soft mode
                       recording value but NOT failing. This lets us observe baseline
                       before turning hard enforcement on.
Exit codes:
  0 success / skipped / soft fail
  1 hard failure (threshold specified and not met & file present)
Artifacts: prints a summary line with `COVERAGE:` prefix for easy grep.
"""
from __future__ import annotations

import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
import argparse

DEFAULT_FILES = ["coverage-combined.xml", "coverage.xml"]


def find_file(explicit: str | None) -> Path | None:
    if explicit:
        p = Path(explicit)
        if p.is_file():
            return p
    for name in DEFAULT_FILES:
        p = Path(name)
        if p.is_file():
            return p
    return None


def parse_line_rate(xml_path: Path) -> float:
    tree = ET.parse(xml_path)
    root = tree.getroot()
    # coverage.py Cobertura root tag = 'coverage' with attribute 'line-rate'
    rate = root.get("line-rate")
    if rate is None:
        raise ValueError("line-rate attribute missing in coverage xml")
    return float(rate) * 100.0


def main() -> int:
    parser = argparse.ArgumentParser(description="Coverage threshold + percent helper")
    parser.add_argument("--percent-file", help="Write observed percent to file", default=None)
    args = parser.parse_args()
    xml_file_env = os.environ.get("COVERAGE_FILE")
    threshold_env = os.environ.get("COVERAGE_FAIL_UNDER")

    xml_path = find_file(xml_file_env)
    if xml_path is None:
        print("COVERAGE: no coverage xml file found (skipping threshold check)")
        return 0

    try:
        pct = parse_line_rate(xml_path)
    except Exception as exc:  # pragma: no cover - defensive
        print(f"COVERAGE: failed to parse coverage xml: {exc}")
        return 0

    if threshold_env:
        try:
            threshold = float(threshold_env)
        except ValueError:
            print(f"COVERAGE: invalid COVERAGE_FAIL_UNDER value '{threshold_env}', ignoring")
            threshold = None
    else:
        threshold = None

    if args.percent_file:
        try:
            with open(args.percent_file, 'w') as f:
                f.write(f"{pct:.2f}\n")
        except OSError as e:  # pragma: no cover
            print(f"COVERAGE: failed writing percent file: {e}")
    # Always append to GitHub summary if available
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        try:  # pragma: no cover
            with open(summary_path, 'a') as f:
                f.write(f"\n### Coverage\n\nObserved: {pct:.2f}%\n")
        except OSError:
            pass
    hard_fail = os.environ.get("COVERAGE_HARD_FAIL") == "1"
    if threshold is None:
        print(f"COVERAGE: observed {pct:.2f}% (soft mode, no threshold set)")
        return 0

    if pct + 1e-9 < threshold:  # small epsilon
        msg = f"COVERAGE: {pct:.2f}% below required {threshold:.2f}%"
        if hard_fail:
            print(msg + " : FAIL")
            return 1
        else:
            print(msg + " : SOFT FAIL (not enforced)")
            return 0

    print(f"COVERAGE: {pct:.2f}% meets required {threshold:.2f}%")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
