#!/usr/bin/env bash
# =============================================================================
# RustCode — OpenClaw Image Builder
# =============================================================================
#
# Clones (or updates) the upstream OpenClaw source, builds the base image
# from source using Dockerfile.upstream, then layers RustCode config
# on top via Dockerfile to produce the final openclaw:local image.
#
# Usage:
#   ./docker/openclaw/build.sh                  # full build from source
#   ./docker/openclaw/build.sh --base-only      # build base image only
#   ./docker/openclaw/build.sh --layer-only     # skip base, layer config only
#   ./docker/openclaw/build.sh --pull <image>   # use a pulled image as base
#   ./docker/openclaw/build.sh --clean          # remove cloned source
#   ./docker/openclaw/build.sh --help
#
# Environment:
#   OPENCLAW_REPO_URL     Override upstream git URL
#   OPENCLAW_BASE_TAG     Override base image tag (default: openclaw-base:local)
#   OPENCLAW_TAG          Override final image tag (default: openclaw:local)
#   OPENCLAW_PLATFORM     Override platform (default: linux/amd64)
#   OPENCLAW_EXTENSIONS   Space-separated extension dirs to include
# =============================================================================

set -euo pipefail

# ── Colours ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

info()  { printf "${CYAN}[info]${NC}  %s\n" "$*"; }
ok()    { printf "${GREEN}[ok]${NC}    %s\n" "$*"; }
warn()  { printf "${YELLOW}[warn]${NC}  %s\n" "$*"; }
err()   { printf "${RED}[error]${NC} %s\n" "$*" >&2; }
banner() { printf "\n${BOLD}%s${NC}\n" "$*"; }

# ── Resolve paths ────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
OPENCLAW_DIR="$SCRIPT_DIR"
SOURCE_DIR="$OPENCLAW_DIR/src"
VERSION_FILE="$OPENCLAW_DIR/.openclaw-version"

# ── Defaults ─────────────────────────────────────────────────────────────────
OPENCLAW_REPO_URL="${OPENCLAW_REPO_URL:-https://github.com/openclaw/openclaw.git}"
OPENCLAW_BASE_TAG="${OPENCLAW_BASE_TAG:-openclaw-base:local}"
OPENCLAW_TAG="${OPENCLAW_TAG:-openclaw:local}"
OPENCLAW_PLATFORM="${OPENCLAW_PLATFORM:-linux/amd64}"
OPENCLAW_EXTENSIONS="${OPENCLAW_EXTENSIONS:-}"

BUILD_BASE=true
BUILD_LAYER=true
PULL_IMAGE=""
CLEAN=false

# ── Parse arguments ──────────────────────────────────────────────────────────
while [ $# -gt 0 ]; do
    case "$1" in
        --base-only)   BUILD_LAYER=false;               shift ;;
        --layer-only)  BUILD_BASE=false;                 shift ;;
        --pull)        PULL_IMAGE="$2"; BUILD_BASE=false; shift 2 ;;
        --clean)       CLEAN=true;                       shift ;;
        --tag)         OPENCLAW_TAG="$2";                shift 2 ;;
        --base-tag)    OPENCLAW_BASE_TAG="$2";           shift 2 ;;
        --platform)    OPENCLAW_PLATFORM="$2";           shift 2 ;;
        --repo-url)    OPENCLAW_REPO_URL="$2";           shift 2 ;;
        --help|-h)
            sed -n '2,/^# ====/{ /^# ====/d; s/^# \{0,1\}//; p; }' "$0"
            exit 0
            ;;
        *)
            err "Unknown option: $1"
            exit 1
            ;;
    esac
done

# ── Clean mode ───────────────────────────────────────────────────────────────
if [ "$CLEAN" = true ]; then
    info "Removing cloned OpenClaw source at $SOURCE_DIR ..."
    rm -rf "$SOURCE_DIR"
    ok "Clean complete."
    exit 0
fi

# ── Read pinned version ─────────────────────────────────────────────────────
OPENCLAW_VERSION="main"
if [ -f "$VERSION_FILE" ]; then
    # Strip comments and whitespace
    OPENCLAW_VERSION="$(grep -v '^\s*#' "$VERSION_FILE" | tr -d '[:space:]')"
    if [ -z "$OPENCLAW_VERSION" ]; then
        OPENCLAW_VERSION="main"
    fi
fi

banner "╔══════════════════════════════════════════════════════════════╗"
printf  "${BOLD}║  RustCode — OpenClaw Image Builder                      ║${NC}\n"
banner "╚══════════════════════════════════════════════════════════════╝"
echo
printf "  %-22s %s\n" "Project root:"   "$PROJECT_ROOT"
printf "  %-22s %s\n" "Upstream repo:"  "$OPENCLAW_REPO_URL"
printf "  %-22s %s\n" "Pinned version:" "$OPENCLAW_VERSION"
printf "  %-22s %s\n" "Base image tag:" "$OPENCLAW_BASE_TAG"
printf "  %-22s %s\n" "Final image tag:" "$OPENCLAW_TAG"
printf "  %-22s %s\n" "Platform:"       "$OPENCLAW_PLATFORM"
printf "  %-22s %s\n" "Build base:"     "$BUILD_BASE"
printf "  %-22s %s\n" "Build layer:"    "$BUILD_LAYER"
if [ -n "$PULL_IMAGE" ]; then
    printf "  %-22s %s\n" "Pull base from:" "$PULL_IMAGE"
fi
echo

# ── Step 1: Clone or update OpenClaw source ──────────────────────────────────
if [ "$BUILD_BASE" = true ]; then
    banner "Step 1/3: Fetching OpenClaw source ..."

    if [ -d "$SOURCE_DIR/.git" ]; then
        info "Existing clone found at $SOURCE_DIR — updating ..."
        cd "$SOURCE_DIR"
        git fetch --depth 1 origin "$OPENCLAW_VERSION"
        git checkout FETCH_HEAD
        cd "$PROJECT_ROOT"
        ok "Updated to $OPENCLAW_VERSION"
    else
        info "Cloning $OPENCLAW_REPO_URL @ $OPENCLAW_VERSION ..."
        rm -rf "$SOURCE_DIR"
        git clone --depth 1 --branch "$OPENCLAW_VERSION" "$OPENCLAW_REPO_URL" "$SOURCE_DIR" 2>/dev/null \
            || git clone --depth 1 "$OPENCLAW_REPO_URL" "$SOURCE_DIR"

        # If we cloned default branch but wanted a specific ref, check it out
        if [ "$OPENCLAW_VERSION" != "main" ] && [ "$OPENCLAW_VERSION" != "master" ]; then
            cd "$SOURCE_DIR"
            git fetch --depth 1 origin "$OPENCLAW_VERSION" 2>/dev/null && \
                git checkout FETCH_HEAD || true
            cd "$PROJECT_ROOT"
        fi
        ok "Cloned OpenClaw source to $SOURCE_DIR"
    fi

    # ── Step 2: Build base image from source ─────────────────────────────────
    banner "Step 2/3: Building base image from source ..."
    info "This may take several minutes on first build (Node.js deps + build) ..."

    DOCKER_BUILD_ARGS=""
    if [ -n "$OPENCLAW_EXTENSIONS" ]; then
        DOCKER_BUILD_ARGS="--build-arg OPENCLAW_EXTENSIONS=$OPENCLAW_EXTENSIONS"
    fi

    # Use the upstream Dockerfile (which is in the OpenClaw source tree, or our copy)
    UPSTREAM_DOCKERFILE="$SOURCE_DIR/Dockerfile"
    if [ ! -f "$UPSTREAM_DOCKERFILE" ]; then
        # Fall back to our reference copy
        UPSTREAM_DOCKERFILE="$OPENCLAW_DIR/Dockerfile.upstream"
        warn "No Dockerfile in source tree — using our reference copy"
    fi

    docker build \
        -f "$UPSTREAM_DOCKERFILE" \
        --platform "$OPENCLAW_PLATFORM" \
        $DOCKER_BUILD_ARGS \
        -t "$OPENCLAW_BASE_TAG" \
        "$SOURCE_DIR"

    ok "Base image built: $OPENCLAW_BASE_TAG"

elif [ -n "$PULL_IMAGE" ]; then
    # ── Pull mode: use an existing image as the base ─────────────────────────
    banner "Step 1/3: Pulling base image ..."
    info "Pulling $PULL_IMAGE ..."
    docker pull "$PULL_IMAGE"

    # Re-tag so our Dockerfile ARG default works
    docker tag "$PULL_IMAGE" "$OPENCLAW_BASE_TAG"
    ok "Pulled and tagged as $OPENCLAW_BASE_TAG"

else
    banner "Step 1/3: Skipping base build (--layer-only)"
    info "Using existing $OPENCLAW_BASE_TAG image"

    # Verify the base image exists
    if ! docker image inspect "$OPENCLAW_BASE_TAG" >/dev/null 2>&1; then
        err "Base image $OPENCLAW_BASE_TAG not found!"
        err "Run without --layer-only first, or use --pull <image>"
        exit 1
    fi
    ok "Base image $OPENCLAW_BASE_TAG exists"
fi

# ── Step 3: Build custom RustCode layer ─────────────────────────────────
if [ "$BUILD_LAYER" = true ]; then
    banner "Step 3/3: Building RustCode OpenClaw image ..."

    # When the base was built from source the Discord extension is properly
    # compiled (plugin-sdk/discord.js exists), so we keep it.  When using a
    # pulled/pre-built registry image the artifact is missing and causes a noisy
    # startup error — suppress it by removing the extension at layer-build time.
    if [ "$BUILD_BASE" = true ]; then
        SUPPRESS_DISCORD="false"
    else
        SUPPRESS_DISCORD="true"
    fi

    docker build \
        -f "$OPENCLAW_DIR/Dockerfile" \
        --build-arg "OPENCLAW_BASE_IMAGE=$OPENCLAW_BASE_TAG" \
        --build-arg "SUPPRESS_DISCORD_PLUGIN=$SUPPRESS_DISCORD" \
        --platform "$OPENCLAW_PLATFORM" \
        -t "$OPENCLAW_TAG" \
        "$PROJECT_ROOT"

    ok "Custom image built: $OPENCLAW_TAG"
else
    banner "Step 3/3: Skipping custom layer (--base-only)"
fi

# ── Summary ──────────────────────────────────────────────────────────────────
echo
banner "Build complete!"
echo
printf "  %-18s %s\n" "Base image:"  "$OPENCLAW_BASE_TAG"
printf "  %-18s %s\n" "Final image:" "$OPENCLAW_TAG"
echo
printf "${BOLD}Next steps:${NC}\n"
echo "  1. Verify:    docker run --rm $OPENCLAW_TAG node openclaw.mjs --version"
echo "  2. Compose:   cd $PROJECT_ROOT && docker compose up -d"
echo "  3. Logs:      docker compose logs -f openclaw-gateway"
echo
