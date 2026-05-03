#!/usr/bin/env bash
# ╔══════════════════════════════════════════════════════════════════╗
# ║      nuniesmith/fks — Overnight Ecosystem Analyzer Launcher      ║
# ╚══════════════════════════════════════════════════════════════════╝
#
# REPOS ANALYSED
# ──────────────
#   nuniesmith/fks         Unified monorepo: Janus (Rust) + Ruby (Python)
#                          + infrastructure, monitoring, proto, docs
#   nuniesmith/rustcode    AI backend: LLM proxy (Grok/Ollama), RAG,
#                          code audit, async task agent
#   nuniesmith/janus       Standalone Janus source mirror (src-code only)
#   nuniesmith/ruby        Standalone Ruby source mirror  (src-code only)
#   nuniesmith/fks-web     Web frontend (src-code only)
#   nuniesmith/fks-kotlin  KMP mobile monitoring app (src-code only)
#
# LLM BACKENDS
# ────────────
#   Default  — calls xAI directly (requires XAI_API_KEY)
#   Rustcode — routes through your local rustcode proxy
#              set RUSTCODE_URL=http://localhost:3500
#              set RUSTCODE_API_KEY=<your RC_PROXY_API_KEYS token>
#
# ROLLING CACHE
# ─────────────
#   Stored under  <fks_clone>/.rustcode/analyzer/  (auto-detected)
#   or set        FKS_CACHE_DIR=/path/to/cache
#
#   Files whose GitHub blob SHA is unchanged since the last run are served
#   from cache — no LLM call made. Only new or modified files hit the API.
#   Syntheses are also cached per unique set of constituent blob SHAs.
#   Each run is archived under .rustcode/analyzer/runs/<timestamp>/.
#
# USAGE
# ─────
#   ./run_analysis.sh                          # analyse nuniesmith/fks only
#   ./run_analysis.sh --all-repos              # full ecosystem overnight sweep
#   ./run_analysis.sh --repos fks rustcode     # specific repos (short names ok)
#   ./run_analysis.sh --dry-run                # list files + cache status, no API calls
#   ./run_analysis.sh --resume                 # continue interrupted run
#   ./run_analysis.sh --branch develop         # branch override
#   ./run_analysis.sh --concurrency 8          # more parallel requests
#
#   # Cache commands
#   ./run_analysis.sh --cache-info             # show cache stats and exit
#   ./run_analysis.sh --cache-info --all-repos # stats per-repo
#   ./run_analysis.sh --no-cache               # ignore cache, full re-analysis
#   ./run_analysis.sh --clear-cache fks        # wipe fks cache entry, re-run fresh
#   ./run_analysis.sh --prune-cache            # remove old archives + orphaned files
#   ./run_analysis.sh --cache-dir /my/path     # override cache location
#
# ENVIRONMENT
# ───────────
#   XAI_API_KEY       xAI API key        (required if not using rustcode proxy)
#   RUSTCODE_URL      rustcode base URL  (optional, e.g. http://localhost:3500)
#   RUSTCODE_API_KEY  rustcode bearer token (optional, for auth)
#   GITHUB_TOKEN      GitHub PAT         (optional — 5 000 req/hr vs 60)
#   FKS_CACHE_DIR     Override cache dir (optional)

set -euo pipefail

# ─── Config ──────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${SCRIPT_DIR}/.venv"
REPORT_DIR="${SCRIPT_DIR}/reports"
LOG_FILE="${REPORT_DIR}/run_$(date +%Y%m%d_%H%M%S).log"

# Repo short-name → full slug mapping (for convenience)
declare -A REPO_MAP=(
    [fks]="nuniesmith/fks"
    [rustcode]="nuniesmith/rustcode"
    [janus]="nuniesmith/janus"
    [ruby]="nuniesmith/ruby"
    [fks-web]="nuniesmith/fks-web"
    [fks-kotlin]="nuniesmith/fks-kotlin"
)

# ─── Colour helpers ───────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'
info()    { echo -e "${CYAN}ℹ  $*${NC}"; }
success() { echo -e "${GREEN}✔  $*${NC}"; }
warn()    { echo -e "${YELLOW}⚠  $*${NC}"; }
error()   { echo -e "${RED}✗  $*${NC}" >&2; exit 1; }

# ─── Parse --repos shorthand before forwarding args ───────────────────────────
# We intercept --repos to allow short names (fks, rustcode, etc.)
# All other args are forwarded verbatim to the Python script.
FORWARD_ARGS=()
REPO_ARGS=()
CONSUMING_REPOS=false

for arg in "$@"; do
    if [[ "${CONSUMING_REPOS}" == "true" ]]; then
        if [[ "${arg}" == --* ]]; then
            CONSUMING_REPOS=false
            FORWARD_ARGS+=("${arg}")
        else
            # Expand short names to full slugs if known
            full="${REPO_MAP[$arg]:-$arg}"
            REPO_ARGS+=("${full}")
        fi
    elif [[ "${arg}" == "--repos" ]]; then
        CONSUMING_REPOS=true
    else
        FORWARD_ARGS+=("${arg}")
    fi
done

if [[ ${#REPO_ARGS[@]} -gt 0 ]]; then
    FORWARD_ARGS+=("--repos" "${REPO_ARGS[@]}")
fi

# ─── Banner ───────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}╔════════════════════════════════════════════════════════════╗"
echo -e "║     nuniesmith/fks — Overnight Ecosystem Analyzer          ║"
echo -e "╠════════════════════════════════════════════════════════════╣"
echo -e "║  Repos   : fks · rustcode · janus · ruby · fks-web · kt   ║"
echo -e "║  Backend : xAI Grok  (or rustcode proxy via RUSTCODE_URL)  ║"
echo -e "╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

# ─── Python check ────────────────────────────────────────────────────────────
if ! command -v python3 &>/dev/null; then
    error "python3 not found. Install Python 3.11+ first."
fi
PY_VER=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
PY_MAJOR=$(echo "${PY_VER}" | cut -d. -f1)
PY_MINOR=$(echo "${PY_VER}" | cut -d. -f2)
if [[ "${PY_MAJOR}" -lt 3 ]] || { [[ "${PY_MAJOR}" -eq 3 ]] && [[ "${PY_MINOR}" -lt 11 ]]; }; then
    error "Python 3.11+ required (found ${PY_VER})."
fi
info "Python ${PY_VER} ✓"

# ─── LLM backend check ───────────────────────────────────────────────────────
echo ""
if [[ -n "${RUSTCODE_URL:-}" ]]; then
    success "RUSTCODE_URL=${RUSTCODE_URL} — routing LLM calls through rustcode proxy."
    if [[ -z "${RUSTCODE_API_KEY:-}" ]]; then
        warn "RUSTCODE_API_KEY not set — rustcode auth may fail if RC_PROXY_API_KEYS is configured."
    else
        success "RUSTCODE_API_KEY is set."
    fi
    info "Checking rustcode health …"
    if curl -sf "${RUSTCODE_URL}/healthz" >/dev/null 2>&1; then
        success "rustcode is reachable."
    else
        warn "rustcode did not respond at ${RUSTCODE_URL}/healthz — LLM calls may fail."
    fi
else
    info "No RUSTCODE_URL — using xAI direct."
    if [[ -z "${XAI_API_KEY:-}" ]]; then
        warn "XAI_API_KEY not set!"
        read -rsp "  Enter your xAI API key: " XAI_API_KEY
        export XAI_API_KEY
        echo ""
    fi
    success "XAI_API_KEY is set."
fi

# ─── GitHub token ────────────────────────────────────────────────────────────
if [[ -z "${GITHUB_TOKEN:-}" ]]; then
    warn "GITHUB_TOKEN not set — GitHub rate limit: 60 req/hr (may be slow for 6 repos)."
    warn "Set GITHUB_TOKEN for 5,000 req/hr."
else
    success "GITHUB_TOKEN is set."
fi
echo ""

# ─── Virtual environment ──────────────────────────────────────────────────────
if [[ ! -d "${VENV_DIR}" ]]; then
    info "Creating Python virtual environment …"
    python3 -m venv "${VENV_DIR}"
fi

source "${VENV_DIR}/bin/activate"
info "Installing / upgrading dependencies …"
pip install --quiet --upgrade pip
pip install --quiet httpx
success "Dependencies ready."
echo ""

# ─── Output directory ─────────────────────────────────────────────────────────
mkdir -p "${REPORT_DIR}"

# ─── Resolve cache dir for display ───────────────────────────────────────────
CACHE_DIR_DISPLAY="${FKS_CACHE_DIR:-auto-detect}"
for _fa in "${FORWARD_ARGS[@]:-}"; do
    if [[ "${_fa}" == "--no-cache" ]]; then CACHE_DIR_DISPLAY="DISABLED (--no-cache)"; fi
done

# ─── Detect run mode ──────────────────────────────────────────────────────────
CACHE_ONLY=false
MODE_LABEL="SINGLE REPO — incremental (nuniesmith/fks)"
for _fa in "${FORWARD_ARGS[@]:-}"; do
    case "${_fa}" in
        --cache-info)   CACHE_ONLY=true; MODE_LABEL="CACHE INFO (no analysis)";;
        --prune-cache)  CACHE_ONLY=true; MODE_LABEL="PRUNE CACHE (no analysis)";;
        --clear-cache)  CACHE_ONLY=true; MODE_LABEL="CLEAR CACHE (no analysis)";;
        --all-repos)    MODE_LABEL="FULL ECOSYSTEM SWEEP (all 6 repos)";;
        --repos)        MODE_LABEL="SELECTED REPOS";;
        --dry-run)      MODE_LABEL="DRY RUN (list files + cache status, no API calls)";;
        --no-cache)     MODE_LABEL="SINGLE REPO — FULL RE-ANALYSIS (cache bypassed)";;
    esac
done

info "Output : ${REPORT_DIR}"
info "Log    : ${LOG_FILE}"
info "Cache  : ${CACHE_DIR_DISPLAY}"
info "Mode   : ${MODE_LABEL}"
echo ""

# ─── LLM auth (skip for cache-only commands) ──────────────────────────────────
if [[ "${CACHE_ONLY}" == "false" ]]; then
    if [[ -n "${RUSTCODE_URL:-}" ]]; then
        success "RUSTCODE_URL=${RUSTCODE_URL}"
        [[ -z "${RUSTCODE_API_KEY:-}" ]] \
            && warn "RUSTCODE_API_KEY not set — auth may fail." \
            || success "RUSTCODE_API_KEY is set."
        curl -sf "${RUSTCODE_URL}/healthz" >/dev/null 2>&1 \
            && success "rustcode reachable." \
            || warn "rustcode did not respond at ${RUSTCODE_URL}/healthz"
    else
        if [[ -z "${XAI_API_KEY:-}" ]]; then
            warn "XAI_API_KEY not set!"
            read -rsp "  Enter your xAI API key: " XAI_API_KEY
            export XAI_API_KEY
            echo ""
        fi
        success "XAI_API_KEY is set."
    fi
    if [[ -z "${GITHUB_TOKEN:-}" ]]; then
        warn "GITHUB_TOKEN not set — rate limit: 60 req/hr (may be slow)."
    else
        success "GITHUB_TOKEN is set."
    fi
    echo ""
fi

# ─── Launch ───────────────────────────────────────────────────────────────────
CMD=(
    python3 "${SCRIPT_DIR}/fks_overnight_analyzer.py"
    --output "${REPORT_DIR}"
    "${FORWARD_ARGS[@]}"
)

echo -e "${BOLD}Command:${NC} ${CMD[*]}"
echo ""

"${CMD[@]}" 2>&1 | tee "${LOG_FILE}"

# ─── Post-run (skip for cache-only commands) ──────────────────────────────────
if [[ "${CACHE_ONLY}" == "true" ]]; then
    echo ""; success "Done."; exit 0
fi

echo ""; success "Run complete! Reports in: ${REPORT_DIR}/"; echo ""

# ── Reports ───────────────────────────────────────────────────────────────────
echo -e "${BOLD}📄 Reports:${NC}"
ls -lh "${REPORT_DIR}"/report_*.md 2>/dev/null \
    | awk '{print "   "$NF" ("$5")"}' || true
ls -lh "${REPORT_DIR}"/fks_ecosystem_report_*.md 2>/dev/null \
    | awk '{print "   "$NF" ("$5")"}' || true

# ── Cache stats ───────────────────────────────────────────────────────────────
echo ""; echo -e "${BOLD}📦 Cache:${NC}"
CACHE_REAL="${FKS_CACHE_DIR:-}"
if [[ -z "${CACHE_REAL}" ]]; then
    for candidate in \
        "${SCRIPT_DIR}/.rustcode/analyzer" \
        "${HOME}/fks/.rustcode/analyzer" \
        "${HOME}/repos/fks/.rustcode/analyzer" \
        "${HOME}/dev/fks/.rustcode/analyzer" \
        "${HOME}/projects/fks/.rustcode/analyzer" \
        "${HOME}/code/fks/.rustcode/analyzer" \
        "${HOME}/.fks-analyzer-cache"; do
        if [[ -d "${candidate}" ]]; then
            CACHE_REAL="${candidate}"
            break
        fi
    done
fi

if [[ -n "${CACHE_REAL}" && -d "${CACHE_REAL}" ]]; then
    REV_COUNT=$(find "${CACHE_REAL}/file_reviews" -name "*.json" 2>/dev/null | wc -l | tr -d ' ')
    RUN_COUNT=$(find "${CACHE_REAL}/runs"  -maxdepth 1 -mindepth 1 -type d 2>/dev/null | wc -l | tr -d ' ')
    CACHE_SIZE=$(du -sh "${CACHE_REAL}" 2>/dev/null | cut -f1)
    info "   Path    : ${CACHE_REAL}"
    info "   Reviews : ${REV_COUNT} cached file reviews"
    info "   Runs    : ${RUN_COUNT} archived runs"
    info "   Size    : ${CACHE_SIZE}"
    LATEST_DELTA=$(ls -t "${CACHE_REAL}/delta/"*.json 2>/dev/null | head -1 || true)
    if [[ -n "${LATEST_DELTA}" ]]; then
        SAVED=$(python3 -c "
import json
d = json.load(open('${LATEST_DELTA}'))
s = d.get('stats', {})
print(f\"LLM calls saved: {s.get('llm_calls_saved',0)}  (new: {s.get('new',0)}, modified: {s.get('modified',0)}, unchanged: {s.get('unchanged',0)})\")
" 2>/dev/null || echo "")
        [[ -n "${SAVED}" ]] && success "   ${SAVED}"
    fi
else
    info "   Cache not yet initialised (created automatically on first full run)."
    info "   Default location: <fks_clone>/.rustcode/analyzer/"
fi

# ── Task files ────────────────────────────────────────────────────────────────
echo ""; echo -e "${BOLD}📋 Task files:${NC}"
if ls "${REPORT_DIR}"/fks_tasks_*.json 2>/dev/null | head -1 | grep -q .; then
    ls -lh "${REPORT_DIR}"/fks_tasks_*.json | awk '{print "   "$NF" ("$5")"}'
    echo ""
    LATEST_TASKS=$(ls -t "${REPORT_DIR}"/fks_tasks_*.json 2>/dev/null | head -1)
    if [[ -n "${LATEST_TASKS}" ]]; then
        AUTO=$(python3 -c \
            "import json; d=json.load(open('${LATEST_TASKS}')); print(d['summary']['auto_tasks'])" \
            2>/dev/null || echo "?")
        MANUAL=$(python3 -c \
            "import json; d=json.load(open('${LATEST_TASKS}')); print(d['summary']['manual_tasks'])" \
            2>/dev/null || echo "?")
        success "   Auto tasks   : ${AUTO}  (rustcode task agent ready)"
        warn    "   Manual review: ${MANUAL}  (CRITICAL — inspect before running)"
        echo ""
        if [[ -n "${RUSTCODE_URL:-}" ]]; then
            info "   To execute via running rustcode:"
        else
            info "   To execute (set RUSTCODE_URL first):"
        fi
        echo "      cp ${LATEST_TASKS} <rustcode_dir>/tasks/"
    fi
else
    info "   No task files generated."
fi

echo ""; echo -e "${BOLD}📊 Recent logs:${NC}"
ls -lh "${REPORT_DIR}"/run_*.log 2>/dev/null \
    | tail -3 | awk '{print "   "$NF" ("$5")"}' || true
echo ""
