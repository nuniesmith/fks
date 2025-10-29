#!/usr/bin/env bash
set -euo pipefail

# Build script for fks_api using shared_docker templates
# Usage: ./build.sh [--gpu] [--no-cache] [--tag custom_tag]

SCRIPT_DIR=$(dirname "$0")
WORKSPACE_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || dirname "$SCRIPT_DIR")
SHARED_BUILD_SCRIPT="$SCRIPT_DIR/shared/docker/scripts/build-service.sh"

# Check if shared build script exists
if [[ ! -f "$SHARED_BUILD_SCRIPT" ]]; then
    echo "[error] Shared build script not found at $SHARED_BUILD_SCRIPT"
    echo "       Make sure shared submodules are initialized:"
    echo "       git submodule update --init --recursive"
    exit 1
fi

# Default arguments
ARGS=(
    --runtime python 
    --type api 
    --tag fks_api:latest
)

# Parse additional arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --gpu)
            ARGS+=(--gpu)
            shift
            ;;
        --no-cache)
            ARGS+=(--no-cache)
            shift
            ;;
        --tag)
            # Replace the default tag
            ARGS=("${ARGS[@]/fks_api:latest/$2}")
            if [[ ! " ${ARGS[*]} " =~ " --tag " ]]; then
                ARGS+=(--tag "$2")
            fi
            shift 2
            ;;
        *)
            echo "[warn] Unknown argument: $1"
            shift
            ;;
    esac
done

echo "[info] Building fks_api with shared_docker template"
echo "[info] Arguments: ${ARGS[*]}"

# Run the shared build script
"$SHARED_BUILD_SCRIPT" "$SCRIPT_DIR" "${ARGS[@]}"

echo "[info] fks_api build complete!"
