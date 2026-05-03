"""
ml/reporting.py — Terminal reporting helpers for the CNN training pipeline.

Covers:
  - ANSI colour constants (TTY-safe)
  - _load_existing_meta    : read the sidecar JSON for a saved model
  - _print_champion_comparison : old vs new metric table
  - _print_cross_tier_summary  : end-of-run summary table across all assets
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

# ── Terminal colours ──────────────────────────────────────────────────────────
_IS_TTY = hasattr(sys.stdout, "isatty") and sys.stdout.isatty()
BOLD   = "\033[1m"  if _IS_TTY else ""
GREEN  = "\033[92m" if _IS_TTY else ""
YELLOW = "\033[93m" if _IS_TTY else ""
RED    = "\033[91m" if _IS_TTY else ""
CYAN   = "\033[96m" if _IS_TTY else ""
DIM    = "\033[2m"  if _IS_TTY else ""
RESET  = "\033[0m"  if _IS_TTY else ""


# ── Sidecar JSON helpers ──────────────────────────────────────────────────────

def load_existing_meta(model_path: Path) -> dict[str, Any] | None:
    """Return the sidecar JSON dict for *model_path*, or None if absent/corrupt."""
    sidecar = model_path.with_suffix(".json")
    if not sidecar.exists():
        return None
    try:
        return json.loads(sidecar.read_text())
    except Exception:
        return None


# ── Formatting utilities ──────────────────────────────────────────────────────

def _pct_raw(v: float | None) -> float | None:
    """Normalise a 0-1 fraction or a 0-100 percentage to percentage float."""
    if v is None:
        return None
    return v * 100.0 if v <= 1.0 else v


def _fmt_metric(val: float | None) -> str:
    if val is None:
        return "—"
    pct = val * 100.0 if val <= 1.0 else val
    return f"{pct:.1f}%"


def _color_acc(val: float | None) -> str:
    if val is None:
        return DIM
    pct = val * 100.0 if val <= 1.0 else val
    if pct >= 65:
        return GREEN
    if pct >= 55:
        return YELLOW
    return RED


# ── Champion comparison ───────────────────────────────────────────────────────

def print_champion_comparison(
    label: str,
    old: dict[str, Any],
    new: dict[str, Any],
) -> None:
    """Print an old-vs-new metric table for a single asset or master model."""
    print()
    print(f"{BOLD}  ── Champion Comparison: {label} ──{RESET}")
    old_date = str(old.get("trained_at", "unknown"))[:19]
    print(f"{DIM}  Previous champion trained: {old_date}{RESET}")
    print()

    header = (
        f"  {BOLD}"
        f"{'Metric':<18} {'Previous':>12} {'New':>12} {'Delta':>12}"
        f"{RESET}"
    )
    sep = f"  {'─' * 18} {'─' * 12} {'─' * 12} {'─' * 12}"
    print(header)
    print(f"{DIM}{sep}{RESET}")

    metrics: list[tuple[str, float | None, float | None]] = []
    metrics.append(("Val Accuracy", _pct_raw(old.get("val_accuracy")), _pct_raw(new.get("val_accuracy"))))

    if "best_val_loss" in old or "best_val_loss" in new:
        metrics.append(("Val Loss", old.get("best_val_loss"), new.get("best_val_loss")))

    old_pc = old.get("per_class", {})
    new_pc = new.get("per_class", {})
    for cls_name in ("long", "short"):
        if cls_name in new_pc or cls_name in old_pc:
            for mk in ("precision", "recall", "f1"):
                metrics.append((
                    f"{cls_name.capitalize()} {mk.upper()}",
                    _pct_raw((old_pc.get(cls_name) or {}).get(mk)),
                    _pct_raw((new_pc.get(cls_name) or {}).get(mk)),
                ))

    for metric_name, old_val, new_val in metrics:
        old_str = f"{old_val:.1f}%" if old_val is not None else "—"
        new_str = f"{new_val:.1f}%" if new_val is not None else "—"

        if old_val is not None and new_val is not None:
            is_loss = "loss" in metric_name.lower()
            delta = new_val - old_val
            delta_sign = -delta if is_loss else delta

            if abs(delta) < 0.05:
                color = DIM
                delta_str = "—"
            elif delta_sign > 0:
                color = GREEN
                delta_str = f"+{delta:.1f}%"
            else:
                color = RED
                delta_str = f"{delta:.1f}%"

            if is_loss:
                old_str = f"{old_val:.4f}"
                new_str = f"{new_val:.4f}"
                delta_str = f"{delta:+.4f}" if abs(delta) >= 0.0001 else "—"
        else:
            color = DIM
            delta_str = "—"

        print(f"  {metric_name:<18} {old_str:>12} {new_str:>12} {color}{delta_str:>12}{RESET}")

    print(f"{DIM}{sep}{RESET}")

    old_acc = _pct_raw(old.get("val_accuracy"))
    new_acc = _pct_raw(new.get("val_accuracy"))
    if old_acc is not None and new_acc is not None:
        diff = new_acc - old_acc
        if diff > 0.5:
            print(f"  {GREEN}▲ New model improves accuracy by {diff:+.1f}%{RESET}")
        elif diff < -0.5:
            print(f"  {RED}▼ New model accuracy dropped by {abs(diff):.1f}%{RESET}")
        else:
            print(f"  {DIM}≈ Accuracy unchanged{RESET}")
    print()


# ── Cross-tier summary ────────────────────────────────────────────────────────

def print_cross_tier_summary(results: list[dict[str, Any]]) -> None:
    """Print the end-of-run table covering all per-asset and master results."""
    asset_results = [
        r for r in results
        if r.get("saved") and r.get("asset") and r.get("type") != "master"
    ]
    master_results  = [r for r in results if r.get("type") == "master" and r.get("saved")]
    skipped_results = [
        r for r in results
        if not r.get("saved") and not r.get("dry_run") and r.get("type") != "master"
    ]

    if not asset_results and not master_results:
        return

    print()
    print(f"{BOLD}{'━' * 80}{RESET}")
    print(f"{BOLD}  Cross-Tier Training Summary{RESET}")
    print(f"{BOLD}{'━' * 80}{RESET}")
    print()

    C = dict(ASSET=12, TIER=10, ACC=10, LP=10, LR=10, SP=10, SR=10, EPOCH=8)

    header = (
        f"  {BOLD}"
        f"{'Asset':<{C['ASSET']}} "
        f"{'Tier':<{C['TIER']}} "
        f"{'Val Acc':>{C['ACC']}} "
        f"{'Long P':>{C['LP']}} "
        f"{'Long R':>{C['LR']}} "
        f"{'Short P':>{C['SP']}} "
        f"{'Short R':>{C['SR']}} "
        f"{'Epochs':>{C['EPOCH']}}"
        f"{RESET}"
    )
    sep = (
        f"  "
        + " ".join(f"{'─' * w}" for w in C.values())
    )
    print(header)
    print(f"{DIM}{sep}{RESET}")

    for r in sorted(asset_results, key=lambda x: x.get("asset", "")):
        asset = r.get("asset", "?").upper()
        pc    = r.get("per_class", {})
        val_acc = r.get("val_accuracy")
        long_p  = (pc.get("long")  or {}).get("precision")
        long_r  = (pc.get("long")  or {}).get("recall")
        short_p = (pc.get("short") or {}).get("precision")
        short_r = (pc.get("short") or {}).get("recall")
        epochs  = r.get("best_epoch", r.get("epochs", "?"))
        print(
            f"  "
            f"{asset:<{C['ASSET']}} "
            f"{'per-asset':<{C['TIER']}} "
            f"{_color_acc(val_acc)}{_fmt_metric(val_acc):>{C['ACC']}}{RESET} "
            f"{_fmt_metric(long_p):>{C['LP']}} "
            f"{_fmt_metric(long_r):>{C['LR']}} "
            f"{_fmt_metric(short_p):>{C['SP']}} "
            f"{_fmt_metric(short_r):>{C['SR']}} "
            f"{epochs!s:>{C['EPOCH']}}"
        )

    for r in sorted(skipped_results, key=lambda x: x.get("asset", "")):
        asset  = r.get("asset", "?").upper()
        reason = r.get("reason", "below threshold")
        val_acc = r.get("val_accuracy") or r.get("best_val_acc")
        tail_w  = C["LP"] + C["LR"] + C["SP"] + C["SR"] + 3
        print(
            f"  "
            f"{asset:<{C['ASSET']}} "
            f"{'per-asset':<{C['TIER']}} "
            f"{_color_acc(val_acc)}{_fmt_metric(val_acc):>{C['ACC']}}{RESET} "
            f"{RED}{'(not saved — ' + reason + ')':>{tail_w}}{RESET} "
            f"{'—':>{C['EPOCH']}}"
        )

    if master_results:
        mr = master_results[0]
        print(f"{DIM}{sep}{RESET}")
        epochs  = mr.get("best_epoch", mr.get("epochs", "?"))
        val_acc = mr.get("val_accuracy")
        val_f1  = mr.get("val_f1")
        pc      = mr.get("per_class", {})
        safe_p  = (pc.get("safe")  or {}).get("precision")
        safe_r  = (pc.get("safe")  or {}).get("recall")
        risky_p = (pc.get("risky") or {}).get("precision")
        risky_r = (pc.get("risky") or {}).get("recall")
        acc_color = _color_acc(val_acc) if val_acc is not None else CYAN

        if val_acc is not None:
            print(
                f"  "
                f"{'MASTER':<{C['ASSET']}} "
                f"{'portfolio':<{C['TIER']}} "
                f"{acc_color}{_fmt_metric(val_acc):>{C['ACC']}}{RESET} "
                f"{_fmt_metric(safe_p):>{C['LP']}} "
                f"{_fmt_metric(safe_r):>{C['LR']}} "
                f"{_fmt_metric(risky_p):>{C['SP']}} "
                f"{_fmt_metric(risky_r):>{C['SR']}} "
                f"{epochs!s:>{C['EPOCH']}}"
            )
            if val_f1 is not None:
                confidence = mr.get("model_confidence", "—")
                print(
                    f"  {DIM}  Master F1={val_f1:.3f}  "
                    f"confidence={confidence}  "
                    f"loss={mr.get('best_val_loss', 0):.4f}{RESET}"
                )
        else:
            val_loss = mr.get("best_val_loss")
            loss_str = f"{val_loss:.4f}" if val_loss is not None else "—"
            print(
                f"  "
                f"{'MASTER':<{C['ASSET']}} "
                f"{'portfolio':<{C['TIER']}} "
                f"{CYAN}{loss_str:>{C['ACC']}}{RESET} "
                f"{'(val_loss)':>{C['LP']}} "
                f"{'—':>{C['LR']}} "
                f"{'—':>{C['SP']}} "
                f"{'—':>{C['SR']}} "
                f"{epochs!s:>{C['EPOCH']}}"
            )

    print(f"{DIM}{sep}{RESET}")
    print()

    if asset_results:
        accs = [
            v * 100.0 if v <= 1.0 else v
            for r in asset_results
            if (v := r.get("val_accuracy")) is not None
        ]
        if accs:
            avg_acc   = sum(accs) / len(accs)
            best_acc  = max(accs)
            worst_acc = min(accs)
            best_asset  = max(asset_results, key=lambda r: _pct_raw(r.get("val_accuracy")) or 0)
            worst_asset = min(asset_results, key=lambda r: _pct_raw(r.get("val_accuracy")) or 999)

            print(f"  {BOLD}Per-asset accuracy:{RESET}")
            print(f"    Average : {avg_acc:.1f}%  ({len(accs)} models)")
            print(f"    Best    : {best_acc:.1f}%  ({best_asset.get('asset', '?').upper()})")
            print(f"    Worst   : {worst_acc:.1f}%  ({worst_asset.get('asset', '?').upper()})")
            print()

            if avg_acc >= 60:
                print(f"  {GREEN}✓ Models look viable for live CNN gating{RESET}")
            elif avg_acc >= 50:
                print(f"  {YELLOW}⚠ Accuracy is marginal — consider tuning labeling params or adding more data{RESET}")
            else:
                print(f"  {RED}✗ Accuracy below break-even — review label distributions and data quality{RESET}")

            all_long_p  = [(r.get("per_class") or {}).get("long",  {}).get("precision", 0) for r in asset_results]
            all_short_p = [(r.get("per_class") or {}).get("short", {}).get("precision", 0) for r in asset_results]
            avg_long_p  = sum(all_long_p)  / len(all_long_p)  if all_long_p  else 0
            avg_short_p = sum(all_short_p) / len(all_short_p) if all_short_p else 0

            if avg_long_p > 0 or avg_short_p > 0:
                print(
                    f"  {DIM}Avg long precision: {avg_long_p * 100:.1f}%  |  "
                    f"Avg short precision: {avg_short_p * 100:.1f}%{RESET}"
                )
            print()

    total_saved = len(asset_results) + len(master_results)
    if total_saved > 0:
        print(f"  {BOLD}Next steps:{RESET}")
        print(f"  {DIM}  1. Review metrics above — long/short precision > 40% is the key signal{RESET}")
        print(f"  {DIM}  2. Promote champions:  bash scripts/train.sh  (auto-commits to git){RESET}")
        print(f"  {DIM}  3. Deploy: restart the bot — CNN gate activates automatically{RESET}")
        print(f"  {DIM}  4. Monitor: check dashboard CNN stats + compare PnL with ml.enabled on/off{RESET}")
        print()
