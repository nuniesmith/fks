#!/usr/bin/env python3
"""
lint_scan.py — Scan a directory for Rust (cargo clippy/check) and Python (ruff)
issues, deduplicate them, and write a Markdown report.

Usage:
    python lint_scan.py <target_dir> [--output report.md]
"""

import argparse
import json
import re
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


# ─────────────────────────────────────────────
#  Data model
# ─────────────────────────────────────────────

@dataclass(frozen=True)
class Issue:
    tool: str          # "clippy" | "cargo-check" | "ruff"
    level: str         # "error" | "warning" | "note" | "help"
    code: str          # e.g. "E501", "clippy::unwrap_used"
    message: str
    file: str
    line: int
    col: int

    # Dedup key — same tool + code + message + location
    def dedup_key(self) -> tuple:
        return (self.tool, self.code, self.message, self.file, self.line)


# ─────────────────────────────────────────────
#  Rust runner (cargo clippy + cargo check)
# ─────────────────────────────────────────────

def _find_cargo_workspaces(root: Path) -> list[Path]:
    """
    Return every directory that contains a Cargo.toml, skipping any that live
    inside a 'target' directory (which can contain nested Cargo.toml fixtures
    from build scripts and proc-macro crates).
    """
    results = []
    for p in root.rglob("Cargo.toml"):
        # Skip paths that pass through a 'target' directory
        if "target" in p.parts:
            continue
        results.append(p.parent)
    return results


def _run_cargo(workspace: Path, subcommand: str) -> str:
    """Run `cargo <subcommand>` and return combined stdout+stderr."""
    cmd = [
        "cargo", subcommand,
        "--message-format=json",
        "--all-targets",
        "--all-features",
        "--quiet",
    ]
    if subcommand == "clippy":
        cmd += ["--", "-W", "clippy::all"]

    try:
        result = subprocess.run(
            cmd,
            cwd=workspace,
            capture_output=True,
            text=True,
        )
        return result.stdout + result.stderr
    except FileNotFoundError:
        print("  [rust] cargo not found in PATH — install via https://rustup.rs")
        return ""


def _parse_cargo_json(raw: str, tool: str, workspace: Path) -> list[Issue]:
    issues: list[Issue] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line or not line.startswith("{"):
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue

        if obj.get("reason") != "compiler-message":
            continue

        msg = obj.get("message", {})
        level = msg.get("level", "")
        if level not in ("error", "warning", "note", "help"):
            continue

        text = msg.get("message", "").strip()
        code_obj = msg.get("code") or {}
        code = code_obj.get("code", "") if code_obj else ""

        spans = msg.get("spans", [])
        if spans:
            sp = spans[0]
            raw_file = sp.get("file_name", "")
            # Make path relative to workspace if possible
            abs_file = (workspace / raw_file).resolve()
            try:
                display_file = str(abs_file.relative_to(workspace.parent))
            except ValueError:
                display_file = raw_file
            line_no = sp.get("line_start", 0)
            col_no = sp.get("column_start", 0)
        else:
            display_file, line_no, col_no = "", 0, 0

        issues.append(Issue(
            tool=tool,
            level=level,
            code=code or "—",
            message=text,
            file=display_file,
            line=line_no,
            col=col_no,
        ))
    return issues


def collect_rust_issues(root: Path) -> list[Issue]:
    workspaces = _find_cargo_workspaces(root)
    if not workspaces:
        print("  [rust] No Cargo.toml found — skipping Rust linting.")
        return []

    issues: list[Issue] = []
    for ws in workspaces:
        print(f"  [rust] cargo clippy  →  {ws}")
        raw = _run_cargo(ws, "clippy")
        issues += _parse_cargo_json(raw, "clippy", ws)

        print(f"  [rust] cargo check   →  {ws}")
        raw = _run_cargo(ws, "check")
        issues += _parse_cargo_json(raw, "cargo-check", ws)

    return issues


# ─────────────────────────────────────────────
#  Ruff runner
# ─────────────────────────────────────────────

# Ruff rule prefixes whose violations are hard errors (syntax / import errors,
# undefined names, etc.).  Everything else is treated as a warning.
# See: https://docs.astral.sh/ruff/rules/
_RUFF_ERROR_PREFIXES = (
    "E9",   # Syntax errors (pycodestyle)
    "F401", # Unused imports that can cause runtime issues if re-exported
    "F811", # Redefinition of unused name
    "F821", # Undefined name
    "F841", # Local variable assigned but never used (keep as warning? subjective)
    "F901", # 'raise NotImplemented' — almost certainly wrong
)

def _ruff_level(code: str) -> str:
    """Map a ruff rule code to 'error' or 'warning'."""
    for prefix in _RUFF_ERROR_PREFIXES:
        if code.startswith(prefix):
            return "error"
    return "warning"


def collect_ruff_issues(root: Path) -> list[Issue]:
    # Check ruff is available
    try:
        probe = subprocess.run(["ruff", "--version"], capture_output=True, text=True)
        if probe.returncode != 0:
            raise FileNotFoundError
    except FileNotFoundError:
        print("  [ruff] ruff not found in PATH — skipping Python linting.")
        print("         Install with: pip install ruff  or  cargo install ruff")
        return []

    print(f"  [ruff] ruff check    →  {root}")
    result = subprocess.run(
        ["ruff", "check", "--output-format=json", str(root)],
        capture_output=True,
        text=True,
    )

    raw = result.stdout.strip()
    if not raw:
        return []

    try:
        entries = json.loads(raw)
    except json.JSONDecodeError:
        print("  [ruff] Could not parse ruff JSON output.")
        return []

    issues: list[Issue] = []
    for e in entries:
        loc = e.get("location", {})
        code = e.get("code", "—")
        issues.append(Issue(
            tool="ruff",
            level=_ruff_level(code),
            code=code,
            message=e.get("message", "").strip(),
            file=e.get("filename", ""),
            line=loc.get("row", 0),
            col=loc.get("column", 0),
        ))
    return issues


# ─────────────────────────────────────────────
#  Deduplication
# ─────────────────────────────────────────────

def deduplicate(issues: list[Issue]) -> tuple[list[Issue], list[dict]]:
    """
    Returns (unique_issues, duplicate_groups).
    duplicate_groups: list of {"key": ..., "count": N, "occurrences": [...]}
    """
    seen: dict[tuple, list[Issue]] = defaultdict(list)
    for issue in issues:
        seen[issue.dedup_key()].append(issue)

    unique = [v[0] for v in seen.values()]
    dups = [
        {"key": k, "count": len(v), "sample": v[0]}
        for k, v in seen.items()
        if len(v) > 1
    ]
    return unique, dups


# ─────────────────────────────────────────────
#  Markdown report
# ─────────────────────────────────────────────

SEVERITY_ORDER = {"error": 0, "warning": 1, "note": 2, "help": 3}
SEVERITY_EMOJI = {"error": "🔴", "warning": "🟡", "note": "🔵", "help": "⚪"}


def _level_badge(level: str) -> str:
    emoji = SEVERITY_EMOJI.get(level, "⚪")
    return f"{emoji} **{level.upper()}**"


def build_report(
    root: Path,
    all_issues: list[Issue],
    unique_issues: list[Issue],
    dup_groups: list[dict],
    output_path: Path,
) -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Group unique issues by tool → level
    by_tool: dict[str, list[Issue]] = defaultdict(list)
    for issue in unique_issues:
        by_tool[issue.tool].append(issue)

    error_count = sum(1 for i in unique_issues if i.level == "error")
    warn_count  = sum(1 for i in unique_issues if i.level == "warning")
    dup_count   = sum(d["count"] - 1 for d in dup_groups)

    lines: list[str] = []

    # ── Header ──
    lines += [
        f"# 🔍 Lint Report",
        f"",
        f"> **Scanned:** `{root.resolve()}`  ",
        f"> **Generated:** {now}  ",
        f"> **Total unique issues:** {len(unique_issues)}  ",
        f"> **Errors:** {error_count} · **Warnings:** {warn_count} · **Duplicates removed:** {dup_count}",
        f"",
    ]

    # ── Summary table ──
    lines += [
        "## Summary",
        "",
        "| Tool | Errors | Warnings | Notes/Help | Total |",
        "|------|-------:|---------:|-----------:|------:|",
    ]
    for tool in sorted(by_tool):
        tool_issues = by_tool[tool]
        e = sum(1 for i in tool_issues if i.level == "error")
        w = sum(1 for i in tool_issues if i.level == "warning")
        n = sum(1 for i in tool_issues if i.level in ("note", "help"))
        lines.append(f"| `{tool}` | {e} | {w} | {n} | {len(tool_issues)} |")
    lines += ["", "---", ""]

    # ── Per-tool sections ──
    for tool in sorted(by_tool):
        tool_issues = sorted(
            by_tool[tool],
            key=lambda i: (SEVERITY_ORDER.get(i.level, 9), i.file, i.line),
        )
        lines += [f"## 🛠 `{tool}`", ""]

        for issue in tool_issues:
            badge = _level_badge(issue.level)
            loc = f"`{issue.file}:{issue.line}:{issue.col}`" if issue.file else "_(unknown location)_"
            code_str = f"`{issue.code}`" if issue.code and issue.code != "—" else "—"

            lines += [
                f"### {badge} — {issue.message}",
                f"",
                f"| Field | Value |",
                f"|-------|-------|",
                f"| **Code** | {code_str} |",
                f"| **Location** | {loc} |",
                f"",
            ]

        lines += ["---", ""]

    # ── Duplicates section ──
    if dup_groups:
        lines += ["## ♻️ Duplicate Issues (collapsed)", ""]
        lines += [
            "These issues appeared more than once and were deduplicated in the sections above.",
            "",
            "| Count | Tool | Code | Message | First seen |",
            "|------:|------|------|---------|------------|",
        ]
        for d in sorted(dup_groups, key=lambda x: -x["count"]):
            s = d["sample"]
            loc = f"`{s.file}:{s.line}`" if s.file else "—"
            msg = s.message[:60] + ("…" if len(s.message) > 60 else "")
            lines.append(
                f"| {d['count']} | `{s.tool}` | `{s.code}` | {msg} | {loc} |"
            )
        lines += ["", "---", ""]

    # ── Footer ──
    lines += [
        "_Report generated by `lint_scan.py`_",
    ]

    output_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n✅ Report written → {output_path.resolve()}")


# ─────────────────────────────────────────────
#  Entry point
# ─────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scan a directory with Rust (cargo clippy/check) + Python (ruff) and emit a Markdown report."
    )
    parser.add_argument("target_dir", type=Path, help="Directory to scan")
    parser.add_argument(
        "--output", "-o",
        type=Path,
        default=Path("lint_report.md"),
        help="Output Markdown file (default: lint_report.md)",
    )
    parser.add_argument(
        "--skip-rust", action="store_true", help="Skip Rust linting"
    )
    parser.add_argument(
        "--skip-python", action="store_true", help="Skip Python / ruff linting"
    )
    args = parser.parse_args()

    root = args.target_dir.resolve()
    if not root.exists():
        sys.exit(f"Error: directory not found: {root}")

    print(f"\n🔍 Scanning: {root}\n")

    all_issues: list[Issue] = []

    if not args.skip_rust:
        all_issues += collect_rust_issues(root)

    if not args.skip_python:
        all_issues += collect_ruff_issues(root)

    unique_issues, dup_groups = deduplicate(all_issues)

    print(f"\n📊 Found {len(all_issues)} raw issues → {len(unique_issues)} unique "
          f"({sum(d['count']-1 for d in dup_groups)} duplicates removed)")

    build_report(root, all_issues, unique_issues, dup_groups, args.output)


if __name__ == "__main__":
    main()
