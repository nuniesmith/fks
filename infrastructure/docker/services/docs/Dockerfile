# ==============================================================================
# docs — self-hosted documentation site (the WebUI /docs tab's backend)
#
# Builds the repo's MkDocs site (mkdocs.yml + docs/) into static HTML and
# serves it with nginx. The front proxy exposes it at /docs-viewer/ (prefix
# stripped), which the fks-web /docs page embeds. Before this service existed
# the embed pointed at nothing and the tab rendered a 404.
#
# Build context: repo root (docs/ + mkdocs.yml live here, not in a sub-repo).
# ==============================================================================

FROM squidfunk/mkdocs-material:latest AS builder

WORKDIR /build
COPY mkdocs.yml ./
COPY docs/ docs/
# The nav's Home is README.md, which lives at the repo root (not in docs/) —
# without it mkdocs emits no root index.html and the container's default
# welcome page leaks through.
COPY README.md docs/README.md

# site_url is a GitHub Pages URL in mkdocs.yml; --no-directory-urls is NOT
# used — material emits relative asset/page links, which survive being served
# behind the front proxy's stripped /docs-viewer/ prefix.
RUN mkdocs build --site-dir /site

FROM nginx:1.27-alpine

COPY --from=builder /site /usr/share/nginx/html

# The stack's standard container healthcheck probes localhost.
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD wget -q -O /dev/null http://localhost:80/ || exit 1

EXPOSE 80
