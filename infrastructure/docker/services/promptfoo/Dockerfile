# =============================================================================
# FKS — Promptfoo (LLM evaluation / red-teaming)
# =============================================================================
# Builder : npm ci installs all dependencies into node_modules
# Runtime : minimal node:slim with node_modules + eval configs
#
# Exposes :3000 for the Promptfoo web UI / API server
# =============================================================================

FROM node:22-alpine AS builder

WORKDIR /app

COPY infrastructure/config/promptfoo/package.json  package.json
COPY infrastructure/config/promptfoo/package-lock.json package-lock.json

# ci is faster and reproducible — honours the lockfile exactly
RUN npm ci --omit=dev --ignore-scripts


FROM node:22-alpine AS runtime

LABEL maintainer="nuniesmith" \
      description="Promptfoo LLM evaluation runner — regression tests for AI prompts"

RUN adduser --disabled-password --gecos '' --uid 1000 promptfoo

WORKDIR /app

COPY --from=builder /app/node_modules              node_modules
COPY infrastructure/config/promptfoo/              .

RUN chown -R promptfoo:promptfoo /app

USER promptfoo
EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD wget -qO- http://localhost:3000/health || exit 1

CMD ["node_modules/.bin/promptfoo", "view", "--port", "3000", "--yes"]
