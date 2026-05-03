# syntax=docker/dockerfile:1.7
# =============================================================================
# RustCode — Custom OpenClaw Image
# =============================================================================
#
# Layers RustCode agent config, workspace defaults, and environment
# overrides on top of the upstream OpenClaw base image.
#
# The base image is built from source by build.sh (see Dockerfile.upstream)
# or pulled from a registry. Either way, this Dockerfile adds our customisation
# layer so the container starts pre-configured for the RUSTCODE stack.
#
# Build (standalone — usually invoked by build.sh):
#   docker build -f docker/openclaw/Dockerfile \
#       --build-arg OPENCLAW_BASE_IMAGE=openclaw-base:local \
#       -t openclaw:local .
#
# Build args:
#   OPENCLAW_BASE_IMAGE       Base image tag (default: openclaw-base:local)
#   SUPPRESS_DISCORD_PLUGIN   Remove the upstream Discord extension at build time
#                             (default: true). The upstream registry image ships
#                             TypeScript extension source without the compiled
#                             plugin-sdk artifact, causing a harmless but noisy
#                             startup error. Set to false only when building
#                             openclaw-base:local from source (build.sh), which
#                             compiles the extension properly.
# =============================================================================

ARG OPENCLAW_BASE_IMAGE=openclaw-base:local
ARG SUPPRESS_DISCORD_PLUGIN=true
FROM ${OPENCLAW_BASE_IMAGE}
# Re-declare ARG after FROM so it is visible in the build stage.
ARG SUPPRESS_DISCORD_PLUGIN=true

LABEL org.opencontainers.image.source="https://github.com/nuniesmith/rustcode" \
    org.opencontainers.image.title="RustCode OpenClaw" \
    org.opencontainers.image.description="OpenClaw gateway customised for the RustCode stack"

# ── Optional: remove broken upstream Discord extension ───────────────────────
# The upstream registry image ships the Discord extension as TypeScript source
# but omits the compiled plugin-sdk/discord.js artifact, so the plugin fails
# to load at startup with a "Cannot find module" error.  Remove it here when
# using the pulled image as a base; leave it in place when building from source
# (build.sh --pull false) because the source build compiles the artifact.
RUN if [ "${SUPPRESS_DISCORD_PLUGIN}" = "true" ] && [ -d /app/extensions/discord ]; then \
        echo "[rc-build] Removing uncompiled Discord extension (set SUPPRESS_DISCORD_PLUGIN=false to keep)"; \
        rm -rf /app/extensions/discord; \
    fi

# ── Bake in RustCode agent configuration ────────────────────────────────
# agents.yml defines the briefer, session-scribe, and default agent personas
# along with tool bindings (GitHub, Discord, RUSTCODE semantic search, RUSTCODE ingest).
USER root
RUN mkdir -p /home/node/.openclaw/config \
    /home/node/.openclaw/workspace/sessions \
    /home/node/.openclaw/workspace/notes \
    && chown -R node:node /home/node/.openclaw

COPY --chown=node:node infrastructure/config/openclaw/agents.yml /home/node/.openclaw/config/agents.yml
COPY --chown=node:node infrastructure/config/openclaw/openclaw.json /home/node/.openclaw/openclaw.json

# ── RustCode-specific environment defaults ──────────────────────────────
# These are defaults — docker-compose environment{} and .env still override.
ENV OPENCLAW_CONFIG_DIR=/home/node/.openclaw \
    OPENCLAW_WORKSPACE_DIR=/home/node/.openclaw/workspace \
    NODE_ENV=production

# ── Drop back to non-root ───────────────────────────────────────────────────
USER node

# Inherit upstream HEALTHCHECK and CMD — no changes needed.
# CMD ["node", "openclaw.mjs", "gateway", "--allow-unconfigured"]
# (overridden by docker-compose command: stanza anyway)
