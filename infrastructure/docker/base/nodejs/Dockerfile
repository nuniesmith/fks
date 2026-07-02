# =============================================================================
# FKS Web — SvelteKit frontend Dockerfile
#
# Builds the fks-web SvelteKit app. Source is acquired via git clone (prod/CI)
# or from the local build context (dev).
#
# Build (from repo root):
#   # Dev (local context):
#   docker compose build webui
#
#   # Prod (clone from GitHub):
#   docker compose build webui \
#     --build-arg WEB_REPO=https://github.com/nuniesmith/fks-web \
#     --build-arg WEB_REF=v2.1.0
#
# Source acquisition:
#   REPO_URL set   → git clone fks-web at REPO_REF, npm ci && npm run build
#   REPO_URL empty → bind-mount local src/web (dev, default)
# =============================================================================

ARG NODE_VERSION=22

# ── Stage 1: builder ──────────────────────────────────────────────────────────
FROM node:${NODE_VERSION}-alpine AS builder

ARG REPO_URL=""
ARG REPO_REF=main
ARG APP_SRC=src/web

WORKDIR /app

RUN apk add --no-cache git

# Source acquisition: git clone or copy from local context.
# `set -e` so a failed clone fails the BUILD — previously the trailing
# `rm -rf` returned 0 after a clone failure, letting the build continue into
# an empty directory and die confusingly at `npm ci` (missing lockfile).
RUN --mount=type=bind,source=.,target=/ctx \
    set -e; \
    if [ -n "${REPO_URL}" ]; then \
        git clone --depth=1 --branch "${REPO_REF}" "${REPO_URL}" /tmp/_repo; \
        cp -r /tmp/_repo/. .; \
        rm -rf /tmp/_repo; \
    else \
        cp -r /ctx/${APP_SRC}/. .; \
    fi

# Install dependencies (uses package-lock.json for reproducible installs)
RUN npm ci

# Build the SvelteKit app
RUN npm run build

# ── Stage 2: production runner ────────────────────────────────────────────────
FROM node:${NODE_VERSION}-alpine AS runner

WORKDIR /app

ENV NODE_ENV=production

# Copy the built output from the builder stage
COPY --from=builder --chown=node:node /app/build ./build
COPY --from=builder --chown=node:node /app/package.json ./package.json
COPY --from=builder --chown=node:node /app/package-lock.json ./package-lock.json

# Production deps only — no dev dependencies
RUN npm ci --only=production --no-optional && npm cache clean --force

USER node

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 --start-period=15s \
    CMD wget -qO- http://localhost:3000/health 2>/dev/null || exit 1

CMD ["node", "build/index.js"]
