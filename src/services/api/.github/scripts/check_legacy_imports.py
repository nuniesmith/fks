#!/usr/bin/env python
"""Fail if deprecated 'shared_python' imports appear outside allowed wrapper directory or tests.

Exit codes:
 0 - no violations
 1 - violations found
"""
from __future__ import annotations
import pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
ALLOWED = ROOT / 'shared' / 'shared_python'
PATTERN = re.compile(r'^\s*(from|import)\s+shared_python(\.|\s|$)')

violations: list[str] = []
for py in ROOT.rglob('*.py'):
    if ALLOWED in py.parents:
        continue
    name_lower = py.name.lower()
    if 'test' in name_lower:
        continue
    try:
        text = py.read_text(encoding='utf-8', errors='ignore')
    except Exception:
        continue
    for i, line in enumerate(text.splitlines(), 1):
        if PATTERN.search(line):
            violations.append(f"{py.relative_to(ROOT)}:{i}:{line.strip()}")

if violations:
    print('Legacy shared_python imports detected:')
    for v in violations:
        print('  ' + v)
    sys.exit(1)
print('No legacy shared_python imports.')
