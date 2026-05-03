# =============================================================================
# FKS — PostgreSQL Init Image
# =============================================================================
#
# Extends the official postgres:16-alpine image by baking all schema
# initialisation scripts directly into the image via COPY.
#
# This avoids bind-mounting individual host files into
# /docker-entrypoint-initdb.d/, which fails on read-only rootfs mounts.
#
# SQL sources are organised by service under src/sql/:
#
#   src/sql/janus/     — janus_db schema  (Janus backward module)
#   src/sql/ruby/      — ruby_db schema   (Ruby engine + Spawner service)
#   src/sql/rustcode/  — rustcode db      (RustCode service + migrations)
#
# Init scripts are copied into /docker-entrypoint-initdb.d/ with a numeric
# prefix that controls lexicographic run order:
#
#   01-03  — Database + user bootstrap   (must run before any migrations)
#   10     — Janus migrations
#   20-26  — Ruby migrations
#   30-50  — RustCode migrations (in original migration order)
#
# Rebuild whenever SQL files change:
#   docker compose build postgres
#
# Environment variables consumed by the init scripts (passed via docker-compose):
#   POSTGRES_USER      — shared DB user for all databases  (default: fks_user)
#   POSTGRES_PASSWORD  — shared password
#   JANUS_DB           — Janus database name               (default: janus_db)
#   RUBY_DB            — Ruby engine database name         (default: ruby_db)
#   RUSTCODE_DB        — RustCode database name            (default: rustcode)
# =============================================================================

FROM postgres:16-alpine

# ---------------------------------------------------------------------------
# Phase 1 — Database bootstrap (must run first; creates DBs + grants)
# ---------------------------------------------------------------------------
COPY src/sql/janus/001_init.sql                           /docker-entrypoint-initdb.d/01-janus-init.sql
COPY src/sql/ruby/001_init.sql                            /docker-entrypoint-initdb.d/02-ruby-init.sql
COPY src/sql/rustcode/001_init.sql                        /docker-entrypoint-initdb.d/03-rustcode-init.sql

# ---------------------------------------------------------------------------
# Phase 2 — Janus migrations (janus_db)
# ---------------------------------------------------------------------------
COPY src/sql/janus/002_api_keys.sql                       /docker-entrypoint-initdb.d/10-janus-api-keys.sql

# ---------------------------------------------------------------------------
# Phase 3 — Ruby migrations (ruby_db)  — includes Spawner schema
# ---------------------------------------------------------------------------
COPY src/sql/ruby/002_futures.sql                         /docker-entrypoint-initdb.d/20-ruby-futures.sql
COPY src/sql/ruby/003_backup_tables.sql                   /docker-entrypoint-initdb.d/21-ruby-backup-tables.sql
COPY src/sql/ruby/004_news_and_registry.sql               /docker-entrypoint-initdb.d/22-ruby-news-and-registry.sql
COPY src/sql/ruby/005_chain.sql                           /docker-entrypoint-initdb.d/23-ruby-chain.sql
COPY src/sql/ruby/006_memories.sql                        /docker-entrypoint-initdb.d/24-ruby-memories.sql
COPY src/sql/ruby/007_spawner.sql                         /docker-entrypoint-initdb.d/25-ruby-spawner.sql
COPY src/sql/ruby/008_accounts.sql                        /docker-entrypoint-initdb.d/26-ruby-accounts.sql

# ---------------------------------------------------------------------------
# Phase 4 — RustCode migrations (rustcode db)
# ---------------------------------------------------------------------------
COPY src/sql/rustcode/002_github_integration.sql          /docker-entrypoint-initdb.d/30-rustcode-github-integration.sql
COPY src/sql/rustcode/003_scan_progress.sql               /docker-entrypoint-initdb.d/31-rustcode-scan-progress.sql
COPY src/sql/rustcode/004_require_git_url.sql             /docker-entrypoint-initdb.d/32-rustcode-require-git-url.sql
COPY src/sql/rustcode/005_notes_enhancements.sql          /docker-entrypoint-initdb.d/33-rustcode-notes-enhancements.sql
COPY src/sql/rustcode/006_documents.sql                   /docker-entrypoint-initdb.d/34-rustcode-documents.sql
COPY src/sql/rustcode/007_ideas.sql                       /docker-entrypoint-initdb.d/35-rustcode-ideas.sql
COPY src/sql/rustcode/008_fix_scan_events.sql             /docker-entrypoint-initdb.d/36-rustcode-fix-scan-events.sql
COPY src/sql/rustcode/009_queue_items.sql                 /docker-entrypoint-initdb.d/37-rustcode-queue-items.sql
COPY src/sql/rustcode/010_scan_checkpoints.sql            /docker-entrypoint-initdb.d/38-rustcode-scan-checkpoints.sql
COPY src/sql/rustcode/011_scan_progress_enhanced.sql      /docker-entrypoint-initdb.d/39-rustcode-scan-progress-enhanced.sql
COPY src/sql/rustcode/012_add_review_requested.sql        /docker-entrypoint-initdb.d/40-rustcode-add-review-requested.sql
COPY src/sql/rustcode/013_add_task_core_columns.sql       /docker-entrypoint-initdb.d/41-rustcode-add-task-core-columns.sql
COPY src/sql/rustcode/014_add_cache_hash.sql              /docker-entrypoint-initdb.d/42-rustcode-add-cache-hash.sql
COPY src/sql/rustcode/015_registered_repos.sql            /docker-entrypoint-initdb.d/43-rustcode-registered-repos.sql
COPY src/sql/rustcode/016_add_document_pinned.sql         /docker-entrypoint-initdb.d/44-rustcode-add-document-pinned.sql
COPY src/sql/rustcode/017_drop_todo_items.sql             /docker-entrypoint-initdb.d/45-rustcode-drop-todo-items.sql
COPY src/sql/rustcode/018_chunks_integer_to_bigint.sql    /docker-entrypoint-initdb.d/46-rustcode-chunks-integer-to-bigint.sql
COPY src/sql/rustcode/019_multi_tenant_tables.sql         /docker-entrypoint-initdb.d/47-rustcode-multi-tenant-tables.sql
COPY src/sql/rustcode/020_documents_integer_to_bigint.sql /docker-entrypoint-initdb.d/48-rustcode-documents-integer-to-bigint.sql
COPY src/sql/rustcode/021_audit_runs.sql                  /docker-entrypoint-initdb.d/49-rustcode-audit-runs.sql
COPY src/sql/rustcode/022_simplified_tasks.sql            /docker-entrypoint-initdb.d/50-rustcode-simplified-tasks.sql
