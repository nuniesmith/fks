#!/usr/bin/env bash
# chmod +x this file
set -euo pipefail

# =============================================================================
# gen-proto.sh — Generate gRPC stubs from FKS Protocol Buffer definitions
# =============================================================================
#
# Generates Python gRPC stubs from ALL proto files:
#   proto/fks/common/v1/common.proto
#   proto/fks/janus/v1/janus.proto
#   proto/fks/forward/v1/forward.proto
#   proto/fks/execution/v1/execution.proto
#   proto/fks/data/v1/data.proto
#   proto/fks/cns/v1/cns.proto
#   proto/fks/neuromorphic/distributed/v1/distributed.proto
#   proto/fks/signals/v1/signals.proto
#   proto/fks/paper_trading/v1/paper_trading.proto
#   proto/fks/feedback/v1/feedback.proto
#
# Python output goes to:
#   src/ruby/src/lib/integrations/proto_gen/
#     ├── common_pb2.py
#     ├── common_pb2_grpc.py
#     ├── janus_pb2.py
#     ├── janus_pb2_grpc.py
#     ├── forward_pb2.py
#     ├── forward_pb2_grpc.py
#     ├── execution_pb2.py
#     ├── execution_pb2_grpc.py
#     ├── data_pb2.py
#     ├── data_pb2_grpc.py
#     ├── cns_pb2.py
#     ├── cns_pb2_grpc.py
#     ├── distributed_pb2.py
#     ├── distributed_pb2_grpc.py
#     ├── signals_pb2.py
#     ├── signals_pb2_grpc.py
#     ├── paper_trading_pb2.py
#     ├── paper_trading_pb2_grpc.py
#     └── __init__.py
#
# The include root passed to protoc is proto/ so that cross-file imports
# between proto definitions resolve correctly.  protoc therefore generates
# a nested directory tree under a temporary staging area.  A post-processing
# step copies and flattens the *_pb2.py / *_pb2_grpc.py files into
# proto_gen/ so they can be imported with simple names:
#   import signals_pb2
#   import signals_pb2_grpc
#
# Optionally also runs `buf generate` for Go stubs if `buf` is in PATH.
#
# Requirements:
#   pip install grpcio-tools
#
# Usage:
#   bash scripts/gen-proto.sh              # generate Python stubs (+ Go if buf available)
#   bash scripts/gen-proto.sh --python     # force Python only, skip buf check
#   bash scripts/gen-proto.sh --buf-only   # only run buf generate (requires buf in PATH)
#   bash scripts/gen-proto.sh --help       # show this help
#
# =============================================================================

# ---------------------------------------------------------------------------
# Colours & logging helpers
# ---------------------------------------------------------------------------

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

log()    { echo -e "${CYAN}[proto]${NC} $*"; }
ok()     { echo -e "${GREEN}[  ✓ ]${NC} $*"; }
warn()   { echo -e "${YELLOW}[ warn]${NC} $*"; }
err()    { echo -e "${RED}[ fail]${NC} $*" >&2; }
section(){ echo -e "\n${BOLD}${CYAN}── $* ──${NC}"; }

# ---------------------------------------------------------------------------
# Usage
# ---------------------------------------------------------------------------

usage() {
    echo ""
    echo -e "${BOLD}gen-proto.sh${NC} — FKS gRPC stub generator"
    echo ""
    echo "Generates Python gRPC stubs from all FKS proto definitions"
    echo "using grpcio-tools (python3 -m grpc_tools.protoc)."
    echo ""
    echo -e "${BOLD}Usage:${NC}"
    echo "  bash scripts/gen-proto.sh              Generate Python stubs (+ Go via buf if available)"
    echo "  bash scripts/gen-proto.sh --python     Python only, skip buf generate"
    echo "  bash scripts/gen-proto.sh --buf-only   Run buf generate only (requires buf in PATH)"
    echo "  bash scripts/gen-proto.sh --help       Show this help message"
    echo ""
    echo -e "${BOLD}Requirements:${NC}"
    echo "  pip install grpcio-tools"
    echo ""
    echo -e "${BOLD}Proto files:${NC}"
    echo "  proto/fks/common/v1/common.proto"
    echo "  proto/fks/janus/v1/janus.proto"
    echo "  proto/fks/forward/v1/forward.proto"
    echo "  proto/fks/execution/v1/execution.proto"
    echo "  proto/fks/data/v1/data.proto"
    echo "  proto/fks/cns/v1/cns.proto"
    echo "  proto/fks/neuromorphic/distributed/v1/distributed.proto"
    echo "  proto/fks/signals/v1/signals.proto"
    echo "  proto/fks/paper_trading/v1/paper_trading.proto"
    echo "  proto/fks/feedback/v1/feedback.proto"
    echo ""
    echo -e "${BOLD}Output:${NC}"
    echo "  src/ruby/src/lib/integrations/proto_gen/"
    echo "    ├── {name}_pb2.py        — protobuf message classes"
    echo "    ├── {name}_pb2_grpc.py   — gRPC service stubs"
    echo "    └── __init__.py          — convenience re-exports"
    echo ""
    echo "  Files are flattened from the nested protoc output so they can be"
    echo "  imported as:  import signals_pb2 / import signals_pb2_grpc"
    echo ""
}

# ---------------------------------------------------------------------------
# Find repo root (directory containing buf.work.yaml)
# ---------------------------------------------------------------------------

find_repo_root() {
    # Walk up from the directory containing this script until we find
    # buf.work.yaml, which marks the repository root.
    local dir
    dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

    while [[ "$dir" != "/" ]]; do
        if [[ -f "$dir/buf.work.yaml" ]]; then
            echo "$dir"
            return 0
        fi
        dir="$(dirname "$dir")"
    done

    err "Could not find repo root (no buf.work.yaml found walking up from ${BASH_SOURCE[0]})"
    return 1
}

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

MODE="auto"   # auto | python | buf-only

for arg in "$@"; do
    case "$arg" in
        --python)     MODE="python" ;;
        --buf-only)   MODE="buf-only" ;;
        --help|-h)    usage; exit 0 ;;
        *)
            err "Unknown option: $arg"
            usage
            exit 1
            ;;
    esac
done

# ---------------------------------------------------------------------------
# Resolve paths
# ---------------------------------------------------------------------------

section "FKS Proto Generator"

log "Locating repository root..."
REPO_ROOT="$(find_repo_root)"
log "  Repo root : ${REPO_ROOT}"

PROTO_ROOT="${REPO_ROOT}/proto"
# The Python "Ruby" service that consumed these stubs was removed (janus is the
# platform — see docs/architecture/RUST_MIGRATION.md). The Rust fks-proto crate
# (src/proto/) compiles the protos itself via build.rs and does NOT need this
# script. Python stub generation now writes to a throwaway build dir instead of
# resurrecting src/ruby; repoint GEN_PYTHON_OUT if you still need the stubs.
GEN_PYTHON_OUT="${GEN_PYTHON_OUT:-${REPO_ROOT}/build/proto_gen_python}"

log "  Proto root: ${PROTO_ROOT}"
log "  Python out: ${GEN_PYTHON_OUT}"

# ---------------------------------------------------------------------------
# Proto file registry
# ---------------------------------------------------------------------------
# Each entry is a relative path from PROTO_ROOT.
# Order matters: dependencies should come before dependents so that if
# cross-file imports are added in the future the generation still works
# in a single pass.

PROTO_FILES=(
    "fks/common/v1/common.proto"
    "fks/janus/v1/janus.proto"
    "fks/forward/v1/forward.proto"
    "fks/execution/v1/execution.proto"
    "fks/data/v1/data.proto"
    "fks/cns/v1/cns.proto"
    "fks/neuromorphic/distributed/v1/distributed.proto"
    "fks/signals/v1/signals.proto"
    "fks/paper_trading/v1/paper_trading.proto"
    "fks/feedback/v1/feedback.proto"
)

# Derived: base names (without .proto extension) used for the flat filenames
# e.g. "fks/signals/v1/signals.proto" → "signals"
PROTO_BASENAMES=()
for pf in "${PROTO_FILES[@]}"; do
    bn="$(basename "$pf" .proto)"
    PROTO_BASENAMES+=("$bn")
done

# Verify all proto files exist
log "Verifying proto files..."
ALL_EXIST=true
for pf in "${PROTO_FILES[@]}"; do
    full="${PROTO_ROOT}/${pf}"
    if [[ ! -f "$full" ]]; then
        err "Proto file not found: ${full}"
        ALL_EXIST=false
    fi
done
if [[ "$ALL_EXIST" != "true" ]]; then
    err "One or more proto files are missing. Aborting."
    exit 1
fi
ok "All ${#PROTO_FILES[@]} proto files found."

# ---------------------------------------------------------------------------
# Python stub generation
# ---------------------------------------------------------------------------

run_python_gen() {
    section "Python gRPC stub generation"

    # Verify grpcio-tools is available
    if ! python3 -m grpc_tools.protoc --version >/dev/null 2>&1; then
        err "grpcio-tools is not installed or not importable."
        err "Install it with:  pip install grpcio-tools"
        return 1
    fi

    local grpc_version
    grpc_version=$(python3 -m grpc_tools.protoc --version 2>&1 | head -1 || echo "unknown")
    log "grpcio-tools: ${grpc_version}"

    # Create output directory if it doesn't exist
    if [[ ! -d "$GEN_PYTHON_OUT" ]]; then
        log "Creating output directory: ${GEN_PYTHON_OUT}"
        mkdir -p "$GEN_PYTHON_OUT"
    else
        log "Output directory exists: ${GEN_PYTHON_OUT}"
    fi

    # ------------------------------------------------------------------
    # Strategy: use proto/ as the include root (-I) so that cross-file
    # imports like `import "fks/common/v1/common.proto"` resolve.
    # protoc will therefore produce a nested directory tree under the
    # output dir:
    #   <staging>/fks/common/v1/common_pb2.py
    #   <staging>/fks/signals/v1/signals_pb2.py
    #   ...
    #
    # We generate into a temporary staging directory, then copy and
    # flatten the _pb2.py / _pb2_grpc.py files into GEN_PYTHON_OUT.
    # ------------------------------------------------------------------

    local STAGING_DIR
    STAGING_DIR="$(mktemp -d)"
    log "Staging directory: ${STAGING_DIR}"

    # Run protoc once with all proto files
    log "Running grpc_tools.protoc..."
    log "  -I \"${PROTO_ROOT}\"  (include root for cross-file imports)"
    log "  --python_out=\"${STAGING_DIR}\""
    log "  --grpc_python_out=\"${STAGING_DIR}\""
    log "  Proto files: ${#PROTO_FILES[@]} total"
    echo ""

    if ! (cd "${PROTO_ROOT}" && python3 -m grpc_tools.protoc \
        -I "." \
        --python_out="${STAGING_DIR}" \
        --grpc_python_out="${STAGING_DIR}" \
        "${PROTO_FILES[@]}"); then
        err "grpc_tools.protoc failed — see output above for details."
        rm -rf "${STAGING_DIR}"
        return 1
    fi

    ok "protoc succeeded — flattening generated files..."

    # ------------------------------------------------------------------
    # Flatten: copy each generated file from the nested staging tree
    # into GEN_PYTHON_OUT with a flat name.
    # ------------------------------------------------------------------

    local copied=0
    for pf in "${PROTO_FILES[@]}"; do
        local bn
        bn="$(basename "$pf" .proto)"
        local proto_dir
        proto_dir="$(dirname "$pf")"

        local pb2_src="${STAGING_DIR}/${proto_dir}/${bn}_pb2.py"
        local grpc_src="${STAGING_DIR}/${proto_dir}/${bn}_pb2_grpc.py"
        local pb2_dst="${GEN_PYTHON_OUT}/${bn}_pb2.py"
        local grpc_dst="${GEN_PYTHON_OUT}/${bn}_pb2_grpc.py"

        if [[ -f "$pb2_src" ]]; then
            cp "$pb2_src" "$pb2_dst"
            ((copied++))
        else
            warn "Expected file not found: ${pb2_src}"
        fi

        if [[ -f "$grpc_src" ]]; then
            cp "$grpc_src" "$grpc_dst"
            ((copied++))
        else
            warn "Expected file not found: ${grpc_src}"
        fi
    done

    log "Copied ${copied} files into ${GEN_PYTHON_OUT}"

    # ------------------------------------------------------------------
    # Post-process: fix imports in the generated files.
    # protoc with -I proto/ generates imports like:
    #   from fks.common.v1 import common_pb2 as ...
    # We need to rewrite those to flat imports:
    #   import common_pb2 as ...
    # ------------------------------------------------------------------

    log "Post-processing imports for flat module layout..."

    for pf in "${PROTO_FILES[@]}"; do
        local bn
        bn="$(basename "$pf" .proto)"

        for suffix in "_pb2.py" "_pb2_grpc.py"; do
            local target="${GEN_PYTHON_OUT}/${bn}${suffix}"
            if [[ -f "$target" ]]; then
                # Rewrite "from fks.<pkg>.<ver> import <name>_pb2" →
                #          "import <name>_pb2"
                # The [a-z_0-9.]* greedily matches everything between
                # "fks." and " import ", handling any nesting depth:
                #   fks.common.v1           → common_pb2
                #   fks.paper_trading.v1    → paper_trading_pb2
                #   fks.neuromorphic.distributed.v1 → distributed_pb2
                sed -i \
                    's/^from fks\.[a-z_0-9.]* import \([a-z_]*_pb2\)/import \1/' \
                    "$target"
            fi
        done
    done

    ok "Import rewriting complete."

    # Clean up staging
    rm -rf "${STAGING_DIR}"
    log "Cleaned up staging directory."

    # ------------------------------------------------------------------
    # Write __init__.py
    # ------------------------------------------------------------------

    local init_py="${GEN_PYTHON_OUT}/__init__.py"
    log "Writing ${init_py}..."

    cat > "$init_py" <<'INIT'
# Generated package — do not edit by hand.
# Run scripts/gen-proto.sh to regenerate.
#
# This directory contains Python gRPC stubs generated from all FKS proto
# definitions under proto/fks/.
#
# Proto sources:
#   proto/fks/common/v1/common.proto
#   proto/fks/janus/v1/janus.proto
#   proto/fks/forward/v1/forward.proto
#   proto/fks/execution/v1/execution.proto
#   proto/fks/data/v1/data.proto
#   proto/fks/cns/v1/cns.proto
#   proto/fks/neuromorphic/distributed/v1/distributed.proto
#   proto/fks/signals/v1/signals.proto
#   proto/fks/paper_trading/v1/paper_trading.proto
#
# Contents after generation (flat layout):
#   {name}_pb2.py       — protobuf message classes
#   {name}_pb2_grpc.py  — gRPC service stubs (client + server)
#
# To regenerate:
#   bash scripts/gen-proto.sh
#
# Requirements:
#   pip install grpcio grpcio-tools

# ── Re-export all generated modules for convenient imports ──
# Usage:
#   from proto_gen import signals_pb2, signals_pb2_grpc
#   from proto_gen import common_pb2

# Common types (shared across services)
from . import common_pb2          # noqa: F401
from . import common_pb2_grpc     # noqa: F401

# Janus AI service
from . import janus_pb2           # noqa: F401
from . import janus_pb2_grpc      # noqa: F401

# Forward service
from . import forward_pb2         # noqa: F401
from . import forward_pb2_grpc    # noqa: F401

# Execution service
from . import execution_pb2       # noqa: F401
from . import execution_pb2_grpc  # noqa: F401

# Data service
from . import data_pb2            # noqa: F401
from . import data_pb2_grpc       # noqa: F401

# CNS service
from . import cns_pb2             # noqa: F401
from . import cns_pb2_grpc        # noqa: F401

# Neuromorphic distributed service
from . import distributed_pb2       # noqa: F401
from . import distributed_pb2_grpc  # noqa: F401

# Signals / inference service
from . import signals_pb2         # noqa: F401
from . import signals_pb2_grpc    # noqa: F401

# Paper trading service
from . import paper_trading_pb2       # noqa: F401
from . import paper_trading_pb2_grpc  # noqa: F401

# Position feedback service
from . import feedback_pb2            # noqa: F401
from . import feedback_pb2_grpc       # noqa: F401

__all__ = [
    "common_pb2",
    "common_pb2_grpc",
    "janus_pb2",
    "janus_pb2_grpc",
    "forward_pb2",
    "forward_pb2_grpc",
    "execution_pb2",
    "execution_pb2_grpc",
    "data_pb2",
    "data_pb2_grpc",
    "cns_pb2",
    "cns_pb2_grpc",
    "distributed_pb2",
    "distributed_pb2_grpc",
    "signals_pb2",
    "signals_pb2_grpc",
    "paper_trading_pb2",
    "paper_trading_pb2_grpc",
    "feedback_pb2",
    "feedback_pb2_grpc",
]
INIT

    ok "Wrote ${init_py}"

    # ------------------------------------------------------------------
    # Write .gitignore
    # ------------------------------------------------------------------

    local gitignore="${GEN_PYTHON_OUT}/.gitignore"
    log "Writing ${gitignore}..."

    cat > "$gitignore" <<'GITIGNORE'
# Generated gRPC stubs — do not commit.
# Run scripts/gen-proto.sh to regenerate.

# Common
common_pb2.py
common_pb2_grpc.py

# Janus
janus_pb2.py
janus_pb2_grpc.py

# Forward
forward_pb2.py
forward_pb2_grpc.py

# Execution
execution_pb2.py
execution_pb2_grpc.py

# Data
data_pb2.py
data_pb2_grpc.py

# CNS
cns_pb2.py
cns_pb2_grpc.py

# Neuromorphic distributed
distributed_pb2.py
distributed_pb2_grpc.py

# Signals
signals_pb2.py
signals_pb2_grpc.py

# Paper trading
paper_trading_pb2.py
paper_trading_pb2_grpc.py

# Position feedback
feedback_pb2.py
feedback_pb2_grpc.py
GITIGNORE

    ok "Wrote ${gitignore}"

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    echo ""
    ok "Python stubs written to: ${GEN_PYTHON_OUT}"

    # List generated files for confirmation
    echo ""
    log "Generated files:"
    find "${GEN_PYTHON_OUT}" -maxdepth 1 -name "*.py" | sort | while read -r f; do
        local rel="${f#"${REPO_ROOT}/"}"
        echo -e "    ${DIM}${rel}${NC}"
    done
    echo ""

    return 0
}

# ---------------------------------------------------------------------------
# buf generate (Go + other language stubs)
# ---------------------------------------------------------------------------

run_buf_gen() {
    section "buf generate (Go / multi-language stubs)"

    if ! command -v buf >/dev/null 2>&1; then
        warn "buf is not in PATH — skipping buf generate."
        warn "Install buf from: https://buf.build/docs/installation"
        return 0
    fi

    local buf_version
    buf_version=$(buf --version 2>&1 | head -1 || echo "unknown")
    log "buf version: ${buf_version}"
    log "Running: buf generate (from ${PROTO_ROOT})"
    echo ""

    if ! buf generate --error-format text 2>&1; then
        err "buf generate failed — see output above."
        return 1
    fi

    echo ""
    ok "buf generate completed successfully."
    return 0
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

PYTHON_FAILED=0
BUF_FAILED=0

case "$MODE" in
    python)
        run_python_gen || PYTHON_FAILED=1
        ;;
    buf-only)
        if ! command -v buf >/dev/null 2>&1; then
            err "buf is not in PATH. Cannot run --buf-only."
            err "Install buf from: https://buf.build/docs/installation"
            exit 1
        fi
        # Change to PROTO_ROOT so buf.yaml is picked up correctly
        (cd "${PROTO_ROOT}" && run_buf_gen) || BUF_FAILED=1
        ;;
    auto)
        run_python_gen || PYTHON_FAILED=1

        if [[ "$PYTHON_FAILED" -eq 0 ]]; then
            # buf generate is optional — only run if buf is available
            if command -v buf >/dev/null 2>&1; then
                (cd "${PROTO_ROOT}" && run_buf_gen) || BUF_FAILED=1
            else
                warn "buf not found in PATH — skipping Go stub generation."
                warn "Install buf to also generate Go stubs: https://buf.build/docs/installation"
            fi
        fi
        ;;
esac

# ---------------------------------------------------------------------------
# Final status
# ---------------------------------------------------------------------------

section "Result"

if [[ "$PYTHON_FAILED" -ne 0 ]]; then
    err "Python stub generation failed."
    err "Make sure grpcio-tools is installed:  pip install grpcio-tools"
    exit 1
fi

if [[ "$BUF_FAILED" -ne 0 ]]; then
    err "buf generate failed (Go stubs not written)."
    exit 1
fi

ok "All done! Python gRPC stubs are at:"
echo -e "    ${BOLD}${GEN_PYTHON_OUT}${NC}"
echo ""
echo -e "    Modules: ${BOLD}${#PROTO_BASENAMES[@]}${NC} proto files → ${BOLD}$((${#PROTO_BASENAMES[@]} * 2))${NC} Python stubs"
echo -e "    Import :  ${DIM}from proto_gen import signals_pb2, common_pb2${NC}"
echo ""

exit 0
