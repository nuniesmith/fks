#!/bin/sh
# =============================================================================
# fks-migrate: apply every src/sql migration that this cluster hasn't recorded
# =============================================================================
#
# initdb runs the scripts in /docker-entrypoint-initdb.d only on an EMPTY
# volume, so a migration added later never reached a running database unless
# someone applied it by hand (#278's schema sat unapplied on the live fks_db;
# #296 found a clean database couldn't bootstrap past 016). This runs on every
# deploy instead, inside the postgres container so the scripts get the env
# they're written for (RUBY_DB, POSTGRES_USER, the role passwords):
#
#   docker exec fks_postgres fks-migrate
#
# Each file under /fks-sql/{janus,spawner} runs once, in file-name order, the
# way initdb runs it (psql, connected to POSTGRES_DB; each script \connects to
# the database it needs), and is then recorded in fks_db.schema_migrations by
# its path and sha256. The first run on a database initdb already built
# re-runs every file to adopt it: the scripts are idempotent by design
# (IF NOT EXISTS, DROP ... IF EXISTS before CREATE TRIGGER, \gexec for
# CREATE DATABASE), so that's a no-op apart from the ledger.
#
# A new migration must be a NEW file (next number), idempotent like the rest.
# A file edited after it was applied is reported, never re-run.
#
# *.validate.sql files are test scripts, not migrations, and are skipped.
set -eu

SQL_DIR=${FKS_SQL_DIR:-/fks-sql}
FKS_DB=${RUBY_DB:-fks_db}
ENTRY_DB=${POSTGRES_DB:-postgres}

pg() { psql -X -q -v ON_ERROR_STOP=1 -U "${POSTGRES_USER:-postgres}" "$@"; }

pg -d "$FKS_DB" -c "CREATE TABLE IF NOT EXISTS schema_migrations (
    version    TEXT PRIMARY KEY,         -- e.g. spawner/017_edge_experiments.sql
    sha256     TEXT NOT NULL,            -- of the file as applied
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
)"

applied=0
edited=0
for dir in janus spawner; do
    for f in "$SQL_DIR/$dir"/[0-9]*.sql; do
        [ -e "$f" ] || continue
        case "$f" in *.validate.sql) continue ;; esac
        version="$dir/$(basename "$f")"
        sum=$(sha256sum "$f" | cut -d' ' -f1)
        recorded=$(pg -At -d "$FKS_DB" -c "SELECT sha256 FROM schema_migrations WHERE version = '$version'")
        if [ -n "$recorded" ]; then
            if [ "$recorded" != "$sum" ]; then
                echo "fks-migrate: WARNING $version changed after it was applied; not re-running it (write a new migration instead)" >&2
                edited=$((edited + 1))
            fi
            continue
        fi
        echo "fks-migrate: applying $version"
        (cd "$SQL_DIR/$dir" && pg -d "$ENTRY_DB" -f "$(basename "$f")")
        pg -d "$FKS_DB" -c "INSERT INTO schema_migrations (version, sha256) VALUES ('$version', '$sum')"
        applied=$((applied + 1))
    done
done

total=$(pg -At -d "$FKS_DB" -c "SELECT count(*) FROM schema_migrations")
summary="fks-migrate: applied $applied, $total recorded"
if [ "$edited" -gt 0 ]; then
    summary="$summary, $edited edited after they were applied"
fi
echo "$summary"
