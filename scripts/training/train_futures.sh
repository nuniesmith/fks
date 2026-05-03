#!/usr/bin/env bash
# =============================================================================
# Futures Trader — Full CNN Training Pipeline
# =============================================================================
#
# Three training modes (mutually exclusive, lowest to highest effort):
#
#   MODE 1 — Standard  (default)
#     Trains Tier 1 + Tier 2 with the hardcoded ASSET_LABEL_PARAMS from
#     train_asset.py.  Fast; good for iterating on architecture or after
#     market-structure changes when you just want a fresh model quickly.
#
#   MODE 2 — Label-Optimized  (--optimize-labels)
#     Runs per-asset Optuna label-param search BEFORE Tier 1 training.
#     Results are cached in models/label_params_{asset}.json (7-day TTL).
#     Tier 2 and the champion guard behave exactly as in standard mode.
#     Use this when you suspect the default consolidation / TP / SL ATR
#     multipliers have drifted from the current market regime.
#
#   MODE 3 — Full Pipeline  (--full-pipeline)
#     Invokes the 5-stage optimize_training.run_pipeline() via train.py:
#       Stage 0 — parallel data prefetch (warms Redis kline cache)
#       Stage 1 — per-asset label-param Optuna search (100 trials, cached)
#       Stage 2 — training hyperparameter Optuna search on proxy asset
#       Stage 3 — Tier-1 per-asset CNN training with best params
#       Stage 4 — Tier-2 MasterCNN training with best params
#       Stage 5 — champion promotion: compare new vs saved, promote if
#                 new_f1 > old_f1 + min_delta_f1; rollback otherwise
#     train.sh then reads the final .json files and does the git commit.
#     Use this for overnight / weekend runs.
#
# After every Mode 2 or Mode 3 run a "Defaults vs Optimized" comparison
# table is printed so you can see exactly what the optimizer changed and
# whether the new model is better or worse than the pre-run champion.
#
# Champion guard (default ON for Modes 1 & 2):
#   A new model is only promoted if it improves on the existing champion's
#   directional F1 score: (long_F1 + short_F1) / 2 for per-asset models,
#   val_f1 for the master.  Mode 3 runs its own internal champion guard
#   inside Python; train.sh's guard still fires on the final .pt files.
#   Use --no-champion-guard to bypass the shell-level guard.
#
# Auto-backup (default ON when --no-promote is set):
#   When --no-promote is used, all newly trained .pt/.json files are
#   copied to models/backups/run_TIMESTAMP/ so a subsequent run can't
#   overwrite them.  Use --no-backup to skip.
#
# Label-param cache (Mode 2 & 3):
#   Optimized label params are cached for 7 days per asset.  Pass
#   --force-label-opt to ignore the cache and re-search from scratch.
#
# Usage:
#   chmod +x scripts/train.sh && ./scripts/train.sh
#
#   # Mode 1 — standard
#   ./scripts/train.sh
#   ./scripts/train.sh --assets btc eth sol
#   ./scripts/train.sh --master-only
#
#   # Mode 2 — label-optimized
#   ./scripts/train.sh --optimize-labels
#   ./scripts/train.sh --optimize-labels --label-trials 200 --force-label-opt
#   ./scripts/train.sh --optimize-labels --assets btc eth --label-trials 150
#
#   # Mode 3 — full pipeline (overnight)
#   ./scripts/train.sh --full-pipeline
#   ./scripts/train.sh --full-pipeline --hyper-trials 100 --proxy-asset btc
#   ./scripts/train.sh --full-pipeline --force-label-opt --force-hyper-opt
#   ./scripts/train.sh --full-pipeline --assets btc eth doge avax wif
#
#   # Shared options (work in all modes)
#   ./scripts/train.sh --no-promote                # train, skip git commit
#   ./scripts/train.sh --no-champion-guard         # promote even if regressed
#   ./scripts/train.sh --dry-run                   # fetch + label, no training
#   ./scripts/train.sh --min-accuracy 0.55
#   ./scripts/train.sh --min-delta-f1 0.01         # stricter promotion gate
#   ./scripts/train.sh --help
#
# API keys are read from .env at the project root:
#   KUCOIN_API_KEY, KUCOIN_API_SECRET, KUCOIN_PASSPHRASE
# =============================================================================

set -euo pipefail

# ── Resolve project root ──────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
MODELS_DIR="${PROJECT_ROOT}/models"
SRUSTCODE_DIR="${PROJECT_ROOT}/src"

cd "${PROJECT_ROOT}"

# ── Colour helpers ────────────────────────────────────────────────────────────
if [[ -t 1 ]]; then
    C_RESET="\033[0m"  C_BOLD="\033[1m"   C_DIM="\033[2m"
    C_GREEN="\033[32m" C_YELLOW="\033[33m" C_RED="\033[31m" C_CYAN="\033[36m"
    C_MAGENTA="\033[35m"
else
    C_RESET="" C_BOLD="" C_DIM="" C_GREEN="" C_YELLOW="" C_RED="" C_CYAN=""
    C_MAGENTA=""
fi

bar()     { echo -e "${C_BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${C_RESET}"; }
section() { echo ""; bar; echo -e "${C_BOLD}  $*${C_RESET}"; bar; }
ok()      { echo -e "${C_GREEN}  ✅ $*${C_RESET}"; }
warn()    { echo -e "${C_YELLOW}  ⚠️  $*${C_RESET}"; }
info()    { echo -e "  $*"; }
err()     { echo -e "${C_RED}  ✗ $*${C_RESET}"; }
opt_row() { printf "  ${C_CYAN}%-28s${C_RESET} %s\n" "$1" "$2"; }

# ── Resolve Python interpreter ────────────────────────────────────────────────
if [[ -f "${PROJECT_ROOT}/.venv/bin/python" ]]; then
    PYTHON="${PROJECT_ROOT}/.venv/bin/python"
elif command -v python3.13 &>/dev/null; then PYTHON="python3.13"
elif command -v python3    &>/dev/null; then PYTHON="python3"
else PYTHON="python"; fi

PYTHON_VERSION="$("${PYTHON}" --version 2>&1)"

# Ensure src/ is importable as a flat package root so that
# `python -m src.ml.train` and internal `from ml.x import y` both work.
export PYTHONPATH="${SRUSTCODE_DIR}${PYTHONPATH:+:${PYTHONPATH}}"

# ── Load .env ─────────────────────────────────────────────────────────────────
ENV_FILE="${PROJECT_ROOT}/.env"
if [[ -f "${ENV_FILE}" ]]; then
    set -o allexport
    # shellcheck source=/dev/null
    source "${ENV_FILE}"
    set +o allexport
else
    warn ".env not found — market data (public endpoints) will still work"
fi

# ── Load enabled asset list from infrastructure/config/futures.yaml ─────────────────────────
CONFIG_FILE="${PROJECT_ROOT}/infrastructure/config/futures.yaml"

_load_config_assets() {
    "${PYTHON}" - "${CONFIG_FILE}" <<'PYEOF'
import sys, os, re
import yaml

config_path = sys.argv[1]

_ENV_RE = re.compile(r'\$\{([A-Za-z_][A-Za-z0-9_]*)(?::?-([^}]*))?\}')
def _expand(raw):
    return _ENV_RE.sub(lambda m: os.environ.get(m.group(1)) or m.group(2) or '', raw)

with open(config_path) as f:
    cfg = yaml.safe_load(_expand(f.read()))

enabled = [k for k, v in cfg.get('assets', {}).items() if v.get('enabled', True)]
print(' '.join(enabled))
PYEOF
}

if [[ ! -f "${CONFIG_FILE}" ]]; then
    warn "infrastructure/config/futures.yaml not found — falling back to built-in asset list"
    ALL_ASSETS=(btc eth sol doge pepe avax sui wif fart gold)
else
    # shellcheck disable=SC2207
    ALL_ASSETS=($(_load_config_assets))
    if [[ ${#ALL_ASSETS[@]} -eq 0 ]]; then
        warn "No enabled assets found in futures.yaml — check 'enabled: true' flags"
        ALL_ASSETS=(btc eth sol doge pepe avax sui wif fart gold)
    fi
fi

# ── Defaults ──────────────────────────────────────────────────────────────────
OPT_BARS=100000
OPT_MIN_BARS=5000
OPT_EPOCHS=60
OPT_TIMEFRAME="1m"
OPT_BATCH_SIZE=64
OPT_LR="3e-4"
OPT_WEIGHT_DECAY="5e-4"
OPT_VAL_SPLIT="0.15"
OPT_MIN_VAL_ACCURACY="0.38"
OPT_MIN_PROMOTE_ACCURACY="0.38"
OPT_LOSS_TYPE="focal"
OPT_FOCAL_GAMMA="2.0"
OPT_CLASS_WEIGHT_BOOST="1.0"
OPT_EARLY_STOP_METRIC="macro_f1"
OPT_EARLY_STOP_PATIENCE="20"
OPT_LABEL_SMOOTHING="0.15"
OPT_SEED=42
OPT_DRY_RUN=false
OPT_NO_PROMOTE=false
OPT_NO_LOG=false
OPT_MASTER_ONLY=false
OPT_CHAMPION_GUARD=true
OPT_NO_BACKUP=false
OPT_LOG_FILE=""
OPT_ASSETS=("${ALL_ASSETS[@]}")

OPT_CONSOLIDATION_ATR_MULT="4.0"
OPT_TP_ATR_MULT="1.5"
OPT_SL_ATR_MULT="1.0"

OPT_MASTER_EMBEDDING_DIM=48
OPT_MASTER_DROPOUT="0.4"
OPT_MASTER_ENCODER_DROPOUT="0.25"

# ── Optimization flags ────────────────────────────────────────────────────────
OPT_FULL_PIPELINE=false
OPT_OPTIMIZE_LABELS=false
OPT_LABEL_TRIALS=100
OPT_FORCE_LABEL_OPT=false
OPT_HYPER_TRIALS=50
OPT_PROXY_ASSET="btc"
OPT_FORCE_HYPER_OPT=false
OPT_MIN_DELTA_F1="0.005"
OPT_NO_GIT_TAG=false

# ── Argument parsing ──────────────────────────────────────────────────────────
show_help() {
    sed -n '3,73p' "$0" | sed 's/^# \{0,1\}//'
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --bars)                    OPT_BARS="${2:?}";                    shift 2 ;;
        --min-bars)                OPT_MIN_BARS="${2:?}";                shift 2 ;;
        --epochs)                  OPT_EPOCHS="${2:?}";                  shift 2 ;;
        --timeframe)               OPT_TIMEFRAME="${2:?}";               shift 2 ;;
        --batch-size)              OPT_BATCH_SIZE="${2:?}";              shift 2 ;;
        --lr)                      OPT_LR="${2:?}";                      shift 2 ;;
        --weight-decay)            OPT_WEIGHT_DECAY="${2:?}";            shift 2 ;;
        --val-split)               OPT_VAL_SPLIT="${2:?}";               shift 2 ;;
        --label-smoothing)         OPT_LABEL_SMOOTHING="${2:?}";         shift 2 ;;
        --min-accuracy)
            OPT_MIN_VAL_ACCURACY="${2:?}"
            OPT_MIN_PROMOTE_ACCURACY="${OPT_MIN_VAL_ACCURACY}"
            shift 2 ;;
        --consolidation-atr-mult)  OPT_CONSOLIDATION_ATR_MULT="${2:?}";  shift 2 ;;
        --tp-atr-mult)             OPT_TP_ATR_MULT="${2:?}";             shift 2 ;;
        --sl-atr-mult)             OPT_SL_ATR_MULT="${2:?}";             shift 2 ;;
        --loss-type)               OPT_LOSS_TYPE="${2:?}";               shift 2 ;;
        --focal-gamma)             OPT_FOCAL_GAMMA="${2:?}";             shift 2 ;;
        --class-weight-boost)      OPT_CLASS_WEIGHT_BOOST="${2:?}";      shift 2 ;;
        --early-stop-metric)       OPT_EARLY_STOP_METRIC="${2:?}";       shift 2 ;;
        --early-stop-patience)     OPT_EARLY_STOP_PATIENCE="${2:?}";     shift 2 ;;
        --seed)                    OPT_SEED="${2:?}";                    shift 2 ;;
        --master-embedding-dim)    OPT_MASTER_EMBEDDING_DIM="${2:?}";    shift 2 ;;
        --master-dropout)          OPT_MASTER_DROPOUT="${2:?}";          shift 2 ;;
        --master-encoder-dropout)  OPT_MASTER_ENCODER_DROPOUT="${2:?}";  shift 2 ;;
        --log-file)                OPT_LOG_FILE="${2:?}";                shift 2 ;;
        --optimize-labels)         OPT_OPTIMIZE_LABELS=true;             shift ;;
        --label-trials)            OPT_LABEL_TRIALS="${2:?}";            shift 2 ;;
        --force-label-opt)         OPT_FORCE_LABEL_OPT=true;             shift ;;
        --full-pipeline)           OPT_FULL_PIPELINE=true;               shift ;;
        --hyper-trials)            OPT_HYPER_TRIALS="${2:?}";            shift 2 ;;
        --proxy-asset)             OPT_PROXY_ASSET="${2:?}";             shift 2 ;;
        --force-hyper-opt)         OPT_FORCE_HYPER_OPT=true;             shift ;;
        --min-delta-f1)            OPT_MIN_DELTA_F1="${2:?}";            shift 2 ;;
        --no-git-tag)              OPT_NO_GIT_TAG=true;                  shift ;;
        --dry-run)                 OPT_DRY_RUN=true;                     shift ;;
        --no-promote)              OPT_NO_PROMOTE=true;                  shift ;;
        --master-only)             OPT_MASTER_ONLY=true;                 shift ;;
        --no-champion-guard)       OPT_CHAMPION_GUARD=false;             shift ;;
        --no-backup)               OPT_NO_BACKUP=true;                   shift ;;
        --no-log)                  OPT_NO_LOG=true;                      shift ;;
        --assets)
            shift; OPT_ASSETS=()
            while [[ $# -gt 0 && "${1}" != --* ]]; do
                OPT_ASSETS+=("${1}"); shift
            done
            [[ ${#OPT_ASSETS[@]} -eq 0 ]] && { err "--assets requires at least one key"; exit 1; }
            ;;
        --help|-h) show_help; exit 0 ;;
        *) err "Unknown option: $1"; echo "Run with --help for usage." >&2; exit 1 ;;
    esac
done

# ── Validate mode conflicts ───────────────────────────────────────────────────
if [[ "${OPT_FULL_PIPELINE}" == true && "${OPT_MASTER_ONLY}" == true ]]; then
    err "--full-pipeline and --master-only are mutually exclusive"
    exit 1
fi
if [[ "${OPT_FULL_PIPELINE}" == true && "${OPT_OPTIMIZE_LABELS}" == true ]]; then
    warn "--optimize-labels is implied by --full-pipeline (Stage 1), ignoring the flag"
    OPT_OPTIMIZE_LABELS=false
fi

DRY_RUN_FLAG=()
[[ "${OPT_DRY_RUN}" == true ]] && DRY_RUN_FLAG=(--dry-run)

if   [[ "${OPT_FULL_PIPELINE}"    == true ]]; then ACTIVE_MODE="Mode 3 — Full Pipeline"
elif [[ "${OPT_OPTIMIZE_LABELS}"  == true ]]; then ACTIVE_MODE="Mode 2 — Label-Optimized"
else                                               ACTIVE_MODE="Mode 1 — Standard"
fi

# ── Pre-flight: filter assets to those registered in ASSET_SYMBOLS ────────────
#
# FIX: was filtering against ASSET_LABEL_PARAMS (pre-tuned subset, 10 assets).
# Now filters against ASSET_SYMBOLS (full registry), so assets that have a
# KuCoin symbol but fall back to CLI-default label params are NOT silently
# dropped.  ASSET_SYMBOLS lives in ml.train_asset, not ml.train.
_ASSET_FILTER_JSON="$("${PYTHON}" - "${SRUSTCODE_DIR}" "${OPT_ASSETS[@]}" 2>/dev/null <<'PYEOF'
import sys, json
sys.path.insert(0, sys.argv[1])
try:
    from ml.train_asset import ASSET_SYMBOLS
    known   = set(ASSET_SYMBOLS.keys())
    passed  = sys.argv[2:]
    valid   = [a for a in passed if a in known]
    unknown = [a for a in passed if a not in known]
except ImportError:
    valid, unknown = list(sys.argv[2:]), []
print(json.dumps({"valid": valid, "unknown": unknown}))
PYEOF
)"

if [[ -n "${_ASSET_FILTER_JSON}" ]]; then
    _VALID_STR="$(   "${PYTHON}" -c "import json,sys; print(' '.join(json.loads(sys.stdin.read())['valid']))"   <<< "${_ASSET_FILTER_JSON}")"
    _UNKNOWN_STR="$( "${PYTHON}" -c "import json,sys; print(' '.join(json.loads(sys.stdin.read())['unknown']))" <<< "${_ASSET_FILTER_JSON}")"
    [[ -n "${_VALID_STR}" ]] && read -ra OPT_ASSETS <<< "${_VALID_STR}"
    if [[ -n "${_UNKNOWN_STR}" ]]; then
        warn "${_UNKNOWN_STR} — not in ASSET_SYMBOLS registry (src/ml/train_asset.py), skipping"
        info "Add the KuCoin symbol to ASSET_SYMBOLS in src/ml/train_asset.py to enable."
        echo ""
    fi
fi

# ── Ensure output directories exist ──────────────────────────────────────────
mkdir -p "${MODELS_DIR}"

# ── Log file setup ────────────────────────────────────────────────────────────
if [[ "${OPT_NO_LOG}" != true ]]; then
    LOGS_DIR="${PROJECT_ROOT}/logs"
    mkdir -p "${LOGS_DIR}"
    if [[ -z "${OPT_LOG_FILE}" ]]; then
        LOG_FILE="${LOGS_DIR}/train_$(date +%Y-%m-%d_%H%M%S).log"
    else
        LOG_FILE="${OPT_LOG_FILE}"
        mkdir -p "$(dirname "${LOG_FILE}")"
    fi
    exec > >(tee "${LOG_FILE}") 2>&1
else
    LOG_FILE=""
fi

# ── Startup banner ────────────────────────────────────────────────────────────
section "Futures CNN — Full Training Pipeline"
info "Python       : ${PYTHON}  (${PYTHON_VERSION})"
info "PYTHONPATH   : ${PYTHONPATH}"
info "Config       : ${CONFIG_FILE}"
echo -e "  ${C_MAGENTA}${C_BOLD}Mode         : ${ACTIVE_MODE}${C_RESET}"
info "Assets       : ${OPT_ASSETS[*]}  (${#OPT_ASSETS[@]} total)"
info "Bars/asset   : ${OPT_BARS}  (${OPT_TIMEFRAME})"
info "Min Bars     : ${OPT_MIN_BARS}"
info "Epochs       : ${OPT_EPOCHS}"
info "Batch size   : ${OPT_BATCH_SIZE}"
info "LR           : ${OPT_LR}  (weight_decay=${OPT_WEIGHT_DECAY})"
info "Loss         : ${OPT_LOSS_TYPE}  γ=${OPT_FOCAL_GAMMA}  class-boost=${OPT_CLASS_WEIGHT_BOOST}×"
info "Early stop   : ${OPT_EARLY_STOP_METRIC}  patience=${OPT_EARLY_STOP_PATIENCE}"
info "ATR mult     : ${OPT_CONSOLIDATION_ATR_MULT}  (consolidation default)"
info "TP/SL mult   : ${OPT_TP_ATR_MULT} / ${OPT_SL_ATR_MULT}  (defaults, overridden by per-asset params)"
info "Min acc      : ${OPT_MIN_PROMOTE_ACCURACY}"
info "Models dir   : ${MODELS_DIR}"
[[ -n "${LOG_FILE}" ]] && info "Log file     : ${LOG_FILE}" || info "Log file     : disabled (--no-log)"
info "Master only  : ${OPT_MASTER_ONLY}  (embed=${OPT_MASTER_EMBEDDING_DIM}  drop=${OPT_MASTER_DROPOUT}  enc_drop=${OPT_MASTER_ENCODER_DROPOUT})"
info "Champ guard  : ${OPT_CHAMPION_GUARD}"
info "Dry run      : ${OPT_DRY_RUN}"

if [[ "${OPT_FULL_PIPELINE}" == true || "${OPT_OPTIMIZE_LABELS}" == true ]]; then
    echo ""
    echo -e "  ${C_MAGENTA}${C_BOLD}── Optimization Settings ──────────────────────────────────${C_RESET}"
    opt_row "Label trials"    "${OPT_LABEL_TRIALS}"
    opt_row "Force label-opt" "${OPT_FORCE_LABEL_OPT}"
    if [[ "${OPT_FULL_PIPELINE}" == true ]]; then
        _hyper_est_min=$(( OPT_HYPER_TRIALS * 7 ))
        opt_row "Hyper trials"    "${OPT_HYPER_TRIALS}  (~$(( _hyper_est_min / 60 ))h$(( _hyper_est_min % 60 ))m est.)"
        opt_row "Proxy asset"     "${OPT_PROXY_ASSET}"
        opt_row "Force hyper-opt" "${OPT_FORCE_HYPER_OPT}"
        opt_row "Min delta F1"    "${OPT_MIN_DELTA_F1}"
        opt_row "Git tag"         "$([ "${OPT_NO_GIT_TAG}" == true ] && echo disabled || echo enabled)"
    fi
fi

if [[ "${OPT_NO_PROMOTE}" == true ]]; then
    [[ "${OPT_NO_BACKUP}" == true ]] \
        && info "Promote      : no (--no-promote, backup disabled)" \
        || info "Promote      : no (--no-promote, models will be auto-backed up)"
else
    info "Promote      : yes — git commit champions >= ${OPT_MIN_PROMOTE_ACCURACY}"
fi
echo ""

if [[ -n "${KUCOIN_API_KEY:-}" ]]; then
    MASKED="${KUCOIN_API_KEY:0:4}****${KUCOIN_API_KEY: -4}"
    info "API key      : ${MASKED}"
else
    warn "KUCOIN_API_KEY not set — using public endpoints only"
fi

# ── Snapshot existing champion metrics ───────────────────────────────────────
SNAPSHOT_FILE="$(mktemp /tmp/train_champ_snapshot.XXXXXX)"
trap 'rm -f "${SNAPSHOT_FILE}"' EXIT

"${PYTHON}" - "${MODELS_DIR}" > "${SNAPSHOT_FILE}" <<'PYEOF'
import sys, json
from pathlib import Path

models_dir = Path(sys.argv[1])
for jf in sorted(models_dir.glob("cnn_*.json")):
    try:
        data = json.loads(jf.read_text())
    except Exception:
        continue
    if not jf.with_suffix(".pt").exists():
        continue

    key = jf.stem[len("cnn_"):]
    pc  = data.get("per_class", {})

    if key == "master":
        dir_f1 = float(data.get("val_f1") or 0)
    else:
        lf1 = float((pc.get("long",  {}) or {}).get("f1") or 0)
        sf1 = float((pc.get("short", {}) or {}).get("f1") or 0)
        dir_f1 = (lf1 + sf1) / 2.0

    val_acc = float(data.get("val_accuracy") or 0)
    val_f1  = float(data.get("val_f1") or 0)
    print(f"{key}\t{dir_f1:.6f}\t{val_acc:.6f}\t{val_f1:.6f}")
PYEOF

PIPELINE_START=$(date +%s)
TIER1_ELAPSED=0
TIER2_ELAPSED=0

# ── "Defaults vs Optimized" comparison table ─────────────────────────────────
#
# FIX: was importing ASSET_LABEL_PARAMS from ml.train (doesn't exist there).
# The dict lives in ml.train_asset.  Also changed PYTHONPATH to SRUSTCODE_DIR
# so bare `from ml.x import y` imports resolve correctly.

_print_label_comparison() {
    "${PYTHON}" - "${MODELS_DIR}" "${SRUSTCODE_DIR}" <<'PYEOF'
import json, sys
from pathlib import Path

models_dir = Path(sys.argv[1])
src_dir    = Path(sys.argv[2])

sys.path.insert(0, str(src_dir))
try:
    from ml.train_asset import ASSET_LABEL_PARAMS as DEFAULTS
except ImportError as exc:
    print(f"  Could not import ASSET_LABEL_PARAMS from ml.train_asset: {exc}", file=sys.stderr)
    sys.exit(0)

GREEN  = "\033[92m"
RED    = "\033[91m"
RESET  = "\033[0m"
BOLD   = "\033[1m"
DIM    = "\033[2m"

print(f"  {BOLD}{'Asset':<12} {'Param':<22} {'Default':>9} {'Optimized':>10} {'Delta':>9}  {'Verdict':<16}{RESET}")
print(f"  {'─'*12} {'─'*22} {'─'*9} {'─'*10} {'─'*9}  {'─'*16}")

any_data = False
for asset in sorted(DEFAULTS.keys()):
    cache_path = models_dir / f"label_params_{asset}.json"
    if not cache_path.exists():
        continue
    try:
        cached = json.loads(cache_path.read_text())
    except Exception:
        continue

    opt_params = cached.get("params", {})
    defaults   = DEFAULTS[asset]
    any_data   = True
    first      = True

    for param, default_val in defaults.items():
        opt_val = opt_params.get(param)
        if opt_val is None:
            continue

        if isinstance(default_val, float):
            delta     = opt_val - default_val
            delta_str = f"{delta:+.3f}"
            if abs(delta) < 0.05:
                color, verdict = DIM,   "≈ unchanged"
            elif delta > 0:
                color, verdict = GREEN, "▲ increased"
            else:
                color, verdict = RED,   "▼ decreased"
            row = (
                f"  {asset.upper() if first else '':<12} {param:<22}"
                f" {default_val:>9.3f} {opt_val:>10.3f}"
                f" {color}{delta_str:>9}{RESET}  {color}{verdict}{RESET}"
            )
        else:
            delta     = int(opt_val) - int(default_val)
            delta_str = f"{delta:+d}"
            if delta == 0:
                color, verdict = DIM,   "≈ unchanged"
            elif delta > 0:
                color, verdict = GREEN, "▲ increased"
            else:
                color, verdict = RED,   "▼ decreased"
            row = (
                f"  {asset.upper() if first else '':<12} {param:<22}"
                f" {int(default_val):>9d} {int(opt_val):>10d}"
                f" {color}{delta_str:>9}{RESET}  {color}{verdict}{RESET}"
            )

        print(row)
        first = False

    train_score = cached.get("train_score", 0)
    val_score   = cached.get("val_score",   0)
    emp         = cached.get("empirical_accuracy", {})
    overall_acc = emp.get("overall", 0)
    if val_score > 0:
        print(f"  {'':12} {'label quality scores':<22} {'train':>9} {'val':>10} {'emp_acc':>9}")
        print(f"  {'':12} {'':22} {train_score:>9.4f} {val_score:>10.4f} {overall_acc:>9.1%}")
    print()

if not any_data:
    print("  No label_params_*.json files found — run with --full-pipeline or --optimize-labels first.")

print(f"  {DIM}Green = optimizer moved param higher  |  Red = optimizer moved it lower{RESET}")
print(f"  {DIM}These params feed directly into generate_labels_breakout() for each asset{RESET}")
PYEOF
}

# ── Warn about degenerate cached label params (>97% flat labels) ──────────────
#
# FIX: was reading key "val_dist" — actual key written by optimize_labels.py
# is "val_distribution".  Also only runs when label opt cache files exist.

_check_label_quality() {
    "${PYTHON}" - "${MODELS_DIR}" <<'PYEOF'
import json, sys
from pathlib import Path
models_dir = Path(sys.argv[1])
flagged = []
for jf in sorted(models_dir.glob("label_params_*.json")):
    try:
        d    = json.loads(jf.read_text())
        dist = d.get("val_distribution", {})   # FIX: was "val_dist"
        flat = float(dist.get("flat", 0))
        if flat > 97.0:                         # stored as percentage (0-100)
            asset = jf.stem.replace("label_params_", "").upper()
            flagged.append(f"{asset} ({flat:.1f}% flat)")
    except Exception:
        pass
if flagged:
    print("DEGENERATE: " + ", ".join(flagged))
PYEOF
}

# =============================================================================
# MODE 3 — Full Pipeline
# =============================================================================

PIPELINE_RC=0

if [[ "${OPT_FULL_PIPELINE}" == true ]]; then
    section "MODE 3 — Full Pipeline  (5 stages)"
    info "Stages: prefetch → label-opt → hyper-opt → Tier-1 → Tier-2 → champion promote"
    info "Label trials : ${OPT_LABEL_TRIALS}  |  Hyper trials : ${OPT_HYPER_TRIALS}"
    info "Proxy asset  : ${OPT_PROXY_ASSET}"
    info "Min ΔF1      : ${OPT_MIN_DELTA_F1}"
    echo ""

    # FIX: was a string with += (word-splitting risk on values with spaces).
    # Use a proper bash array instead.
    PIPELINE_FLAGS=()
    [[ "${OPT_FORCE_LABEL_OPT}" == true ]] && PIPELINE_FLAGS+=(--force-label-opt)
    [[ "${OPT_FORCE_HYPER_OPT}" == true ]] && PIPELINE_FLAGS+=(--force-hyper-opt)
    [[ "${OPT_NO_GIT_TAG}"      == true ]] && PIPELINE_FLAGS+=(--no-git-tag)

    set +e
    "${PYTHON}" -m src.ml.train \
        --full-pipeline                                              \
        --assets              "${OPT_ASSETS[@]}"                    \
        --bars                "${OPT_BARS}"                         \
        --min-bars            "${OPT_MIN_BARS}"                     \
        --epochs              "${OPT_EPOCHS}"                       \
        --timeframe           "${OPT_TIMEFRAME}"                    \
        --batch-size          "${OPT_BATCH_SIZE}"                   \
        --lr                  "${OPT_LR}"                           \
        --weight-decay        "${OPT_WEIGHT_DECAY}"                 \
        --val-split           "${OPT_VAL_SPLIT}"                    \
        --min-val-accuracy    "${OPT_MIN_VAL_ACCURACY}"             \
        --loss-type           "${OPT_LOSS_TYPE}"                    \
        --focal-gamma         "${OPT_FOCAL_GAMMA}"                  \
        --class-weight-boost  "${OPT_CLASS_WEIGHT_BOOST}"           \
        --early-stop-metric   "${OPT_EARLY_STOP_METRIC}"            \
        --early-stop-patience "${OPT_EARLY_STOP_PATIENCE}"          \
        --label-smoothing     "${OPT_LABEL_SMOOTHING}"              \
        --consolidation-atr-mult "${OPT_CONSOLIDATION_ATR_MULT}"    \
        --tp-atr-mult         "${OPT_TP_ATR_MULT}"                  \
        --sl-atr-mult         "${OPT_SL_ATR_MULT}"                  \
        --models-dir          "${MODELS_DIR}"                       \
        --seed                "${OPT_SEED}"                         \
        --master-embedding-dim   "${OPT_MASTER_EMBEDDING_DIM}"      \
        --master-dropout         "${OPT_MASTER_DROPOUT}"            \
        --master-encoder-dropout "${OPT_MASTER_ENCODER_DROPOUT}"    \
        --label-trials        "${OPT_LABEL_TRIALS}"                 \
        --hyper-trials        "${OPT_HYPER_TRIALS}"                 \
        --proxy-asset         "${OPT_PROXY_ASSET}"                  \
        --min-delta-f1        "${OPT_MIN_DELTA_F1}"                 \
        "${PIPELINE_FLAGS[@]}"                                      \
        "${DRY_RUN_FLAG[@]}"

    PIPELINE_RC=$?
    set -e

    PIPELINE_END_INNER=$(date +%s)
    TIER1_ELAPSED=$(( PIPELINE_END_INNER - PIPELINE_START ))
    TIER2_ELAPSED=0

    echo ""
    if [[ $PIPELINE_RC -eq 0 ]]; then
        ok "Full pipeline complete — $(( TIER1_ELAPSED / 60 ))m $(( TIER1_ELAPSED % 60 ))s"
    else
        _saved=$(find "${MODELS_DIR}" -name "cnn_*.pt" 2>/dev/null | wc -l | tr -d ' ')
        if [[ "${PIPELINE_RC}" -eq 1 && "${_saved}" -gt 0 ]]; then
            warn "Pipeline exited 1 (non-fatal logging bug) — ${_saved} model(s) saved — $(( TIER1_ELAPSED / 60 ))m $(( TIER1_ELAPSED % 60 ))s"
            info "Fix: src/ml/optimize_training.py final logger.info has mismatched format args."
        else
            warn "Full pipeline failed (exit ${PIPELINE_RC}) — $(( TIER1_ELAPSED / 60 ))m $(( TIER1_ELAPSED % 60 ))s"
        fi
    fi

    section "Defaults vs Optimized — Label Param Comparison"
    echo ""
    _print_label_comparison

    _degen="$(_check_label_quality)"
    if [[ "${_degen}" == DEGENERATE:* ]]; then
        echo ""
        warn "Degenerate label params detected: ${_degen#DEGENERATE: }"
        info "Re-run with --force-label-opt to bust the 7-day cache for these assets."
    fi

else
    # =========================================================================
    # MODE 1 & 2 — Standard / Label-Optimized
    # =========================================================================

    # FIX: was string concatenation (word-splitting risk).  Use an array.
    LABEL_OPT_FLAGS=()
    if [[ "${OPT_OPTIMIZE_LABELS}" == true ]]; then
        LABEL_OPT_FLAGS+=(--optimize-labels --label-opt-trials "${OPT_LABEL_TRIALS}")
        [[ "${OPT_FORCE_LABEL_OPT}" == true ]] && LABEL_OPT_FLAGS+=(--force-label-opt)
    fi

    # ── TIER 1 — Per-Asset CNN ────────────────────────────────────────────────

    TIER1_RC=0

    if [[ "${OPT_MASTER_ONLY}" == true ]]; then
        section "TIER 1 — Per-Asset CNN  (SKIPPED — --master-only)"
        EXISTING_MODELS=$(find "${MODELS_DIR}" -name "cnn_*.pt" ! -name "cnn_master.pt" 2>/dev/null | wc -l | tr -d ' ')
        info "Skipping per-asset training — using ${EXISTING_MODELS} existing model(s) in ${MODELS_DIR}/"
        [[ "${EXISTING_MODELS}" -eq 0 ]] && warn "No per-asset models found — master encoder warm-start will be skipped."
        echo ""
    else
        if [[ "${OPT_OPTIMIZE_LABELS}" == true ]]; then
            section "TIER 1 — Per-Asset CNN  (${#OPT_ASSETS[@]} assets)  +  Label Optimization"
            info "Label-param Optuna search will run BEFORE each asset's training."
            info "Trials : ${OPT_LABEL_TRIALS}  |  Cache TTL : 7 days  |  Force : ${OPT_FORCE_LABEL_OPT}"
        else
            section "TIER 1 — Per-Asset CNN  (${#OPT_ASSETS[@]} assets)"
        fi
        info "Training: ${OPT_ASSETS[*]}"
        echo ""

        TIER1_START=$(date +%s)
        set +e

        "${PYTHON}" -m src.ml.train \
            --assets              "${OPT_ASSETS[@]}"                         \
            --bars                "${OPT_BARS}"                              \
            --min-bars            "${OPT_MIN_BARS}"                          \
            --epochs              "${OPT_EPOCHS}"                            \
            --timeframe           "${OPT_TIMEFRAME}"                         \
            --batch-size          "${OPT_BATCH_SIZE}"                        \
            --lr                  "${OPT_LR}"                                \
            --weight-decay        "${OPT_WEIGHT_DECAY}"                      \
            --val-split           "${OPT_VAL_SPLIT}"                         \
            --min-val-accuracy    "${OPT_MIN_VAL_ACCURACY}"                  \
            --loss-type           "${OPT_LOSS_TYPE}"                         \
            --focal-gamma         "${OPT_FOCAL_GAMMA}"                       \
            --class-weight-boost  "${OPT_CLASS_WEIGHT_BOOST}"                \
            --early-stop-metric   "${OPT_EARLY_STOP_METRIC}"                 \
            --early-stop-patience "${OPT_EARLY_STOP_PATIENCE}"               \
            --label-smoothing     "${OPT_LABEL_SMOOTHING}"                   \
            --consolidation-atr-mult "${OPT_CONSOLIDATION_ATR_MULT}"         \
            --tp-atr-mult         "${OPT_TP_ATR_MULT}"                       \
            --sl-atr-mult         "${OPT_SL_ATR_MULT}"                       \
            --models-dir          "${MODELS_DIR}"                            \
            --seed                "${OPT_SEED}"                              \
            "${LABEL_OPT_FLAGS[@]}"                                          \
            "${DRY_RUN_FLAG[@]}"

        TIER1_RC=$?
        set -e

        TIER1_END=$(date +%s)
        TIER1_ELAPSED=$(( TIER1_END - TIER1_START ))

        echo ""
        if [[ $TIER1_RC -eq 0 ]]; then
            ok "Tier 1 complete — $(( TIER1_ELAPSED / 60 ))m $(( TIER1_ELAPSED % 60 ))s"
        else
            warn "Tier 1 finished with warnings (exit ${TIER1_RC}) — $(( TIER1_ELAPSED / 60 ))m $(( TIER1_ELAPSED % 60 ))s"
        fi
    fi

    # ── Auto-backup when --no-promote ─────────────────────────────────────────
    if [[ "${OPT_NO_PROMOTE}" == true && "${OPT_NO_BACKUP}" != true && "${OPT_DRY_RUN}" != true ]]; then
        BACKUP_DIR="${MODELS_DIR}/backups/run_$(date +%Y%m%d_%H%M%S)"
        mkdir -p "${BACKUP_DIR}"
        BACKED_UP=0
        for pt in "${MODELS_DIR}"/cnn_*.pt; do
            [[ -f "${pt}" ]] || continue
            base="$(basename "${pt}" .pt)"
            json="${MODELS_DIR}/${base}.json"
            cp "${pt}" "${BACKUP_DIR}/"
            [[ -f "${json}" ]] && cp "${json}" "${BACKUP_DIR}/"
            BACKED_UP=$(( BACKED_UP + 1 ))
        done
        if [[ $BACKED_UP -gt 0 ]]; then
            echo ""
            ok "Auto-backed up ${BACKED_UP} model(s) → ${BACKUP_DIR}/"
        fi
    fi

    # ── TIER 2 — MasterCNN ────────────────────────────────────────────────────
    section "TIER 2 — MasterCNN  Portfolio Risk Aggregator"
    info "Assets for master model: ${OPT_ASSETS[*]}"
    echo ""

    TIER2_START=$(date +%s)
    set +e

    # FIX: was missing --assets, so train.py would fall back to its full
    # DEFAULT_ASSETS list regardless of what --assets was passed at the top.
    # Now explicitly passes the same OPT_ASSETS used for Tier 1.
    "${PYTHON}" -m src.ml.train \
        --master-only                                                \
        --assets              "${OPT_ASSETS[@]}"                    \
        --bars                "${OPT_BARS}"                         \
        --min-bars            "${OPT_MIN_BARS}"                     \
        --epochs              "${OPT_EPOCHS}"                       \
        --timeframe           "${OPT_TIMEFRAME}"                    \
        --loss-type           "${OPT_LOSS_TYPE}"                    \
        --focal-gamma         "${OPT_FOCAL_GAMMA}"                  \
        --class-weight-boost  "${OPT_CLASS_WEIGHT_BOOST}"           \
        --early-stop-metric   "${OPT_EARLY_STOP_METRIC}"            \
        --early-stop-patience "${OPT_EARLY_STOP_PATIENCE}"          \
        --mixup-alpha         "0.2"                                 \
        --batch-size          "${OPT_BATCH_SIZE}"                   \
        --lr                  "${OPT_LR}"                           \
        --weight-decay        "${OPT_WEIGHT_DECAY}"                 \
        --val-split           "${OPT_VAL_SPLIT}"                    \
        --master-embedding-dim   "${OPT_MASTER_EMBEDDING_DIM}"      \
        --master-dropout         "${OPT_MASTER_DROPOUT}"            \
        --master-encoder-dropout "${OPT_MASTER_ENCODER_DROPOUT}"    \
        --consolidation-atr-mult "${OPT_CONSOLIDATION_ATR_MULT}"    \
        --tp-atr-mult         "${OPT_TP_ATR_MULT}"                  \
        --sl-atr-mult         "${OPT_SL_ATR_MULT}"                  \
        --models-dir          "${MODELS_DIR}"                       \
        --seed                "${OPT_SEED}"                         \
        "${DRY_RUN_FLAG[@]}"

    TIER2_RC=$?
    set -e

    TIER2_END=$(date +%s)
    TIER2_ELAPSED=$(( TIER2_END - TIER2_START ))

    echo ""
    if [[ $TIER2_RC -eq 0 ]]; then
        ok "Tier 2 complete — $(( TIER2_ELAPSED / 60 ))m $(( TIER2_ELAPSED % 60 ))s"
    else
        warn "Tier 2 finished with warnings (exit ${TIER2_RC}) — $(( TIER2_ELAPSED / 60 ))m $(( TIER2_ELAPSED % 60 ))s"
    fi

    if [[ "${OPT_OPTIMIZE_LABELS}" == true && "${OPT_DRY_RUN}" != true ]]; then
        section "Defaults vs Optimized — Label Param Comparison"
        echo ""
        _print_label_comparison

        _degen="$(_check_label_quality)"
        if [[ "${_degen}" == DEGENERATE:* ]]; then
            echo ""
            warn "Degenerate label params detected: ${_degen#DEGENERATE: }"
            info "Re-run with --force-label-opt to bust the 7-day cache for these assets."
        fi
    fi

fi  # end mode branch

# ── Dry-run exit ──────────────────────────────────────────────────────────────
if [[ "${OPT_DRY_RUN}" == true ]]; then
    section "Dry Run — Skipping Champion Promotion"
    info "Re-run without --dry-run to perform full training and promotion."
    echo ""
    PIPELINE_END=$(date +%s)
    PIPELINE_ELAPSED=$(( PIPELINE_END - PIPELINE_START ))
    section "Pipeline Complete (dry run)"
    printf "  Total  : %dm %02ds\n" $(( PIPELINE_ELAPSED / 60 )) $(( PIPELINE_ELAPSED % 60 ))
    echo ""; exit 0
fi

# =============================================================================
# CHAMPION SELECTION
# =============================================================================

section "Champion Selection  (threshold >= ${OPT_MIN_PROMOTE_ACCURACY})"
echo ""

CHAMPION_GUARD_FLAG="${OPT_CHAMPION_GUARD}"

PARSED_TABLE="$("${PYTHON}" - "${MODELS_DIR}" "${OPT_MIN_PROMOTE_ACCURACY}" "${SNAPSHOT_FILE}" "${CHAMPION_GUARD_FLAG}" <<'PYEOF'
import sys, json
from pathlib import Path

def pct(v):
    if v is None: return "—"
    try:
        f = float(v)
        return f"{f * 100:.1f}%" if f <= 1.0 else f"{f:.1f}%"
    except (TypeError, ValueError):
        return "—"

models_dir   = Path(sys.argv[1])
min_acc      = float(sys.argv[2])
snapshot_f   = Path(sys.argv[3])
guard_on     = sys.argv[4].lower() == "true"

old_metrics = {}
try:
    for line in snapshot_f.read_text().splitlines():
        parts = line.split("\t")
        if len(parts) >= 4:
            old_metrics[parts[0]] = (float(parts[1]), float(parts[2]), float(parts[3]))
except Exception:
    pass

for jf in sorted(models_dir.glob("cnn_*.json")):
    try:
        data = json.loads(jf.read_text())
    except Exception:
        continue

    pt_file = jf.with_suffix(".pt")
    if not pt_file.exists():
        continue

    key        = jf.stem[len("cnn_"):]
    model_type = "master" if key == "master" else "per-asset"
    val_acc    = data.get("val_accuracy")
    val_f1     = data.get("val_f1")
    trained    = str(data.get("trained_at", "unknown"))[:19]
    epochs     = data.get("epochs", "?")
    best_ep    = data.get("best_epoch", "")
    tf         = data.get("timeframe", "?")
    kb         = round(pt_file.stat().st_size / 1024, 1)
    epoch_str  = f"{best_ep}/{epochs}" if best_ep else str(epochs)
    confidence = data.get("model_confidence", "")

    pc = data.get("per_class", {})
    if model_type == "master":
        fmt_lp = pct(pc.get("safe",  {}).get("precision"))
        fmt_lr = pct(pc.get("safe",  {}).get("recall"))
        fmt_sp = pct(pc.get("risky", {}).get("precision"))
        fmt_sr = pct(pc.get("risky", {}).get("recall"))
        new_dir_f1 = float(val_f1 or 0)
        check_val  = float(val_f1 or 0)
    else:
        fmt_lp = pct(pc.get("long",  {}).get("precision"))
        fmt_lr = pct(pc.get("long",  {}).get("recall"))
        fmt_sp = pct(pc.get("short", {}).get("precision"))
        fmt_sr = pct(pc.get("short", {}).get("recall"))
        lf1 = float((pc.get("long",  {}) or {}).get("f1") or 0)
        sf1 = float((pc.get("short", {}) or {}).get("f1") or 0)
        new_dir_f1 = (lf1 + sf1) / 2.0
        check_val  = float(val_acc or 0)

    fmt_acc = pct(val_acc) if val_acc is not None else "n/a"
    fmt_f1  = pct(val_f1) if val_f1 is not None else ""

    meets_threshold = check_val >= min_acc

    if not meets_threshold:
        guard_action = "below"
    elif key not in old_metrics:
        guard_action = "new"
    else:
        old_dir_f1 = old_metrics[key][0]
        if guard_on and new_dir_f1 < old_dir_f1 - 0.01:
            guard_action = "regressed"
        else:
            guard_action = "promote"

    print("\t".join([
        key, model_type, str(val_acc or ""), trained, epoch_str, tf,
        str(kb), str(pt_file), str(jf), guard_action,
        fmt_acc, fmt_lp, fmt_lr, fmt_sp, fmt_sr, fmt_f1, confidence,
        f"{new_dir_f1:.4f}",
        f"{old_metrics.get(key, (0,))[0]:.4f}" if key in old_metrics else "n/a",
    ]))
PYEOF
)"

if [[ -z "${PARSED_TABLE}" ]]; then
    warn "No trained models found in ${MODELS_DIR}"
    exit 0
fi

# ── Print selection table ─────────────────────────────────────────────────────
printf "  ${C_BOLD}%-12s %-10s %-10s %-8s %-8s %-8s %-8s %-8s %-4s %-8s${C_RESET}\n" \
    "ASSET" "TYPE" "VAL_ACC" "LONG_P" "LONG_R" "SHORT_P" "SHORT_R" "EPOCH" "TF" "SIZE"
echo "  ──────────────────────────────────────────────────────────────────────────────────────────────"

CHAMP_PT_FILES=()
CHAMP_JSON_FILES=()
CHAMP_LABELS=()
CHAMP_ACCS=()
GUARDED_LABELS=()

while IFS=$'\t' read -r key model_type val_acc trained epoch_str tf kb pt_file json_file \
    guard_action fmt_acc fmt_lp fmt_lr fmt_sp fmt_sr fmt_f1 confidence new_dir_f1 old_dir_f1; do

    if git ls-files --error-unmatch "${pt_file}" &>/dev/null 2>&1; then
        GIT_TAG="${C_CYAN}[tracked]${C_RESET}"
    else
        GIT_TAG="${C_DIM}[new]${C_RESET}    "
    fi

    case "${guard_action}" in
        promote|new)
            ACC_COL="${C_GREEN}"
            BADGE="${C_GREEN}★ champion${C_RESET}"
            CHAMP_PT_FILES+=("${pt_file}")
            CHAMP_JSON_FILES+=("${json_file}")
            CHAMP_LABELS+=("${key}=${fmt_acc}")
            CHAMP_ACCS+=("${val_acc}")
            ;;
        regressed)
            ACC_COL="${C_YELLOW}"
            old_pct="$(echo "${old_dir_f1}" | "${PYTHON}" -c "import sys; v=float(sys.stdin.read()); print(f'{v*100:.1f}%')" 2>/dev/null || echo "${old_dir_f1}")"
            new_pct="$(echo "${new_dir_f1}" | "${PYTHON}" -c "import sys; v=float(sys.stdin.read()); print(f'{v*100:.1f}%')" 2>/dev/null || echo "${new_dir_f1}")"
            BADGE="${C_YELLOW}⚠ guarded (dir_F1: ${old_pct}→${new_pct})${C_RESET}"
            GUARDED_LABELS+=("${key}")
            ;;
        below)
            ACC_COL="${C_RED}"
            BADGE="${C_DIM}✗ below threshold${C_RESET}"
            ;;
        *)
            ACC_COL="${C_DIM}"
            BADGE="${C_DIM}? unknown${C_RESET}"
            ;;
    esac

    if [[ "${model_type}" == "master" ]]; then
        printf "  %-12s %-10s ${ACC_COL}%-10s${C_RESET} %-8s %-8s %-8s %-8s %-8s %-4s %-8s %b  %b\n" \
            "${key}" "${model_type}" "${fmt_acc}" \
            "${fmt_lp}" "${fmt_lr}" "${fmt_sp}" "${fmt_sr}" \
            "${epoch_str}" "${tf}" "${kb}KB" "${BADGE}" "${GIT_TAG}"
        [[ -n "${fmt_f1}" ]] && printf "  ${C_DIM}%-12s %-10s F1=%-7s confidence=%-8s  (cols above: safe_P safe_R risky_P risky_R)${C_RESET}\n" \
            "" "" "${fmt_f1}" "${confidence}"
    else
        printf "  %-12s %-10s ${ACC_COL}%-10s${C_RESET} %-8s %-8s %-8s %-8s %-8s %-4s %-8s %b  %b\n" \
            "${key}" "${model_type}" "${fmt_acc}" \
            "${fmt_lp}" "${fmt_lr}" "${fmt_sp}" "${fmt_sr}" \
            "${epoch_str}" "${tf}" "${kb}KB" "${BADGE}" "${GIT_TAG}"
    fi

done <<< "${PARSED_TABLE}"

echo "  ──────────────────────────────────────────────────────────────────────────────────────────────"
echo -e "${C_DIM}  Green = meets threshold + improved  Yellow = meets threshold but regressed (guarded)${C_RESET}"
echo -e "${C_DIM}  Per-asset: LONG_P/R SHORT_P/R  |  Master: SAFE_P/R RISKY_P/R  |  EPOCH = best/total${C_RESET}"
echo ""

if [[ ${#GUARDED_LABELS[@]} -gt 0 ]]; then
    GUARDED_STR="$(IFS=', '; echo "${GUARDED_LABELS[*]}")"
    warn "Champion guard blocked ${#GUARDED_LABELS[@]} model(s): ${GUARDED_STR}"
    info "These models met the accuracy threshold but had lower (long_F1+short_F1)/2 than the champion."
    info "Use --no-champion-guard to promote anyway."
    echo ""
fi

if [[ ${#CHAMP_PT_FILES[@]} -eq 0 ]]; then
    warn "No models selected for promotion."
    info "Options: --min-accuracy 0.45 | --no-champion-guard | --optimize-labels | --full-pipeline"
    echo ""; exit 0
fi

SUMMARY="$(IFS=','; echo "${CHAMP_LABELS[*]}")"
info "${#CHAMP_PT_FILES[@]} model(s) selected as champions:"
echo -e "  ${C_BOLD}${SUMMARY}${C_RESET}"
echo ""

if [[ ${#CHAMP_ACCS[@]} -gt 0 ]]; then
    AVG_ACC="$("${PYTHON}" - <<PYEOF
raw = """${CHAMP_ACCS[*]}"""
accs = [float(x) for x in raw.split() if x]
if not accs:
    print("0.0")
else:
    avg = sum(accs) / len(accs)
    print(f"{avg * 100.0 if avg <= 1.0 else avg:.1f}")
PYEOF
)"
    if "${PYTHON}" -c "import sys; sys.exit(0 if float('${AVG_ACC}') >= 60 else 1)" 2>/dev/null; then
        echo -e "  ${C_GREEN}✓ Avg champion accuracy ${AVG_ACC}% — viable for live CNN gating${C_RESET}"
    elif "${PYTHON}" -c "import sys; sys.exit(0 if float('${AVG_ACC}') >= 50 else 1)" 2>/dev/null; then
        echo -e "  ${C_YELLOW}⚠ Avg champion accuracy ${AVG_ACC}% — marginal, consider tuning${C_RESET}"
    else
        echo -e "  ${C_RED}✗ Avg champion accuracy ${AVG_ACC}% — review label quality${C_RESET}"
    fi
    echo ""
fi

# =============================================================================
# GIT PROMOTION
# =============================================================================

if [[ "${OPT_NO_PROMOTE}" == true ]]; then
    section "Promotion Skipped  (--no-promote)"
    info "To promote manually:"
    echo ""
    for i in "${!CHAMP_PT_FILES[@]}"; do
        pt_rel="${CHAMP_PT_FILES[$i]#${PROJECT_ROOT}/}"
        jf_rel="${CHAMP_JSON_FILES[$i]#${PROJECT_ROOT}/}"
        info "  git add -f ${pt_rel} ${jf_rel}"
    done
    info "  git commit -m \"model: promote champions — ${SUMMARY}\""
    echo ""
else
    section "Promoting Champions to Git"
    echo ""

    if ! git rev-parse --git-dir &>/dev/null; then
        warn "Not inside a git repository — skipping promotion."
    else
        for i in "${!CHAMP_PT_FILES[@]}"; do
            pt_rel="${CHAMP_PT_FILES[$i]#${PROJECT_ROOT}/}"
            jf_rel="${CHAMP_JSON_FILES[$i]#${PROJECT_ROOT}/}"
            echo -e "  ${C_CYAN}+${C_RESET} ${pt_rel}"
            git add -f "${CHAMP_PT_FILES[$i]}"
            echo -e "  ${C_CYAN}+${C_RESET} ${jf_rel}"
            git add -f "${CHAMP_JSON_FILES[$i]}"
            for asset_key in "${OPT_ASSETS[@]}"; do
                lp="${MODELS_DIR}/label_params_${asset_key}.json"
                if [[ -f "${lp}" ]]; then
                    git add -f "${lp}" 2>/dev/null || true
                fi
            done
        done
        echo ""

        if git diff --cached --quiet; then
            info "Nothing new to commit — champions are already up to date in git."
        else
            MODE_TAG="[${ACTIVE_MODE}]"
            COMMIT_MSG="model: champion CNN checkpoint(s) ${MODE_TAG} — ${SUMMARY}"
            COMMIT_BODY=""
            while IFS=$'\t' read -r key model_type val_acc trained epoch_str tf kb pt_file json_file \
                guard_action _fmt_acc _fmt_lp _fmt_lr _fmt_sp _fmt_sr _fmt_f1 _confidence new_dir_f1 old_dir_f1; do
                if [[ "${guard_action}" == "promote" || "${guard_action}" == "new" ]]; then
                    COMMIT_BODY+="  ${key}: val_acc=${val_acc}  epochs=${epoch_str}  tf=${tf}  trained=${trained}"$'\n'
                fi
            done <<< "${PARSED_TABLE}"
            git commit -m "${COMMIT_MSG}" -m "${COMMIT_BODY}"
            echo ""
            ok "Committed: ${COMMIT_MSG}"
            echo ""
            echo -e "${C_DIM}  Run 'git push' to publish to the remote.${C_RESET}"
        fi
    fi
fi

# =============================================================================
# FINAL SUMMARY
# =============================================================================

PIPELINE_END=$(date +%s)
PIPELINE_ELAPSED=$(( PIPELINE_END - PIPELINE_START ))

section "Pipeline Complete  [${ACTIVE_MODE}]"
printf "  Total    : %dm %02ds\n"  $(( PIPELINE_ELAPSED / 60 )) $(( PIPELINE_ELAPSED % 60 ))

if [[ "${OPT_FULL_PIPELINE}" == true ]]; then
    printf "  Stages   : prefetch → label-opt (%d trials) → hyper-opt (%d trials) → Tier-1 → Tier-2 → promote\n" \
        "${OPT_LABEL_TRIALS}" "${OPT_HYPER_TRIALS}"
elif [[ "${OPT_MASTER_ONLY}" != true ]]; then
    if [[ "${OPT_OPTIMIZE_LABELS}" == true ]]; then
        printf "  Tier 1   : %dm %02ds  per-asset (%d assets) + label-opt (%d trials)\n" \
            $(( TIER1_ELAPSED / 60 )) $(( TIER1_ELAPSED % 60 )) "${#OPT_ASSETS[@]}" "${OPT_LABEL_TRIALS}"
    else
        printf "  Tier 1   : %dm %02ds  per-asset (%d assets)\n" \
            $(( TIER1_ELAPSED / 60 )) $(( TIER1_ELAPSED % 60 )) "${#OPT_ASSETS[@]}"
    fi
    printf "  Tier 2   : %dm %02ds  master\n"  $(( TIER2_ELAPSED / 60 )) $(( TIER2_ELAPSED % 60 ))
else
    printf "  Tier 1   : skipped (--master-only)\n"
    printf "  Tier 2   : %dm %02ds  master\n"  $(( TIER2_ELAPSED / 60 )) $(( TIER2_ELAPSED % 60 ))
fi

MODEL_COUNT=$(find "${MODELS_DIR}" -name "cnn_*.pt" 2>/dev/null | wc -l | tr -d ' ')
LABEL_COUNT=$(find "${MODELS_DIR}" -name "label_params_*.json" 2>/dev/null | wc -l | tr -d ' ')
printf "  Models   : %s .pt files in %s\n" "${MODEL_COUNT}" "${MODELS_DIR}"
[[ $LABEL_COUNT -gt 0 ]] && printf "  LabelOpt : %s cached label_params_*.json files\n" "${LABEL_COUNT}"
[[ -n "${LOG_FILE}" && -f "${LOG_FILE}" ]] && \
    printf "  Log file : %s  (%s)\n" "${LOG_FILE}" "$(du -h "${LOG_FILE}" 2>/dev/null | cut -f1)"
echo ""

echo -e "${C_DIM}  Champion models are in ${MODELS_DIR}/"
echo -e "  The trading system loads them automatically on startup."
echo -e "  If no .pt file exists for an asset, CNN gating is silently disabled"
echo -e "  for that asset and it falls back to the rule-based EMA pipeline.${C_RESET}"
echo ""

echo -e "${C_BOLD}  Next steps:${C_RESET}"
echo -e "${C_DIM}    1. Review per-class precision above — long/short P > 40% is the key${C_RESET}"
echo -e "${C_DIM}    2. Deploy: restart the bot — CNN gate activates when .pt files exist${C_RESET}"
echo -e "${C_DIM}    3. Monitor: ml.enabled in config controls the gate (true = on)${C_RESET}"
echo -e "${C_DIM}    4. A/B test: toggle ml.enabled and compare PnL over 48h windows${C_RESET}"
echo -e "${C_DIM}    5. Retrain: re-run this script — new vs old comparison prints automatically${C_RESET}"
if [[ "${OPT_FULL_PIPELINE}" == true || "${OPT_OPTIMIZE_LABELS}" == true ]]; then
    echo -e "${C_DIM}    6. Force re-optimization: add --force-label-opt to ignore 7-day cache${C_RESET}"
    echo -e "${C_DIM}    7. Tighten promotion gate: --min-delta-f1 0.01 (default 0.005)${C_RESET}"
fi
if [[ -n "${LOG_FILE}" && -f "${LOG_FILE}" ]]; then
    echo ""
    echo -e "  ${C_BOLD}Full log:${C_RESET} ${LOG_FILE}"
    echo -e "${C_DIM}    View  : less -R ${LOG_FILE}${C_RESET}"
    echo -e "${C_DIM}    Plain : cat ${LOG_FILE} | sed 's/\x1b\[[0-9;]*m//g' > clean.log${C_RESET}"
fi
echo ""
